# How We Used Kiro

We built Research Gap Index almost entirely through Kiro, using spec-driven development, steering docs, hooks, a custom agent, MCP, and a Power. Everything is in the `/.kiro` folder.

## Tools and setup
We used Kiro IDE as our main environment across four laptops: three Mac and one Windows. The Windows teammate handled the hooks, agent, MCP, and Power work. We also used the Kiro CLI to run the health-reviewer agent from the terminal, which showed the same agent works outside the IDE.

Windows and Mac behaved differently in one concrete way. On Windows, Python's `socket.socketpair()` falls back to a loopback TCP connection, and our test suite's network-blocking fixture treated it as an unauthorized outbound request. Instead of skipping those tests, we added a narrow `allow_loopback` pytest marker and confirmed the fix passed on both platforms before merging. The fix is in the repo and the commit history.

## Specs (spec-driven development)
We ran 4 specs, each going requirements → design → tasks in `.kiro/specs/` before any implementation code. Each spec had its own branch and owner, so teammates could work in parallel, and each was merged into main through a pull request.

**Spec 1: Data pipeline (`research-gap-data-pipeline`).** Before writing any code, Kiro ran ten read-only API probes (V1–V10, recorded in `probe_results.md`) against ClinicalTrials.gov and CDC PLACES. Probe V10 confirmed the API's server-side date filter worked, which changed the design from one query to two before any fetcher existed. We then updated the requirements to match the settled design, so we never built a fetcher that queried the wrong thing.

**Spec 2: Condition grouping (`condition-grouping`).** Groups related conditions so diseases match correctly between the two data sources.

**Spec 3: Scoring export (`scoring-export`).** Scores research gaps and exports JSON for the site. 38 tasks and 353 tests, run on real data for asthma, diabetes, and high cholesterol.

**Spec 4: Dashboard (`dashboard`).** The website that shows the gaps, built against the shared data contract.

## Steering docs
Six steering files keep Kiro consistent across all specs:
- `product.md`: what the product is and who it helps
- `tech.md`: stack and tools
- `structure.md`: folder layout
- `data-contract.md`: the JSON format shared between the pipeline and the website
- `health-safety.md`: rules for presenting health data responsibly
- `visual-design.md`: UI style rules

`data-contract.md` mattered most. It let the pipeline team and the dashboard team build at the same time without breaking each other.

## Agent hooks
- **pytest-on-save**: runs Python tests whenever pipeline code changes
- **vitest-on-save**: runs frontend tests whenever dashboard code changes
- **stop-guard-and-log**: checks work and logs it to `KIRO_LOG.md` when an agent finishes
- **fetch-domain-allowlist**: only lets Kiro fetch data from approved sources

## Custom agent
- **health-reviewer**: reviews output for health-safety issues before it ships. Runs in the IDE and from the Kiro CLI.

## MCP and Powers
- MCP server configured in `.kiro/settings/mcp.json`
- **research-gap-data** Power bundles our data steering, skill, MCP config, and domain allowlist so the setup can be reused

## Testing
353 tests on the scoring export alone, plus property-based tests with fast-check on the dashboard. Tests run automatically through hooks, and the full suite passes on both Mac and Windows.

## Other tools
We used Kombai only for final UI polish (spacing and colors), after Kiro finished the dashboard tasks. Each use is noted in `KIRO_LOG.md`.

## What worked best
Specs plus a shared data contract let 4 people build in parallel without breaking each other's code. Probing the APIs before designing meant our data pipeline was built on facts, not guesses.