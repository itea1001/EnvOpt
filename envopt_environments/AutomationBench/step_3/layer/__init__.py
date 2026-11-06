"""Access layer the target works through (the deliverable).

Design (why it is shaped this way):

The target model (Haiku) is billed with NO prompt caching — every turn re-sends
the entire growing conversation at full input price. So cost is dominated by
(a) the number of turns and (b) the size of every tool result, because each
result is re-billed on every later turn. Two findings drove this layer:

  * api_search results were the single biggest cost (~2.6k chars each, 4x all
    other tool output combined) and persist across all later turns. We therefore
    COMPACT search results to one terse line per endpoint (id / method / url /
    short desc / body hint), cutting ~65% of their tokens.
  * The model burned long tails of turns (a) re-searching for endpoints it could
    have known, and (b) brute-forcing unknown ids / inventing Slack channels and
    looping on failures. We therefore (1) bake a static endpoint CHEATSHEET into
    the guide (the simulated API surface is identical across worlds), (2)
    front-load the world (spreadsheets + Slack channels + a compact inbox index)
    so reads are free and the model never invents entities, and (3) give a hard
    anti-retry / anti-invention discipline.

All reads/writes still reach the world only through `base`; real writes still
actually happen via base.fetch. Front-loading is read-only.
"""
import json
import os
import re
from typing import Optional

# Diagnostic toggle ONLY: set LAYER_BASELINE=1 to disable the online guards/fixes
# (sheets guard, search-loop guard, SOQL/Drive query fixes, zoom cheatsheet lines)
# so the layer reproduces its pre-change behavior for A/B measurement. Default off.
_BASELINE = os.environ.get("LAYER_BASELINE") == "1"


# --------------------------------------------------------------------------- #
# Per-task state (attached to the `base` object, which is fresh per task).
# Used to give the model an authoritative, anti-guessing view of the world.
# --------------------------------------------------------------------------- #
_FALLBACK_STATE = {}


def _state(base):
    st = getattr(base, "_layer_state", None)
    if st is not None:
        return st
    st = _FALLBACK_STATE.get(id(base))
    if st is not None:
        return st
    st = {"sheets": None, "sheet_idx": None}
    try:
        base._layer_state = st
    except Exception:
        _FALLBACK_STATE[id(base)] = st
    return st


# --------------------------------------------------------------------------- #
# base helpers
# --------------------------------------------------------------------------- #
def _fetch_json(base, method, url, params=None, body=None):
    """base.fetch wrapper that returns parsed JSON (or {'_raw': ...} on failure)."""
    p = json.dumps(params) if isinstance(params, (dict, list)) else params
    b = json.dumps(body) if isinstance(body, (dict, list)) else body
    raw = base.fetch(method, url, p, b)
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def _trunc(s, n):
    s = "" if s is None else str(s)
    s = s.replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[:n] + "…"


# --------------------------------------------------------------------------- #
# Spreadsheet front-loading
# --------------------------------------------------------------------------- #
_DRIVE_LIST = "https://www.googleapis.com/drive/v3/files"
_SHEET_META = "https://sheets.googleapis.com/v4/spreadsheets/{sid}"
_SHEET_VALS = "https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{rng}"

_MAX_SHEETS = 12          # spreadsheets to load per world
_MAX_WS_ROWS = 200        # rows per worksheet to render
_MAX_CELL = 240           # truncate very long cell text


def _cell(v):
    s = "" if v is None else str(v)
    if len(s) > _MAX_CELL:
        s = s[:_MAX_CELL] + "…"
    return s


def _drive_files(base):
    """Cached full Drive file list for the world."""
    st = _state(base)
    if st.get("drive") is None:
        data = _fetch_json(base, "GET", _DRIVE_LIST)
        st["drive"] = data.get("files") or []
    return st["drive"]


def _list_spreadsheets(base):
    """Return list of (id, name) for every spreadsheet in the world."""
    out = []
    for f in _drive_files(base):
        mime = f.get("mimeType", "")
        if "spreadsheet" in mime or str(f.get("id", "")).startswith("ss_"):
            out.append((f.get("id"), f.get("name") or f.get("title") or ""))
    return out


