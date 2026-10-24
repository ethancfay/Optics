---
inclusion: always
---
# Health safety rules

## Data
- Public data only: ClinicalTrials.gov and CDC PLACES. No real patient data, no synthetic patient records, no user health data collected.
- Never read, store, log or display investigator, contact or official names, emails or phone numbers.
- Never commit secrets. Keys, if any, go in `.env` only (gitignored).

## Claims
- No diagnosis, treatment, eligibility or "you should join this trial" language anywhere.
- Call it an index, never a prediction or a recommendation.
- Always state the limit: compares trial opportunity with how common a condition is, not how severe it is.
- Never invent numbers. Every number shown must come from pipeline output and link to its source.
- Prevalence is for adults 18+ (CDC PLACES); say so wherever affected adults are shown.

## Presentation
- Show low-high ranges, never a bare single-number ranking.
- Footer on every page: "Not medical advice. Index, not prediction." with source links and a "Data as of" date.
- Cancer is shown separately so it does not swamp the scale.
- Plain language (aim for grade 8 reading level). Define any term like "interventional" or "prevalence" in one short phrase.

## Accessibility
- WCAG AA contrast, colour-blind-safe palette, keyboard navigable, visible focus.
- Every chart and map has a text alternative (table or summary sentence) for screen readers.

## When unsure
- If a change could imply medical advice or expose personal data, stop and ask instead of guessing.