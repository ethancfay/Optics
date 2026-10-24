# Condition inclusion rules (Spec 2 input)

Principle: a study counts for a disease only if its participants match what the
CDC PLACES measure counts (BRFSS: adults 18+ ever told by a health professional
they have the condition). Approved by team 2026-10-24.

| Disease | PLACES measureid | Include | Exclude |
|---|---|---|---|
| Diabetes | DIABETES | Type 1, type 2, unspecified diabetes; diabetic complications when diabetes is a listed condition | Gestational diabetes, prediabetes |
| High blood pressure | BPHIGH | Essential/primary hypertension, resistant hypertension | Pulmonary, portal, intracranial, ocular hypertension; preeclampsia / pregnancy-only hypertension |
| High cholesterol | HIGHCHOL | Hypercholesterolemia, hyperlipidemia, dyslipidemia, familial hypercholesterolemia, elevated LDL or Lp(a) | Studies tagged only ASCVD / myocardial infarction (counted under coronary heart disease) |
| Asthma | CASTHMA | Asthma in adults or all ages | Child-only studies (maximumAge < 18 years) |
| Depression | DEPRESSION | Major depressive disorder, treatment-resistant depression, dysthymia, postpartum depression, depressive symptoms as primary condition | Bipolar disorder incl. bipolar depression; depression only as a secondary outcome |

## General rules
- A study counts for a disease if ANY listed condition matches (many-to-many allowed).
  Per-disease totals = distinct NCT IDs.
- Studies with healthyVolunteers = true and no matching patient condition do not count.
- Child-only studies (maximumAge < 18) do not count for any disease (PLACES is adults only).
- Unclear matches are marked "questionable" and reported separately, never silently counted.

## Validation
- Recall: per disease, our count of matching studies must be >= 80% of
  ClinicalTrials.gov's own query.cond count under the same filters.
- Precision: 20 assigned studies per disease are hand-checked by the bio teammate.