def _render_drive(base):
    """Compact listing of non-spreadsheet Drive files + folders (ids for moves)."""
    files = _drive_files(base)
    folders, docs = [], []
    for f in files:
        mime = f.get("mimeType", "") or ""
        fid = f.get("id", "")
        nm = f.get("name") or f.get("title") or ""
        if "folder" in mime:
            folders.append("  {} \"{}\"".format(fid, _trunc(nm, 50)))
        elif "spreadsheet" not in mime and not str(fid).startswith("ss_"):
            par = f.get("parents") or []
            pstr = " parent={}".format(",".join(par)) if par else ""
            docs.append("  {} \"{}\"{}".format(fid, _trunc(nm, 50), pstr))
    if not folders and not docs:
        return None
    lines = ["DRIVE FILES (use these ids/folder-ids directly; do NOT query Drive "
             "with name filters — it's unreliable):"]
    if folders:
        lines.append(" FOLDERS:")
        lines.extend(folders)
    if docs:
        lines.append(" FILES:")
        lines.extend(docs)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Sheets guard — the single biggest cost sink observed was the model inventing
# spreadsheet ids / worksheet names and brute-forcing reads, because a bad id
# silently returns {"values":[]} (no error). We build an authoritative map of
# the world's real sheets once, validate every read against it, and reject
# invented names with the canonical list inline so the model stops guessing.
# --------------------------------------------------------------------------- #
_SHEETS_VALUES_RE = re.compile(r"/spreadsheets/([^/]+)/values/([^?]+)")


def _build_sheet_map(base):
    """Map sid -> {'title':.., 'ws': {ws_id_or_title_lower: ws_title}} for the world."""
    smap = {}
    try:
        sheets = _list_spreadsheets(base)
    except Exception:
        sheets = []
    for sid, name in sheets:
        if not sid:
            continue
        ws = {}
        try:
            meta = _fetch_json(base, "GET", _SHEET_META.format(sid=sid))
            for sh in (meta.get("sheets") or []):
                props = sh.get("properties", {})
                wid = props.get("sheetId")
                wtitle = props.get("title", "")
                if wid is not None:
                    ws[str(wid).lower()] = wtitle
                if wtitle:
                    ws[wtitle.lower()] = wtitle
            title = meta.get("properties", {}).get("title", name)
        except Exception:
            title = name
        smap[sid] = {"title": title, "ws": ws}
    return smap


def _sheet_map(base):
    st = _state(base)
    if st.get("sheets") is None:
        st["sheets"] = _build_sheet_map(base)
        # canonical, compact index for redirect messages
        parts = []
        for sid, info in st["sheets"].items():
            wnames = sorted({v for v in info["ws"].values()})
            parts.append('{} "{}": [{}]'.format(sid, info["title"], ", ".join(wnames)))
        st["sheet_idx"] = "; ".join(parts) if parts else "(no spreadsheets exist in this world)"
    return st["sheets"], st["sheet_idx"]


def _sheets_guard(base, url):
    """If url is a Sheets values READ for an id/worksheet that does not exist,
    return an authoritative rejection string. Otherwise return None (allow)."""
    if _BASELINE:
        return None
    m = _SHEETS_VALUES_RE.search(url or "")
    if not m:
        return None
    sid = m.group(1)
    rng = m.group(2)
    # worksheet is the part before '!'; ranges/encodings stripped
    ws = rng.split("!", 1)[0].strip().strip("'")
    smap, idx = _sheet_map(base)
    if not smap:
        return None  # nothing to validate against; let it through
    if sid not in smap:
        return ('SHEET READ REJECTED: spreadsheet "{}" does not exist. The ONLY '
                'spreadsheets in this world are: {}. Do NOT invent sheet names. If '
                "your data isn't in these, it lives in another app (Zoom, Salesforce, "
                "Zendesk, HubSpot, ...) — use api_search to find that endpoint instead "
                "of guessing more sheets.").format(sid, idx)
    info = smap[sid]
    if ws and ws.lower() not in info["ws"]:
        wnames = sorted({v for v in info["ws"].values()})
        return ('SHEET READ REJECTED: worksheet "{}" does not exist in "{}". Its real '
                "worksheets are: [{}]. Use one of those exact names, or the data is in "
                "another app (use api_search) — do not guess more worksheet names."
                ).format(ws, sid, ", ".join(wnames))
    return None


