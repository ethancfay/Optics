---
inclusion: always
---
# Research Gap Data — working rules

This steering governs any use of the `fetch` tool bundled with this power. The
**authoritative** rules live in the project's own steering; read them before
acting and treat them as the source of truth:

- `.kiro/steering/data-contract.md` — definitions (MA study, eligibility, T, N,
  prevalence fractions, low/mid/high) and the exact JSON the dashboard reads.
- `.kiro/steering/health-safety.md` — data, claims, presentation, and "when
  unsure" rules.
- `.kiro/steering/product.md` — scope, counting rules, and non-goals.

If this power is installed in a workspace that does not contain those files,
ask the user for them rather than guessing.

## Allowed sources (hard limit)

The `fetch` tool may only reach:

- `clinicaltrials.gov` — the ClinicalTrials.gov v2 API and study pages.
- `data.cdc.gov` and other `cdc.gov` hosts — CDC PLACES data and measure
  definitions.

Every other host is out of scope. `mcp-server-fetch` has no built-in allowlist,
so enforce the limit with the bundled guard as a PreToolUse hook.

### Wiring the domain guard

`scripts/allow_fetch_domains.py` reads the tool payload on stdin, extracts the
`url`, and exits `2` (block) for any host that is not `clinicaltrials.gov` or
`cdc.gov`, for raw IPs, and for non-http(s) schemes; it exits `0` otherwise.
Add a hook like this (adjust the path to where the power is installed):

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "Restrict fetch to allowed sources",
      "trigger": "PreToolUse",
      "matcher": "fetch",
      "action": {
        "type": "command",
        "command": "python3 \"<power-dir>/scripts/allow_fetch_domains.py\""
      }
    }
  ]
}
```

Note: the matcher `fetch` is a substring match on the tool name, so it also
matches a built-in `web_fetch` tool if one exists. That is intentional here —
it keeps all fetches on the allowlist — but narrow the matcher if you only want
to guard the MCP server.

## How to read and report data

- **Numbers trace to source.** Every count, prevalence, or score you report
  must come from a fetched source and be linked to it. Never invent or
  hardcode a number.
- **Prevalence is adults 18+** (CDC PLACES crude prevalence). Say "adults 18+"
  wherever affected-adult figures appear, with the measure's data year.
- **Counting.** A study count is distinct `nctId`; sites never count as
  studies; unknown site status is never treated as recruiting. See
  data-contract.md for T, N, and the low/mid/high formulas.
- **Show ranges, not bare rankings.** Present a low-high range, not a single
  number, for any ranked/scored value shown to a user.

## Never do

- Never read, store, log, or display investigator, contact, or official names,
  emails, or phone numbers. Exclude `centralContacts`, `overallOfficials`,
  `locations[].contacts`, and `responsibleParty` names. If a fetched payload
  contains such fields, do not echo them — refer to them by field name only.
- Never describe the index as a prediction, forecast, or recommendation, and
  never use "neglected", "underfunded", or "needs more trials".
- Never give diagnosis, treatment, eligibility, or "you should join this trial"
  advice.
- Never put secrets in this power or in logs. Keys, if ever needed, live in a
  gitignored `.env`.

## When unsure

If a request could imply medical advice, expose personal data, or require a
source outside the two allowed domains, stop and ask instead of guessing.
