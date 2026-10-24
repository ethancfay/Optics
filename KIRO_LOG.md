# Kiro Log

| Time | Who | Kiro feature | What happened | Commit |
| --- | --- | --- | --- | --- |
| 15:58 | Ethan | Spec (dashboard) | Kiro generated requirements.md from the dashboard prompt. Reviewed and edited it: added ma_counties.geojson (Req 1.2, 1.7, 2.8) so the county map has bundled shapes, and allowed outbound source links. Approved and asked Kiro to generate design. | |
| 2026-10-24T16:58Z | Kiro | Spec task execution | Task 2 scaffold. Only Python 3.14.7 is installed locally, so the < 3.11 rejection (Req 14.2) is tested by faking `sys.version_info` in a subprocess with an audit hook that records any file/socket/import event. Network block records attempts and fails the test at teardown even if code swallows the error (Req 13.6). Pins: pytest==9.1.1, hypothesis==6.170.9. | task 2 |
| 17:29 | Ethan | Spec task execution | Kiro ran tasks 5.1/5.3/5.5/5.7 in parallel; 5.1 and 5.3 raced on conditions.ts and sortConditions was lost. Kiro detected it by re-reading the file and re-dispatched 5.1 to restore it; tsc passes. | |
| 18:11 | Ethan | Spec task execution | Kiro finished all 55 dashboard tasks incl. optional property tests: 102 tests passing in 21 files, tsc and vite build clean. Kiro unblocked its own scheduler by dispatching optional tests directly and cleared checkpoints 6, 11, 15 after verifying build + suite. | |
| 18:33 | Ethan | Review | Live check found WHERE map rendering as one rectangle: Kiro-generated sample ma_counties.geojson used placeholder boxes wound counter-clockwise (d3-geo treats that as the whole globe). Replaced with real MA county shapes from us-atlas (Census-derived, 14 counties, 10.7 KB). | |
| 18:37 | Ethan | Property-based tests | Property 8 (source links) found a counterexample: two sources named "A". Kiro fixed the generator (fc.uniqueArray by name) and also found a second flaky case (fc.date producing Invalid Date) and added noInvalidDate. 102/102 tests pass, stable across runs. | |