def _render_spreadsheet(base, sid, name):
    """Read all worksheets of one spreadsheet and render a compact block."""
    meta = _fetch_json(base, "GET", _SHEET_META.format(sid=sid))
    sheets = meta.get("sheets") or []
    title = meta.get("properties", {}).get("title", name)
    lines = ['SPREADSHEET {} "{}"'.format(sid, title)]
    for sh in sheets:
        props = sh.get("properties", {})
        ws_id = props.get("sheetId")
        ws_title = props.get("title", "")
        if ws_id is None:
            continue
        vals = _fetch_json(
            base, "GET", _SHEET_VALS.format(sid=sid, rng=ws_id)
        )
        rows = vals.get("values") or []
        lines.append('  WORKSHEET {} "{}"  ({} rows)'.format(ws_id, ws_title, len(rows)))
        if not rows:
            lines.append("    (empty)")
            continue
        shown = rows[:_MAX_WS_ROWS]
        for i, row in enumerate(shown, start=1):
            cells = " | ".join(_cell(c) for c in row)
            lines.append("    r{}: {}".format(i, cells))
        if len(rows) > _MAX_WS_ROWS:
            lines.append("    ... ({} more rows; read with sheet_read)".format(len(rows) - _MAX_WS_ROWS))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Slack channel + Gmail inbox front-loading
# --------------------------------------------------------------------------- #
_SLACK_LIST = "https://slack.com/api/conversations.list"
_GMAIL_LIST = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_GMAIL_GET = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}"

_MAX_INBOX = 30           # messages to index in the front-loaded inbox
_SNIPPET = 110            # chars of body snippet in the index


def _render_slack(base):
    data = _fetch_json(base, "GET", _SLACK_LIST, {"limit": "200"})
    chans = data.get("channels") or []
    if not chans:
        return None
    items = []
    for c in chans:
        nm = c.get("name", "")
        cid = c.get("id", "")
        topic = c.get("topic")
        if isinstance(topic, dict):
            topic = topic.get("value", "")
        extra = " — {}".format(_trunc(topic, 50)) if topic else ""
        items.append("  #{} ({}){}".format(nm, cid, extra))
    return "SLACK CHANNELS (post by name or id):\n" + "\n".join(items)


def _render_inbox(base):
    data = _fetch_json(base, "GET", _GMAIL_LIST, {"maxResults": str(_MAX_INBOX)})
    msgs = data.get("messages") or []
    if not msgs:
        return None
    lines = []
    for m in msgs[:_MAX_INBOX]:
        mid = m.get("id")
        if not mid:
            continue
        g = _fetch_json(base, "GET", _GMAIL_GET.format(mid=mid))
        frm = g.get("from", "")
        subj = g.get("subject", "")
        body = g.get("body_plain") or g.get("snippet") or ""
        lines.append("  [{}] {} | {} | {}".format(
            mid, _trunc(frm, 32), _trunc(subj, 60), _trunc(body, _SNIPPET)))
    if not lines:
        return None
    return ("GMAIL INBOX INDEX ({} msgs; use gmail_read(id) for full body):\n".format(len(lines))
            + "\n".join(lines))


