---
name: research-gap-data
version: 0.1.0
description: >-
  Answer questions about ClinicalTrials.gov clinical studies and CDC PLACES
  adult (18+) prevalence for Massachusetts, using a domain-restricted fetch
  tool. Use when a request involves looking up trial records, study counts,
  statuses, phases, or interventions on ClinicalTrials.gov, or disease
  prevalence / measure definitions on CDC PLACES, for the Research Gap Index.
keywords:
  - clinicaltrials.gov
  - clinical trials
  - CDC PLACES
  - prevalence
  - Massachusetts
  - research gap index
  - disease burden
  - NCT
---

# Research Gap Data

A project power for the **Research Gap Index**. It bundles a network `fetch`
tool restricted to the project's two allowed public sources and the steering
that governs how their data may be read, counted, and described.

## When to use this power

Activate it when a request is about either of the project's two data sources:

- **ClinicalTrials.gov** — looking up study (NCT) records, recruiting status,
  study type, phases, interventions, or Massachusetts-associated study counts.
- **CDC PLACES** — adult (18+) crude-prevalence measures, measure definitions,
  county values, or the measure IDs behind the project's diseases (e.g.
  CASTHMA, HIGHCHOL, BPHIGH, DIABETES, DEPRESSION).

Do **not** use it for general web lookups. The fetch tool only reaches
`clinicaltrials.gov` and `cdc.gov` (including `data.cdc.gov`); every other host
is blocked before the request is made.

## What it provides

- **MCP server `fetch`** (`uvx mcp-server-fetch`) for retrieving pages and JSON
  from the two allowed sources. See `mcp.json`.
- **A domain allowlist guard** (`scripts/allow_fetch_domains.py`) that fails any
  fetch to a host other than `clinicaltrials.gov` or `cdc.gov`. It is a copy of
  the project's `.kiro/hooks/allow_fetch_domains.py`; wire it in as a
  `PreToolUse` hook on the `fetch` tool to enforce the limit (the MCP server has
  no built-in allowlist). Steps are in `steering/research-gap-data.md`.
- **Steering** (`steering/research-gap-data.md`) that points at the project's
  authoritative `data-contract` and `health-safety` rules and summarizes the
  non-negotiables (no contact data, index not prediction, numbers must trace to
  source, prevalence is adults 18+).

## Hard rules (summary — the steering files are authoritative)

- Only two sources, ever: `clinicaltrials.gov` and `data.cdc.gov` (`cdc.gov`).
- Never read, store, log, or display investigator/contact/official names,
  emails, or phone numbers.
- Call it an **index**, never a prediction or recommendation. Do not use
  "neglected", "underfunded", or "needs more trials".
- Every number must come from source and link to it; prevalence is adults 18+.
- No secrets in this power. Any key, if ever needed, lives in a gitignored
  `.env`, never in the power.
