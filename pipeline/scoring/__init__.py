"""Scoring & Export stage (Spec 3).

Reads the processed CSVs from Spec 1 (`studies.csv`, `sites.csv`,
`places_ma.csv`, `fetch_log.json`) and the disease-to-measure matches from
Spec 2 (`study_diseases.csv`), computes the per-disease burden-versus-activity
index and activity decomposition, and writes the four dashboard JSON files
(`what.json`, `investigate.json`, `evidence.json`, `sources.json`) to
`web/public/data/`. The stage is local and offline, deterministic, and writes
atomically. The entry point is `python -m pipeline.scoring.export`.
"""