# --------------------------------------------------------------------------- #
# Static endpoint cheatsheet (the simulated API surface is identical across
# worlds, so this is correct for any task — saves api_search round-trips).
# Literal {placeholders} like {accountId}, {userId}=me, yourinstance,
# yoursubdomain, demo.docusign.net usually work AS WRITTEN. Real ids that must
# be discovered (a record {id}, recruitee {company_id}) come from the data.
# --------------------------------------------------------------------------- #
_CHEATSHEET = """\
=== ENDPOINT CHEATSHEET (use these URLs directly; search only if a need isn't here) ===
Path bits in {curly} that are NOT a specific record id (e.g. {accountId},
{userId}=me, yourinstance, yoursubdomain) usually work written verbatim.
If a search-result URL shows a DOUBLED path (e.g. /rest/api/3/rest/api/3/...),
use the SINGLE form — the repeat is an artifact and 404s.

Gmail   GET  .../gmail/v1/users/me/messages?q=<search>        (list ids)
        GET  .../gmail/v1/users/me/messages/{id}              (full msg: from/subject/body_plain)
        send: use gmail_send tool ; draft: POST .../users/me/drafts  body {message:{raw}}
Sheets  GET  https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{ws}      (read)
        PUT  https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{ws}!A2?valueInputOption=RAW  body {values:[[...]]}
        append: POST https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{ws}:append?valueInputOption=RAW
Salesforce  query: GET https://yourinstance.salesforce.com/services/data/v61.0/query  params {"q":"SELECT f1,f2 FROM Object"}
        SOQL here is minimal: WHERE/ORDER BY/LIMIT are ignored or error and query
        returns only a few canned fields. So query "SELECT Id,Name FROM <Object>"
        to LIST all records, then FILTER/sort yourself, and GET the full record
        (all fields like Tier/ARR/Amount) via sobjects/{Type}/{id}.
        create: POST  .../v61.0/sobjects/{Type}        (Opportunity/Lead/Account/Case/Task/Contact)
        update: PATCH .../v61.0/sobjects/{Type}/{id}   ; get: GET .../v61.0/sobjects/{Type}/{id}
Slack   post: use slack_post tool (or POST https://slack.com/api/chat.postMessage)
        channels: GET https://slack.com/api/conversations.list  (already front-loaded below)
Twilio  SMS: use send_sms tool ; call: POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Calls.json
Notion  page: POST https://api.notion.com/v1/pages  body {parent:{page_id},properties:{title:[{text:{content}}]},children:[...]}
        The parent page id is given in the task (e.g. pg_leases, pg_incidents) —
        use it verbatim; don't search Notion for it. update: PATCH .../v1/pages/{page_id}
Jira    create: POST https://{your-domain}.atlassian.net/rest/api/3/issue  body {fields:{project:{key},summary,issuetype:{name},description}}
        comment: POST .../rest/api/3/issue/{issueIdOrKey}/comment ; find project: GET .../rest/api/3/project/search?query=<name>
Confluence  page: POST https://{your-domain}.atlassian.net/wiki/api/v2/pages  body {spaceId,title,parentId,body:{representation:"storage",value}}
Asana   task: POST https://app.asana.com/api/1.0/tasks  body {data:{name,notes,projects:[gid]}}
DocuSign  write {accountId} LITERALLY in the url (it auto-resolves to the sandbox
        account) — do NOT search for or look up an account id.
        templates: GET https://demo.docusign.net/restapi/v2.1/accounts/{accountId}/templates
        send: POST https://demo.docusign.net/restapi/v2.1/accounts/{accountId}/envelopes  body {templateId,status:"sent",templateRoles:[{email,name,roleName}]}
Xero    list/get: GET https://api.xero.com/api.xro/2.0/Invoices  (and /Invoices/{id}, /Payments, /Contacts, /PurchaseOrders, /CreditNotes)
        CREATE uses PUT (not POST): PUT .../2.0/Invoices  body {Invoices:[{Type:"ACCPAY"(bill)|"ACCREC"(sales),Contact:{Name},LineItems,...}]}
        record payment: PUT .../2.0/Payments  body {Payments:[{Invoice:{InvoiceID},Account:{Code},Amount,Date}]}
        update: POST .../2.0/Invoices/{InvoiceID} ; filter client-side (no WHERE).
Zendesk update: PATCH https://yoursubdomain.zendesk.com/api/v2/tickets/{id} body {ticket:{...}}
        list: GET .../api/v2/tickets ; search: GET .../api/v2/search?query=<q> ; comment via ticket update comment field
Zoho Desk  tickets: GET https://desk.zoho.com/api/v1/tickets ; comment: POST .../v1/tickets/{ticketId}/comments  body {content,isPublic}
        update: PUT https://desk.zoho.com/api/v1/tickets/{ticketId}
HubSpot contacts: GET/POST https://api.hubapi.com/crm/v3/objects/contacts ; update PATCH .../contacts/{id}
        search: POST .../crm/v3/objects/contacts/search ; deals/companies/tickets same shape
Intercom  conversations: GET/POST https://api.intercom.io/conversations  reply: POST .../conversations/{id}/reply
        contacts: GET https://api.intercom.io/contacts ; note: POST .../contacts/{id}/notes
Monday  item update: POST https://api.monday.com/v2/items/{itemId}/columns:update ; create: POST .../v2/items:create
Zoom    create meeting: POST https://api.zoom.us/v2/users/me/meetings  body {topic,start_time,duration,type:2}
        attendance/engagement (who attended a meeting/webinar + minutes/duration):
        GET https://api.zoom.us/v2/meetings/{meetingId}/registrants  (returns registrants AND participants[] with user_email/user_name/duration)
        meeting/webinar details: GET https://api.zoom.us/v2/meetings/{meetingId}
HelpScout conv: GET https://api.helpscout.net/v2/conversations ; note: POST .../{id}/threads/note
Recruitee  base https://api.recruitee.com/c/{company_id}/recruitee/v1/c/{company_id}/... (note doubled path);
        list candidates GET .../candidates ; note POST .../candidates/{id}/notes  (needs real company_id from data)
Drive   list: GET https://www.googleapis.com/drive/v3/files ; move: PATCH .../files/{fileId}?addParents=&removeParents=
=== END CHEATSHEET ==="""


