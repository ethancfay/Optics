# Rules_Config for condition grouping (Spec 2, Requirement 2).
#
# Plain data only: no import statement and no logic (Req 2.11). Edit the term
# lists here to change matching; logic code reads nothing else (Req 2.1).
#
# - "include" is a list of terms.
# - "exclude" and "questionable" are lists of (term, reason) tuples.
# - Terms are compared as Normalized_Text (case folded, whitespace collapsed).
#   MeSH and ancestor values use Exact_Match, condition text uses Phrase_Match.
# - A concept with a MeSH descriptor is listed in its MeSH_Form and at least one
#   Free_Text_Form when the two differ as Normalized_Text (Req 2.10). When they
#   are the same (for example "Asthma" / "asthma"), the term is listed once
#   (Open Item 14), because a duplicated Normalized_Text is a config error
#   (Req 2.6).
# - The lists come from .kiro/specs/condition-grouping/term_audit.md together
#   with burden_test/inclusion_rules.md (Req 14.8, 14.9). Questionable terms
#   wait for the bio teammate's review (Open Item 13). Audit values marked
#   not_disease are deliberately absent.
# - Reserved reason codes (child_only, unparseable_age, healthy_volunteers_only,
#   ancestor_only) must not be used here (Req 2.5).

SAMPLE_SEED = 20261024

