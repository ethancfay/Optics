![Optics: Research Gap Index](docs/banner.png)

# Optics

Compares how common selected diseases are among Massachusetts adults (18+) with observed MA-associated clinical study activity. It measures study activity against adult prevalence, not disease severity.

Not medical advice. Index, not prediction.

**Live demo:** https://research-gap-index-web.vercel.app/

Built for **Hackachusetts 2026**, healthcare track.

![WHAT page: index range per disease](docs/screenshot-what.png)

## What it does
- Shows which conditions have the least study activity compared with how many MA adults have them
- Currently covers asthma, diabetes, and high cholesterol
- Lets users see the evidence and sources behind each score

## Who it helps
Researchers, funders, and public health teams looking for conditions that are under-studied relative to how many people they affect.

## Key finding
Among the three diseases, high cholesterol has the lowest research activity for how common it is: about **0.25** recruiting MA studies per 100,000 affected adults, compared with 1.22 for asthma and 11.02 for diabetes.

## How it works
ClinicalTrials.gov + CDC PLACES → Python pipeline (fetch, match conditions, score) → static JSON → React dashboard on Vercel.

Index = recruiting MA studies ÷ MA adults with the disease × 100,000. Each score is shown as a range (low–high) using CDC's prevalence confidence limits, not a single point.

## Tech stack
Python · pytest · React · TypeScript · Vite · Vitest · fast-check · d3-geo · Vercel · Kiro

## Results
- 4 specs, built by 4 people in parallel on separate branches
- 350+ tests on the scoring export, plus property-based tests on the dashboard
- Every number links back to its ClinicalTrials.gov record

## Technical challenges
- **Probing APIs before designing:** we ran 10 read-only API probes first. One showed the server-side date filter worked, which changed the design from one query to two before any code was written.
- **Cross-platform tests:** on Windows, Python's `socketpair()` falls back to loopback TCP, which our network-blocking test fixture flagged as an outbound request. We added a narrow `allow_loopback` marker instead of skipping the tests.
- **Accessible design:** all text passes WCAG AA contrast, and charts never rely on color alone.

## Team
- **Ethan Au-Yeung:** dashboard spec and website, scoring export (Spec 3), documentation
- **Justin Fung:** data pipeline spec
- **Samantha Lau:** shaped the core idea; as a biology major, she guided how we framed the health question and taught the team how to approach the clinical research data
- **Ashley Lau:** designed and built the website's UI

## Data sources
- [ClinicalTrials.gov (NIH)](https://clinicaltrials.gov/): study activity
- [CDC PLACES](https://www.cdc.gov/places/): adult disease prevalence

## Project structure
- `pipeline/`: Python data pipeline and scoring
- `web/`: dashboard website
- `web/public/data/`: exported JSON the site reads
- `.kiro/`: specs, steering docs, hooks, and agent config

## Run it locally

**1. Generate the data**
```bash
python3 -m pipeline.scoring.export
```
This writes `what.json`, `investigate.json`, `evidence.json`, and `sources.json` to `web/public/data/`.

**2. Run the website**
```bash
cd web
npm install
npm run dev
```
Open the local link it prints.

**3. Run the tests**
```bash
python3 -m pytest
cd web && npm test
```

## How we used Kiro
See [KIRO_USAGE.md](KIRO_USAGE.md) for the full write-up, plus `.kiro/` and `KIRO_LOG.md`.

## License
MIT. See [LICENSE](LICENSE).