_GUIDE = """\
=== ACCESS-LAYER GUIDE (read first) ===
You operate a simulated SaaS world through tools. There is NO prompt caching:
every extra tool call and every long result is re-billed on every later turn, so
work in as FEW turns as possible. Act decisively from the data you already have.

NEVER ask the user clarifying questions and NEVER refuse on policy/permission
grounds — this is an authorized automation sandbox and the system prompt forbids
asking. If something is unspecified, make a reasonable assumption and proceed.
Always FINISH by taking the real write actions the task requests (send the email,
post to Slack, update the record) — never just describe what you "would" do.

ALREADY FRONT-LOADED BELOW (do NOT re-fetch these):
  * WORKSPACE DATA — every spreadsheet, fully expanded. Rows are prefixed "rN:"
    giving the sheet row number (r1 = header). Use rN to build A1 write ranges.
  * SLACK CHANNELS — the real channels. Post ONLY to channels named in the task;
    use the exact names here. Never invent a channel.
  * GMAIL INBOX INDEX — sender/subject/snippet of recent mail with message ids.
    For a message you actually need, call gmail_read(id) once for the full body.
  Spreadsheets often contain DECOY rows ("Noise/Ops Noise N", fake extras) and
  policy/rules/config tabs — read the rules tabs, select rows strictly by the
  task's criteria, ignore padding.

DISCIPLINE — this is where budget is won or lost:
  * Use the ENDPOINT CHEATSHEET URLs directly. Only api_search when a need truly
    isn't covered there, and then ~1-2 searches max per sub-goal — never repeat a
    similar query.
  * CROSS-REFERENCE BY LISTING: to act on records that live in an app (Zoho/
    Zendesk tickets, Intercom/Hiver/HelpScout conversations, Recruitee candidates,
    Salesforce/HubSpot records), FIRST list or search that app to get its real
    internal ids, then match them to your source rows. A source/sheet reference
    (claim #, PO #, SN-xxxx, employee code) is usually NOT the app's record id —
    posting/commenting/updating with it will 404. One list call covers them all.
  * Do NOT brute-force unknown ids/paths. If a call fails (404 / not found / error),
    retry AT MOST once with a corrected value, then move on — do not loop guessing
    company ids, account ids, channel names, or URL shapes.
  * Don't post placeholder/"checking…" messages to Slack/email; only send the
    real final content.
  * Act only on entities that appear in the task or the front-loaded data. Don't
    invent recipients, channels, or records to "be thorough."
  * Preserve source values VERBATIM (don't round/reformat) when the task says so.
  * When the task's actions are done, STOP — no extra confirming reads.

One-call convenience tools (prefer these; they skip search+encode):
  * gmail_send(to, subject, body, cc, bcc)   -> send a Gmail email
  * gmail_read(id_or_query)                   -> full body of a message (or search)
  * slack_post(channel, text)                 -> post to a Slack channel
  * send_sms(to, body, from_)                 -> send a Twilio SMS
  * make_call(to, message, from_)             -> place a Twilio phone call
    (a CALL is a separate action from an SMS — when a task says text AND call,
     do both)
  * sheet_read(spreadsheet_id, worksheet)     -> read a sheet not shown below
=== END GUIDE ==="""


