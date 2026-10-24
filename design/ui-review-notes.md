UI redesign: review notes and Kiro handoff (2026-10-24)
Tags: [facts] = checked against the live site/JSON today, [interpretation] = judgment.

What the live site does today
Nav: Home, WHAT, Method, Build. Investigate and Evidence are only reachable from WHAT (/investigate/:id, /evidence/:id). [facts]
The WHAT comparison chart is NOT missing: one SVG bar chart with ranges renders above a data table. The problem is presentation (small, no direct labels, table dominates), not a broken component. [facts for presence; interpretation for the diagnosis]
Investigate is four plain tables (status, type, intervention, phase) plus findings. [facts]
sources.json is_sample is now false, data_as_of 2026-10-24. The older open-issues note about is_sample: true is out of date. [facts]
Data checks run on production JSON
All Investigate counts (status, type, phase, intervention) match counts derived from evidence.json records exactly, for all three conditions. Evidence filters can therefore be computed client-side with no backend change. [facts]
Status and study-type counts sum to ma_studies. Phase counts overlap for Diabetes (8 multi-phase studies, bars total 264 for 256 studies). [facts]
Intervention-type counts are distinct studies per type and overlap; 5 asthma and 15 diabetes records list no intervention, and Investigate has no bar for them. [facts]
us_studies is null for every condition. [facts]
No sponsor, site, location or eligibility field in any export, so the brief's "no sponsor filter" rule is enforced by the data anyway. [facts]
Issues the brief did not mention
Two recruiting numbers: WHAT t (8 / 61 / 5) vs Investigate overall-status Recruiting (11 / 70 / 5). The Method page's filter list ("lists a Massachusetts recruiting location") suggests t uses site-level status. [facts for numbers; interpretation for the cause, confirm with Ethan]
Traceability gap: Evidence cannot show "the 8 studies behind the index" because no field marks them. The brief's "Traceability" principle cannot be fully met without a backend field. I wrote it as decision D2 rather than assuming. [facts for the gap; interpretation for the options]
Chart scale: mids are 0.25, 1.22, 11.02 (about 44x spread). On a linear zero-based axis the High Cholesterol bar is about 2% of the width. The brief bans truncated axes, so the file keeps linear and relies on outside labels. A log axis would show all three bars but is harder for judges to read. [facts for values; interpretation for the trade-off]
The headline finding is partly a rule artefact: High Cholesterol is lowest partly because heart-disease-only trials are excluded, and Asthma/High Cholesterol rest on 8 and 5 studies. The file makes both caveats mandatory next to the chart. Without them, a judge can fairly call the main result fragile. [interpretation]
Count-up number animations are common in dashboard Figma kits and would display values that are not in the data. Banned in 8.4. [interpretation]
Where I disagree with the brief
Writing the Kiro spec (requirements/design/tasks) myself would weaken "Best Use of Kiro": the rules say Kiro evidence must come from real Kiro sessions. I wrote only the steering file; Kiro should generate the spec from it. [interpretation]
"Retain four pages" vs current Home/Build: Build likely holds your Kiro write-up and should stay reachable. Logged as D5. [interpretation]
How to use these files
Answer D1–D6 in ui-presentation.md section 11, then save it as .kiro/steering/ui-presentation.md.
In Kiro, start a new spec named frontend-redesign with this prompt:
Create a spec for the frontend redesign described in .kiro/steering/ui-presentation.md. Do not modify the pipeline, scoring, exports or the four existing specs. First task: audit the existing React components, routes and the four JSON files, and report which components can be reused and whether the WHAT chart can render low–high ranges. Turn section 10 into requirements with EARS acceptance criteria and tasks with tests. Flag any requirement that needs a field not present in the JSON instead of inventing it.

Log the session in KIRO_LOG.md (spec generated from steering, audit results).