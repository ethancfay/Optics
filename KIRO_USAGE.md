# How We Used Kiro

We built Research Gap Index almost entirely through Kiro, using spec-driven development, steering docs, hooks, a custom agent, MCP, and a Power. Everything is in the `/.kiro` folder.

## Specs (spec-driven development)
We split the project into 4 specs, one branch and one owner each, so teammates could work in parallel on separate laptops:
- **research-gap-data-pipeline**: pulls and cleans public study data
- **condition-grouping**: groups related conditions so diseases match correctly
- **scoring-export**: scores research gaps and exports JSON for the site (38 tasks, 353 tests)
- **dashboard**: the website that shows the gaps

Each spec went requirements → design → tasks, and Kiro carried out the tasks one by one. We merged each spec branch into main through pull requests.

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
- **health-reviewer**: reviews output for health-safety issues before it ships

## MCP and Powers
- MCP server configured in `.kiro/settings/mcp.json`
- **research-gap-data** Power bundles our data steering, skill, MCP config, and domain allowlist so the setup can be reused

## Testing
353 tests on the scoring export alone, run automatically through hooks.

## Other tools
We used Kombai only for final UI polish (spacing and colors), after Kiro finished the dashboard tasks. Each use is noted in `KIRO_LOG.md`.

## What worked best
Specs plus a shared data contract let 4 people build in parallel without breaking each other's code.