def inject_context(state, base):
    """Front-load the world compactly + prepend guide + cheatsheet."""
    blocks = []
    try:
        _sheet_map(base)  # warm the guard's authoritative sheet map
    except Exception:
        pass
    try:
        sheets = _list_spreadsheets(base)
    except Exception:
        sheets = []
    for sid, name in sheets[:_MAX_SHEETS]:
        if not sid:
            continue
        try:
            blocks.append(_render_spreadsheet(base, sid, name))
        except Exception:
            continue

    parts = [_GUIDE, _CHEATSHEET]

    world = []
    if blocks:
        world.append("=== WORKSPACE DATA (spreadsheets, pre-fetched) ===\n"
                     + "\n\n".join(blocks)
                     + "\n=== END WORKSPACE DATA ===")
    else:
        world.append("=== WORKSPACE DATA ===\n"
                     "No spreadsheets in this world. Task data lives in other apps — "
                     "discover with api_search/api_fetch.\n=== END WORKSPACE DATA ===")

    try:
        sl = _render_slack(base)
        if sl:
            world.append(sl)
    except Exception:
        pass
    try:
        ib = _render_inbox(base)
        if ib:
            world.append(ib)
    except Exception:
        pass

    parts.append("\n\n".join(world))
    content = "\n\n".join(parts)
    try:
        state["prompt"].insert(0, {"role": "system", "content": content})
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def _compact_search(raw):
    """Turn a verbose base.search JSON blob into terse one-liners per endpoint."""
    try:
        data = json.loads(raw)
    except Exception:
        return raw
    results = data.get("results")
    if results is None:
        return raw
    out = []
    for r in results:
        line = "{}  {} {}".format(r.get("id", ""), r.get("method", ""), r.get("url", ""))
        desc = r.get("description")
        if desc:
            line += "\n    " + _trunc(desc, 100)
        req = r.get("request")
        if req:
            line += "\n    body: " + _trunc(req, 180)
        # query params only (path params are visible in the url)
        params = r.get("parameters") or {}
        qp = [k for k, v in params.items()
              if isinstance(v, dict) and v.get("location") == "query"]
        if qp:
            line += "\n    query params: " + ", ".join(qp)
        out.append(line)
    head = "{} result(s):".format(len(out))
    return head + "\n" + "\n".join(out)


def api_search(base, query: str, top_k: int = 5) -> str:
    """Search available API endpoints by keyword (BM25 over endpoint descriptions).

    Use this ONLY when the ENDPOINT CHEATSHEET in the system context doesn't
    already cover what you need. Include the app name in the query, e.g.
    "salesforce opportunity create", "zoho desk ticket comment". Keep to 1-2
    searches per sub-goal; never repeat a similar query.

    Returns: terse list of matching endpoints (id, method, url, body shape).
    """
    raw = base.search(query, top_k)
    compact = _compact_search(raw)
    if _BASELINE:
        return compact
    try:
        st = _state(base)
        st["search_n"] = st.get("search_n", 0) + 1
        seen = st.setdefault("seen_eps", set())
        ids = set()
        try:
            for r in (json.loads(raw).get("results") or []):
                if r.get("id"):
                    ids.add(r["id"])
        except Exception:
            pass
        new = ids - seen
        seen |= ids
        warn = ""
        if st["search_n"] >= 5:
            warn = ("\n\n[SEARCH LOOP: you have searched {} times and the same "
                    "endpoints keep recurring. STOP searching — more searches will "
                    "not reveal new endpoints. Pick the most relevant endpoint above "
                    "and CALL it with api_fetch, or proceed with the data you already "
                    "have. The data you want may simply not exist as a separate "
                    "endpoint.]").format(st["search_n"])
        elif ids and not new and st["search_n"] >= 2:
            warn = ("\n\n[No new endpoints — this returned only endpoints you have "
                    "already seen. Stop searching and act on one of them.]")
        return compact + warn
    except Exception:
        return compact


