# Workspace-Bench

Environments from our evolve run on Workspace-Bench. The fixed target agent is Codex with GPT-5.4-mini.
Each step used 20 synthetic training tasks without verifiers.

## Where the environments are

The environments are too large for GitHub (about 25 GB per step). They are hosted at
https://huggingface.co/datasets/itea1001/EnvOpt-WorkspaceBench

- `step_1/` … `step_6/`: the full environment after each step, as one archive per workspace
  (`chanpin.tar`, `kaifa.tar`, `research.tar`, `yunying.tar`, `houqin.tar`).
  Each step starts from the previous step's environment. Step 6 is our final environment.
- Baseline: the original Workspace-Bench workspaces. We do not re-upload them. Download them from
  https://huggingface.co/datasets/Workspace-Bench/Workspace-Bench-Workspaces
  or with `python3 scripts/download_hf_assets.py --workspaces` in the Workspace-Bench repo.

## How to use a step

Each archive unpacks to one folder. Use it in place of the matching Workspace-Bench folder
`evaluation/filesys/<name>_raw/`:

| Archive | Workspace-Bench folder | Role |
|---|---|---|
| `chanpin.tar` | `chanpin_raw` (`ProductManager_Workdir`) | Product Manager |
| `kaifa.tar` | `kaifa_raw` (`BackendDeveloper_Workdir`) | Backend Developer |
| `research.tar` | `research_raw` (`Research_Workdir`) | Researcher |
| `yunying.tar` | `yunying_raw` (`OperationsManager_Workdir`) | Operations Manager |
| `houqin.tar` | `houqin_raw` (`LogisticsManager_Workdir`) | Logistics Manager |

For example, for step 6:

```
tar -xf step_6/chanpin.tar && mv chanpin Workspace-Bench/evaluation/filesys/chanpin_raw
```

Then run Workspace-Bench as usual.

## What we changed

Every step only added files to the original workspaces. No original file was changed or deleted.
The added files are pre-extracted text copies of documents (`.text/`), a file catalog,
an `AGENTS.md` guide in each workspace, and small helper tools.

## License

The workspaces are from Workspace-Bench (Tang et al., 2026, https://arxiv.org/abs/2605.03596),
released under the Apache-2.0 license. Our environments are modified versions of those workspaces
and are released under the same license. If you use them, please also cite Workspace-Bench.