DISEASES = [
    {
        "measureid": "CASTHMA",
        "disease_label": "Asthma",
        "ancestor_only_status": "included",
        "recall_query_term": "Asthma",
        # Child-only studies are excluded by the age rule (Req 5), not by a term.
        "include": [
            # MeSH descriptors and their free-text forms
            "Asthma",
            "Asthma, Aspirin-Induced",
            "aspirin-induced asthma",
            "Asthma, Exercise-Induced",
            "exercise-induced asthma",
            "Asthma, Occupational",
            "occupational asthma",
            "Status Asthmaticus",
            # Term_Audit condition values
            "Severe Asthma",
            "Eosinophilic Asthma",
            "Asthma Attack",
            "Moderate to Severe Asthma",
            "Aspirin-Sensitive Asthma With Nasal Polyps",
            "Asthma Chronic",
            "Asthma Exacerbations",
            "Asthma Moderate Persistent With Exacerbation",
            "Asthma Severe Persistent With Exacerbation",
            "Asthma, Allergic",
            "allergic asthma",
            "Asthma; Eosinophilic",
            "Mild to Moderate Asthma",
            "Moderate Asthma",
            "Moderate to Severe Persistent Asthma",
            "Participants With Mild Asthma",
        ],
        "exclude": [],
        "questionable": [
            ("Asthma in Children", "pediatric_label"),
            ("Pediatric Asthma", "pediatric_label"),
            ("Childhood Asthma", "pediatric_label"),
            ("Asthma Childhood", "pediatric_label"),
            ("Asthma COPD", "overlap_syndrome"),
            ("Asthma-Chronic Obstructive Pulmonary Disease Overlap Syndrome", "overlap_syndrome"),
        ],
    },
    {
        "measureid": "DIABETES",
        "disease_label": "Diabetes",
        "ancestor_only_status": "questionable",
        "recall_query_term": "Diabetes",
        "include": [
            # MeSH descriptors
            "Diabetes Mellitus",
            "Diabetes Mellitus, Type 1",
            "Diabetes Mellitus, Type 2",
            "Latent Autoimmune Diabetes in Adults",
            # Free-text forms
            "diabetes",
            "type 1 diabetes",
            "type 2 diabetes",
            "latent autoimmune diabetes",
            # Term_Audit condition values
            "Type 2 Diabetes Mellitus",
            "Type 1 Diabetes Mellitus",
            "Type 1 Diabetes (T1D)",
            "Diabetes Type 2",
            "Type1diabetes",
            "Type2 Diabetes",
            "Type2Diabetes",
            "Autoimmune Diabetes",
            "Diabetes type1",
            "Type 2 Diabetes Treated With Insulin",
            "Diabetes Mellitus Type 2",
            "Diabetes Mellitus, Type I",
            "Diabetes Mellitus, Insulin-Dependent",
            "Diabetes, Autoimmune",
        ],
        "exclude": [
            ("Diabetes, Gestational", "gestational"),
            ("gestational diabetes", "gestational"),
            ("Gestational Diabetes Mellitus (GDM)", "gestational"),
            ("Prediabetic State", "prediabetes"),
            ("prediabetes", "prediabetes"),
            # MeSH_Form and Free_Text_Form share one Normalized_Text (Open Item 14)
            ("Diabetes Insipidus", "not_mellitus"),
            ("Diabetes Insipidus, Neurogenic", "not_mellitus"),
            ("neurogenic diabetes insipidus", "not_mellitus"),
            ("central diabetes insipidus", "not_mellitus"),
            ("Diabetes Insipidus, Nephrogenic", "not_mellitus"),
            ("nephrogenic diabetes insipidus", "not_mellitus"),
        ],
        # Complications count only when diabetes is a listed condition
        # (inclusion_rules.md), so alone they are questionable.
        "questionable": [
            ("Diabetic Retinopathy", "complication_only"),
            ("Diabetic Foot", "complication_only"),
            ("Diabetic Nephropathies", "complication_only"),
            ("Diabetic Neuropathies", "complication_only"),
            ("Diabetes Complications", "complication_only"),
            ("Diabetic Ketoacidosis", "complication_only"),
            ("Diabetic Cardiomyopathies", "complication_only"),
            ("Diabetic Angiopathies", "complication_only"),
            ("Diabetic Macular Edema", "complication_only"),
            ("Diabetic Macular Edema (DME)", "complication_only"),
            ("Diabetic Peripheral Neuropathic Pain", "complication_only"),
            ("Diabetic Foot Ulcer", "complication_only"),
            ("Diabetic Foot Ulcers", "complication_only"),
            ("Diabetic Foot Ulcer (DFU)", "complication_only"),
            ("Painful Diabetic Neuropathy", "complication_only"),
            ("Diabetic Neuropathy, Painful", "complication_only"),
            ("Diabetic Gastroparesis", "complication_only"),
            ("Diabetic Peripheral Neuropathy", "complication_only"),
            ("Diabetic Kidney Disease", "complication_only"),
            ("Diabetic Kidney Disease (DKD)", "complication_only"),
            ("Diabetes Mellitus, Insulin-Dependent, 12", "monogenic_or_rare"),
            ("Noninsulin-dependent diabetes mellitus with deafness", "monogenic_or_rare"),
            ("Pregnancy in Diabetics", "pregnancy_population"),
            ("Cystic Fibrosis-related Diabetes", "secondary_cause"),
            ("Cystic Fibrosis Related Diabetes", "secondary_cause"),
        ],
    },
    {
        "measureid": "HIGHCHOL",
        "disease_label": "High cholesterol",
        "ancestor_only_status": "questionable",
        "recall_query_term": "High Cholesterol",
        "include": [
            # MeSH descriptors (MeSH_Form = Free_Text_Form listed once)
            "Hypercholesterolemia",
            "Homozygous Familial Hypercholesterolemia",
            "Hyperlipidemias",
            "Dyslipidemias",
            "Hyperlipoproteinemias",
            "Hyperlipoproteinemia Type II",
            "Hyperlipidemia, Familial Combined",
            # Free-text forms
            "hyperlipidemia",
            "dyslipidemia",
            "hyperlipoproteinemia",
            "familial hypercholesterolemia",
            "familial combined hyperlipidemia",
            "high cholesterol",
            # Elevated LDL and Lp(a) (inclusion_rules.md). The bare values
            # "Lipoprotein(a)" and "Lipoproteins" are questionable lab values.
            "elevated ldl",
            "high ldl",
            "elevated lipoprotein(a)",
            "elevated lp(a)",
            # Term_Audit condition values
            "Hypercholesterolaemia",
            "Familial Hypercholesterolaemia",
            "Heterozygous Familial Hypercholesterolemia",
            "Heterozygous Familial Hypercholesterolemia (HeFH)",
            "Cholesterol, Elevated",
            "Elevated Cholesterol",
            "High Cholesterol/Hyperlipidemia",
            "Hyperlipidaemia",
            "Mixed Dyslipidemia",
        ],
        # ASCVD / myocardial infarction alone are counted under coronary heart
        # disease, not high cholesterol (Open Item 3).
        "exclude": [
            ("Myocardial Infarction", "ascvd_only"),
            ("heart attack", "ascvd_only"),
            ("Coronary Artery Disease", "ascvd_only"),
            ("Coronary Disease", "ascvd_only"),
            ("coronary heart disease", "ascvd_only"),
            ("Atherosclerosis", "ascvd_only"),
            ("atherosclerotic cardiovascular disease", "ascvd_only"),
            ("ASCVD", "ascvd_only"),
        ],
        "questionable": [
            ("Cholesterol", "lab_value_only"),
            ("HDL Cholesterol", "lab_value_only"),
            ("Lipoprotein(a)", "lab_value_only"),
            ("Cardiovascular Disease and Lipoprotein(a)", "lab_value_only"),
            ("Lipoproteins", "lab_value_only"),
            ("Lipid Metabolism Disorders", "broad_category"),
            ("Lipid Metabolism Disorder", "broad_category"),
            ("Lipid Disorders", "broad_category"),
            ("Lipoprotein Disorder", "broad_category"),
            ("Cholesterol Ester Storage Disease", "monogenic_or_rare"),
            ("Lipid Metabolism, Inborn Errors", "monogenic_or_rare"),
            ("Hyperlipoproteinemia Type V", "triglyceride_predominant"),
        ],
    },
]