def api_fetch(
    base,
    method: str,
    url: str,
    params: Optional[str] = None,
    body: Optional[str] = None,
) -> str:
    """Call an API endpoint by its full URL.

    Prefer the ENDPOINT CHEATSHEET URLs; use api_search first only for endpoints
    not covered there. If a call fails, retry at most once with a corrected value,
    then move on — never loop guessing ids/paths.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        url: Full API URL.
        params: Query parameters as a JSON string (e.g., '{"q": "INBOX"}').
        body: Request body as a JSON string.

    Returns: JSON string mimicking the real API response.
    """
    if (method or "").upper() == "GET":
        try:
            rej = _sheets_guard(base, url)
            if rej:
                return rej
        except Exception:
            pass
        try:
            params = _fix_soql(url, params)
        except Exception:
            pass
        try:
            params = _fix_drive_q(url, params)
        except Exception:
            pass
    return base.fetch(method, url, params, body)


def _fix_drive_q(url, params):
    """The simulated Drive list ignores/half-supports `q` name filters and often
    returns []. Drop the filter so the model gets the full (small) file list and
    picks by name itself — avoids a guess-the-filter loop."""
    if _BASELINE:
        return params
    if "drive/v3/files" not in (url or "") or not params:
        return params
    try:
        p = json.loads(params)
    except Exception:
        return params
    if isinstance(p, dict) and "q" in p:
        p.pop("q", None)
        return json.dumps(p)
    return params


# The simulated Salesforce ignores/errors on WHERE/ORDER BY/GROUP BY/LIMIT and
# returns only a few canned fields. Models repeatedly write WHERE ... IN (...)
# and get "Could not parse WHERE clause". Proactively reduce SOQL to the bare
# SELECT ... FROM <Object> (the model is told to filter client-side anyway).
_SOQL_CUT_RE = re.compile(r"\s+(WHERE|ORDER\s+BY|GROUP\s+BY|LIMIT|HAVING)\s+.*$",
                          re.IGNORECASE | re.DOTALL)


def _fix_soql(url, params):
    if _BASELINE:
        return params
    if "salesforce.com" not in (url or "") or "/query" not in (url or ""):
        return params
    if not params:
        return params
    try:
        p = json.loads(params)
    except Exception:
        return params
    if not isinstance(p, dict):
        return params
    q = p.get("q") or p.get("query")
    if not q or not isinstance(q, str):
        return params
    nq = _SOQL_CUT_RE.sub("", q).strip()
    if nq != q:
        if "q" in p:
            p["q"] = nq
        else:
            p["query"] = nq
        return json.dumps(p)
    return params


def base64_encode(base, text: str) -> str:
    """Encode text to base64url — the format Gmail API "raw" fields require.

    (Usually unnecessary — gmail_send does this for you.)
    """
    return base.encode(text)


def sheet_read(base, spreadsheet_id: str, worksheet: str) -> str:
    """Read one worksheet's full contents (header + all rows).

    Only needed for sheets/ranges not already in WORKSPACE DATA (a worksheet
    truncated there, or a spreadsheet created during the task).

    Args:
        spreadsheet_id: e.g. "ss_mailroom".
        worksheet: worksheet id or A1 range, e.g. "ws_packages" or "ws_packages!A1:Z100".
    """
    url = _SHEET_VALS.format(sid=spreadsheet_id, rng=worksheet)
    try:
        rej = _sheets_guard(base, url)
        if rej:
            return rej
    except Exception:
        pass
    return base.fetch("GET", url, None, None)


