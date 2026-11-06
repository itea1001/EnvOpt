"""The access layer the target works through — and the thing YOU (the evolve
agent) edit. This is the deliverable.

At baseline it is exactly the raw `api` toolset: three tools that forward to the
outside unchanged, no context injected. So a target run on this baseline is
identical to a normal `auto-bench --toolset api` run.

Contract (how this package plugs into the target's run):

  LAYER_TOOLS : list[callable]
      The tools the target sees. Each tool takes `base` as its FIRST argument —
      the client to the outside (base.search / base.fetch / base.encode) — plus
      the arguments the target passes. `base` is hidden from the target's tool
      spec, exactly like the stock tools hide `world`. The tool's body runs in
      the container; it reaches the world only via `base`.

  inject_context(state, base)    [OPTIONAL — absent at baseline]
      Called once at task start, before the target acts. May pre-fetch the world
      through `base` and prepend a single system message to state["prompt"] to
      front-load a compact overview. Absent here, so the baseline injects nothing.

You may add tools, rewrite what they return, add inject_context, add helper
modules / cheatsheets — anything, as long as the tools still reach the world only
through `base`, and real writes still actually happen.
"""
from typing import Optional


def api_search(base, query: str, top_k: int = 5) -> str:
    """Search available API endpoints by keyword.

    Use this to discover which endpoint to call before using api_fetch.
    Ranks results using BM25 over endpoint descriptions and parameter text.
    Returns full endpoint details including the URL to pass to api_fetch.

    Args:
        query: Space-separated keywords (e.g. "inbox messages", "trash", "send label").
               Uses API-native terms: "messages" not "emails", "trash" not "delete".
        top_k: Maximum number of results to return (default 5).

    Returns:
        JSON with matching endpoints: id, method, url, description,
        parameters (with types/descriptions), request body, and response format.
    """
    return base.search(query, top_k)


def api_fetch(
    base,
    method: str,
    url: str,
    params: Optional[str] = None,
    body: Optional[str] = None,
) -> str:
    """
    Call an API endpoint by its full URL, routing to the appropriate world state mutation.

    Use api_search first to discover the correct URL and parameters for an endpoint.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        url: Full API URL from api_search results (e.g., "https://api.hubapi.com/crm/v3/objects/contacts").
        params: Query parameters as a JSON string (e.g., '{"labelIds": "INBOX"}').
        body: Request body as a JSON string (e.g., '{"subject": "Hi", "body": "Hello"}').

    Returns:
        JSON string mimicking the real API response.
    """
    return base.fetch(method, url, params, body)


def base64_encode(base, text: str) -> str:
    """Encode text to base64url — the format Gmail API body fields require.

    The Gmail messages.send / drafts endpoints accept the message body only in
    base64url form: either ``raw`` (the full RFC 2822 message, base64url-encoded)
    or ``payload.body.data`` (the body text, base64url-encoded). Use this tool to
    produce that encoding, then pass the result to api_fetch. This is a local
    helper — it does not call any API endpoint.

    Args:
        text: Plaintext to encode (an email body, or a full RFC 2822 message).

    Returns:
        The base64url-encoded string.
    """
    return base.encode(text)


LAYER_TOOLS = [api_search, api_fetch, base64_encode]
