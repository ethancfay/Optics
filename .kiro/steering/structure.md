# Project Structure

## Layout

```
.kiro/
  steering/           # product, tech, structure, health-safety (always committed)
  specs/
    research-gap-data-pipeline/   # Spec 1: requirements.md, design.md, tasks.md
    condition-grouping/           # Spec 2 (planned)
    scoring-export/               # Spec 3 (planned)
    dashboard/                    # Spec 4 (planned)
  hooks/              # agent hooks (*.json)
  agents/             # custom agents (e.g. health-reviewer)
  settings/           # mcp.json

pipeline/
  data/         # HTTP_Client, CTGov_Fetcher, PLACES_Fetcher, Contact_Scrubber, Raw_Store
  transform/    # Study_Transformer, PLACES_Transformer, PII_Guard, Sanity_Checker
  io/           # CSV_Writer, CSV_Reader, Fetch_Log_Writer
  mapping/      # Spec 2: MeSH/condition text -> PLACES measure grouping, recall check
  scoring/      # Spec 3: sites per 100k affected adults, distance to nearest site
  export.py     # Spec 3: writes web/public/data/*.json
  errors.py     # PipelineError, shared by data/, transform/, io/
  patterns.py   # Email_Pattern, Phone_Pattern (Contact_Scrubber, PII_Guard)
  __main__.py   # entry point: python -m pipeline [--offline]
  raw/          # cached raw API pages (scrubbed). Gitignored.
  processed/    # studies.csv, sites.csv, places_ma.csv, fetch_log.json

web/            # Spec 4: Vite + React static site, deployed on Vercel
  public/data/  # what.json, where.json, sources.json (generated, committed)

tests/          # pytest + Hypothesis; mirrors pipeline/ folders; no network

requirements.txt
KIRO_LOG.md     # log of Kiro features used, decisions, what worked
README.md
.gitignore      # excludes .env, pipeline/raw/, __pycache__/, .venv/, node_modules/. NEVER .kiro/
```

## Components

Use the glossary names from the pipeline requirements in code and docs:

- `HTTP_Client`: HTTP requests, 60 s timeout, retry policy.
- `CTGov_Fetcher` / `PLACES_Fetcher`: paginated fetching and URL recording.
- `Contact_Scrubber`: strips contact structures before any storage or use, and counts removals.
- `Raw_Store`: reads and writes per-page raw files plus saved Fetch_Date and URLs in `pipeline/raw/`.
- `Study_Transformer`: builds study rows and site rows.
- `PLACES_Transformer`: builds county-measure rows.
- `PII_Guard`: checks email and phone patterns on final string values before any write.
- `CSV_Writer` / `CSV_Reader`: deterministic CSV writing and round-trip reading.
- `Sanity_Checker`: count warnings (fewer than 2,000 MA studies; county count not 14).
- `Fetch_Log_Writer`: writes `fetch_log.json`.

## Data flow

fetch → scrub → raw store → transform → PII guard → sanity check → write CSVs → write fetch log
→ (Spec 2) group conditions → (Spec 3) score + export JSON → (Spec 4) website

Contact data must be removed at the scrub step, before raw storage. The PII guard runs before any file in `pipeline/processed/` is touched.

## Working with specs

- One spec per component, one owner and one git branch per spec (`spec/<name>`), merged by pull request.
- Read the spec's `requirements.md` before changing behavior, and cite requirement numbers (e.g. "Req 5.3") in design notes, tests and commit messages.
- If code needs to differ from the requirements, update the spec first.
- After each completed task: commit with the task number, and add a line to `KIRO_LOG.md` if anything notable happened.