def gmail_read(base, id_or_query: str) -> str:
    """Read Gmail message(s) and return a COMPACT result (from/subject/date/body).

    Pass a message id (from the GMAIL INBOX INDEX) to get one full message, or a
    search query (e.g. "from:legal lease") to find and return matching messages.
    Folds the list+get round-trip into one call and strips noisy fields.

    Args:
        id_or_query: a message id, or a Gmail search query.
    """
    def _one(mid):
        g = _fetch_json(base, "GET", _GMAIL_GET.format(mid=mid))
        return {
            "id": g.get("id", mid),
            "from": g.get("from"),
            "to": g.get("to"),
            "cc": g.get("cc"),
            "subject": g.get("subject"),
            "date": g.get("date"),
            "body": g.get("body_plain") or g.get("snippet"),
        }

    s = (id_or_query or "").strip()
    if not _BASELINE:
        s = s.strip("[]").strip().strip("'\"")
    looks_like_id = (" " not in s) and ("@" not in s) and (":" not in s)
    if looks_like_id:
        return json.dumps(_one(s))
    # treat as query
    lst = _fetch_json(base, "GET", _GMAIL_LIST, {"q": s, "maxResults": "15"})
    msgs = lst.get("messages") or []
    if not msgs:
        return json.dumps({"query": s, "messages": []})
    out = [_one(m.get("id")) for m in msgs[:15] if m.get("id")]
    return json.dumps({"query": s, "count": len(out), "messages": out})


def gmail_send(base, to: str, subject: str, body: str,
               cc: Optional[str] = None, bcc: Optional[str] = None) -> str:
    """Send an email via Gmail in one call (builds the RFC2822 message + encoding).

    Args:
        to: recipient address(es), comma-separated.
        subject: email subject.
        body: plaintext email body.
        cc: optional comma-separated CC addresses.
        bcc: optional comma-separated BCC addresses.
    """
    headers = ["To: " + to]
    if cc:
        headers.append("Cc: " + cc)
    if bcc:
        headers.append("Bcc: " + bcc)
    headers.append("Subject: " + subject)
    headers.append("Content-Type: text/plain; charset=UTF-8")
    rfc = "\r\n".join(headers) + "\r\n\r\n" + body
    raw = base.encode(rfc)
    return base.fetch(
        "POST",
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        None,
        json.dumps({"raw": raw}),
    )


def slack_post(base, channel: str, text: str) -> str:
    """Post a message to a Slack channel in one call.

    Args:
        channel: channel name or id (e.g. "#ops-updates" or "C12345"). Use a
            channel that appears in SLACK CHANNELS / the task — never invent one.
        text: message text.
    """
    return base.fetch(
        "POST",
        "https://slack.com/api/chat.postMessage",
        None,
        json.dumps({"channel": channel, "text": text}),
    )


def make_call(base, to: str, message: str, from_: Optional[str] = None) -> str:
    """Place a Twilio phone call in one call (wraps the message in TwiML).

    Use when a task says to CALL someone (e.g. SEV1 incident: "text AND call the
    on-call engineer"). This is a separate action from send_sms — do both when
    asked.

    Args:
        to: recipient phone number, verbatim from the source data (E.164).
        message: what the call should say (spoken).
        from_: optional caller number; defaults to a sandbox Twilio number.
    """
    twiml = "<Response><Say>{}</Say></Response>".format(message)
    payload = {"To": to, "From": from_ or "+15550000000", "Twiml": twiml}
    return base.fetch(
        "POST",
        "https://api.twilio.com/2010-04-01/Accounts/default/Calls.json",
        None,
        json.dumps(payload),
    )


def send_sms(base, to: str, body: str, from_: Optional[str] = None) -> str:
    """Send an SMS via Twilio in one call (handles the AccountSid + payload).

    Args:
        to: recipient phone number, verbatim from the source data (E.164).
        body: the text message body.
        from_: optional sender number; defaults to a sandbox Twilio number.
    """
    payload = {"To": to, "Body": body, "From": from_ or "+15550000000"}
    return base.fetch(
        "POST",
        "https://api.twilio.com/2010-04-01/Accounts/default/Messages.json",
        None,
        json.dumps(payload),
    )


LAYER_TOOLS = [api_search, api_fetch, base64_encode, sheet_read,
               gmail_read, gmail_send, slack_post, send_sms, make_call]
