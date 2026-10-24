"""Shared Hypothesis generators."""
from __future__ import annotations

from dataclasses import dataclass, field

from hypothesis import strategies as st

# Base page content uses only lowercase ASCII and digits, and keys from a fixed
# set with no contact key names. Injected contact values always contain "ZQX",
# "@" or "-", so they cannot appear in the base content by chance.
SAFE_KEYS = ["nctId", "briefTitle", "facility", "city", "state", "zip", "status",
             "protocolSection", "derivedSection", "modules", "items", "type"]
safe_text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", max_size=8)
json_scalars = st.one_of(
    st.none(), st.booleans(), st.integers(-10**6, 10**6),
    st.floats(allow_nan=False, allow_infinity=False), safe_text,
)
json_trees = st.recursive(
    json_scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.sampled_from(SAFE_KEYS), children, max_size=4),
    ),
    max_leaves=25,
)

RP_FIELDS = ["investigatorFullName", "investigatorTitle", "investigatorAffiliation", "oldNameTitle"]


@dataclass
class InjectedPage:
    page: dict
    expected: dict[str, int] = field(default_factory=dict)  # RemovalCounts attr -> count
    values: list[str] = field(default_factory=list)          # every injected contact value


def _dict_nodes(tree: object) -> list[dict]:
    nodes, stack = [], [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            nodes.append(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return nodes


@st.composite
def pages_with_contacts(draw) -> InjectedPage:
    """A CTGov-like page with contact structures injected into dicts at any depth (P6)."""
    studies = draw(st.lists(json_trees, max_size=4))
    page = {"studies": studies, "totalCount": len(studies)}
    targets = _dict_nodes(page)  # computed before injection: no nesting inside contacts
    result = InjectedPage(page=page, expected={
        "centralContacts": 0, "overallOfficials": 0,
        "locations_contacts": 0, "responsibleParty_investigator": 0,
    })
    serial = [0]

    def contact() -> dict:
        serial[0] += 1
        n = serial[0]
        person = {
            "name": "ZQX Person %d" % n,
            "email": "zqx%d@example.org" % n,
            "phone": "617-555-%04d" % n,
        }
        result.values.extend(person.values())
        return person

    ops = draw(st.lists(st.tuples(
        st.sampled_from(["central", "officials", "locations", "rp"]),
        st.integers(0, len(targets) - 1),
    ), max_size=8))
    for kind, index in ops:
        node = targets[index]
        if kind == "central" and "centralContacts" not in node:
            node["centralContacts"] = [contact() for _ in range(draw(st.integers(0, 2)))]
            result.expected["centralContacts"] += 1
        elif kind == "officials" and "overallOfficials" not in node:
            node["overallOfficials"] = [contact() for _ in range(draw(st.integers(0, 2)))]
            result.expected["overallOfficials"] += 1
        elif kind == "locations" and "locations" not in node:
            flags = draw(st.lists(st.booleans(), min_size=1, max_size=3))
            node["locations"] = [
                {"facility": "site", "contacts": [contact()]} if has else {"facility": "site"}
                for has in flags
            ]
            result.expected["locations_contacts"] += sum(flags)
        elif kind == "rp" and "responsibleParty" not in node:
            chosen = draw(st.lists(st.sampled_from(RP_FIELDS), unique=True))
            rp = {"type": "PRINCIPAL_INVESTIGATOR"}
            for name in chosen:
                rp[name] = contact()["name"]
            node["responsibleParty"] = rp
            result.expected["responsibleParty_investigator"] += len(chosen)
    return result


# --- Study_Transformer generators (P3, P4, P8) ---------------------------------

# A small nctId pool so duplicates within and across pages and queries are common.
# "" and None cover Req 4.9 (records the transformer excludes).
NCT_IDS = ["NCT00000001", "NCT00000002", "NCT00000003", "NCT00000004", "NCT00000005"]
STUDY_STATUSES = ["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED",
                  "TERMINATED", "WITHDRAWN", "recruiting", ""]
SITE_STATES = ["Massachusetts", " ma ", "Rhode Island", "NH", "connecticut", "New York",
               "VT", "California", "Ontario", "", None]
# Boundary values are listed explicitly so they are drawn often (Req 13.3).
BOUNDARY_LATS = [-90, 90, -90.0, 90.0, 0, 42.3]
BOUNDARY_LONS = [-180, 180, -180.0, 180.0, 0, -71.8]

coordinates = st.one_of(
    st.floats(allow_nan=True, allow_infinity=True),
    st.integers(-400, 400),
    st.sampled_from(BOUNDARY_LATS + BOUNDARY_LONS),
    st.sampled_from([None, True, "42.3", [], {}]),
)
geo_points = st.one_of(
    st.none(),
    st.just({}),
    st.fixed_dictionaries({"lat": st.sampled_from(BOUNDARY_LATS),
                           "lon": st.sampled_from(BOUNDARY_LONS)}),
    st.fixed_dictionaries({}, optional={"lat": coordinates, "lon": coordinates}),
)
locations = st.fixed_dictionaries({}, optional={
    "facility": st.sampled_from(["Site A", "Site B", " Site A ", ""]),
    "city": st.sampled_from(["Boston", "Worcester", ""]),
    "state": st.sampled_from(SITE_STATES),
    "zip": st.sampled_from(["02115", "01605", ""]),
    "status": st.sampled_from(["RECRUITING", "COMPLETED", "WITHDRAWN", ""]),
    "geoPoint": geo_points,
})


@st.composite
def study_records(draw) -> dict:
    """A scrubbed CTGov study record with zero, one or many sites."""
    ident = {}
    nct_id = draw(st.sampled_from(NCT_IDS + ["", None]))
    if nct_id is not None:
        ident["nctId"] = nct_id
    status_module = {
        "overallStatus": draw(st.sampled_from(STUDY_STATUSES)),
        "lastUpdatePostDateStruct": {
            "date": draw(st.sampled_from(["2026-01-01", "2023-10-24", "2023-10-23",
                                          "2020-05-05", "2025-02-30", "bad"]))},
    }
    return {"protocolSection": {
        "identificationModule": ident,
        "statusModule": status_module,
        "designModule": {"studyType": draw(st.sampled_from(["INTERVENTIONAL",
                                                            "OBSERVATIONAL", ""]))},
        "contactsLocationsModule": {"locations": draw(st.lists(locations, max_size=4))},
    }}


@st.composite
def ctgov_query_pages(draw) -> list[dict]:
    """Q1 pages followed by Q2 pages, as the transformer receives them."""
    page = st.builds(lambda s: {"studies": s}, st.lists(study_records(), max_size=5))
    q1 = draw(st.lists(page, min_size=1, max_size=3))
    q2 = draw(st.lists(page, min_size=1, max_size=3))
    return q1 + q2

# --- CSV round-trip generators (P5, Req 7.7, 13.4) ------------------------------
# Tricky fragments are sampled often; general text excludes surrogates (Cs),
# which cannot be encoded as UTF-8 and so are not valid row values.
CSV_TRICKY = ["", "|", "\\", "[", "]", "[]", '["a","b"]', '[""]', ",", '"', '""',
              "\r", "\n", "\r\n", "é", "Ünïcödé", "日本語", "😀", "a,b", 'say "hi"',
              "\\n", "null", " ", "\u2028", "\x00"]
csv_text = st.one_of(
    st.sampled_from(CSV_TRICKY),
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=12),
    st.lists(st.sampled_from(CSV_TRICKY), max_size=4).map("".join),
)
csv_lists = st.lists(csv_text, max_size=4)


def _rows_of(row_type, list_fields: frozenset[str]):
    from dataclasses import fields as dc_fields
    return st.builds(row_type, **{
        f.name: (csv_lists if f.name in list_fields else csv_text)
        for f in dc_fields(row_type)
    })


def csv_rows(kind: str):
    """Rows of one table kind with tricky strings in every field."""
    from pipeline.io.csv_writer import LIST_COLUMNS, ROW_TYPES
    return st.lists(_rows_of(ROW_TYPES[kind], LIST_COLUMNS[kind]), max_size=6)

# --- Scoring input generators (Spec 3, P1-P5; Req 9.1-9.5) ----------------------
# These build the four inputs the Scoring_Exporter consumes: Spec 1 StudyRow /
# SiteRow / PlacesRow and the Spec 2 DiseaseMatch. Everything is drawn from a
# small shared nctId pool so duplicate study rows, several MA sites per study,
# and many-to-many (nctId, measureid) matches are all common (Req 9.4). Only
# lowercase/safe text and plain non-PII values are generated, so output strings
# can never match the email or phone pattern by chance (Req 9.5).

from pipeline.scoring.models import DiseaseMatch  # noqa: E402
from pipeline.transform.places_transformer import PlacesRow  # noqa: E402
from pipeline.transform.study_transformer import SiteRow, StudyRow  # noqa: E402

# A tiny pool keeps collisions dense: duplicate studies, repeated matches, and
# multiple sites per study all appear within a handful of draws.
SCORING_NCT_IDS = ["NCT00000001", "NCT00000002", "NCT00000003", "NCT00000004"]
# The three active measures plus one the places/diseases data may omit, so the
# "missing measure" degenerate case (Req 4.8, 4.9) is reachable.
SCORING_MEASURE_IDS = ["CASTHMA", "HIGHCHOL", "DIABETES"]
SCORING_MEASURE_POOL = SCORING_MEASURE_IDS + ["DEPRESSION"]

# safe_text is lowercase ASCII + digits + space only, so no "@" / "-" / digit
# run can form an email or phone by chance. A short alphabetic label is enough.
scoring_label = st.one_of(st.just(""), st.sampled_from(["a", "bb", "ccc", "d e"]))

OVERALL_STATUSES = ["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING",
                    "COMPLETED", "WITHDRAWN", "recruiting", ""]
STUDY_TYPES = ["INTERVENTIONAL", "OBSERVATIONAL", ""]
# Empty, single, multi, and the literal "NA" (not-applicable) phase (Req 5.4, 5.5).
PHASE_LISTS = [[], ["PHASE1"], ["PHASE2"], ["PHASE1", "PHASE2"], ["NA"],
               ["PHASE2", "PHASE3", "PHASE4"], ["NA", "PHASE1"]]
# Empty, single, repeated (same type twice), and multi distinct (Req 5.3).
INTERVENTION_TYPE_LISTS = [[], ["DRUG"], ["DRUG", "DRUG"], ["DRUG", "BEHAVIORAL"],
                           ["DEVICE"], ["DRUG", "DEVICE", "BEHAVIORAL"]]
# Massachusetts (exact), " ma " (abbrev with surrounding space), other, blank.
SCORING_SITE_STATES = ["Massachusetts", "massachusetts", "MA", " ma ", "Rhode Island",
                       "connecticut", "", None]
SCORING_SITE_STATUSES = ["RECRUITING", "COMPLETED", "WITHDRAWN", "recruiting", ""]
MATCH_STATUSES = ["included", "questionable", "excluded"]

# PLACES numeric cells are kept as source text, like the transformer writes them.
YEARS = ["2022", "2023"]


@st.composite
def study_rows(draw) -> list[StudyRow]:
    """Spec 1 StudyRows drawn from the shared nctId pool; duplicates are common."""
    def one(nct_id: str) -> StudyRow:
        return StudyRow(
            nctId=nct_id,
            briefTitle=draw(scoring_label),
            overallStatus=draw(st.sampled_from(OVERALL_STATUSES)),
            studyType=draw(st.sampled_from(STUDY_TYPES)),
            phases=list(draw(st.sampled_from(PHASE_LISTS))),
            healthyVolunteers=draw(st.sampled_from(["true", "false", ""])),
            minimumAge=draw(scoring_label),
            maximumAge=draw(scoring_label),
            stdAges=list(draw(st.sampled_from([[], ["ADULT"], ["ADULT", "OLDER_ADULT"]]))),
            conditions=list(draw(st.sampled_from([[], ["a"], ["a", "bb"]]))),
            interventionTypes=list(draw(st.sampled_from(INTERVENTION_TYPE_LISTS))),
            interventionNames=list(draw(st.sampled_from([[], ["x"], ["x", "y"]]))),
            meshTerms=[], meshIds=[], ancestorTerms=[], ancestorIds=[],
            lastUpdatePostDate=draw(st.sampled_from(["2026-01-01", "2023-10-24", ""])),
            source_url="https://clinicaltrials.gov/study/" + nct_id,
        )
    nct_ids = draw(st.lists(st.sampled_from(SCORING_NCT_IDS), max_size=6))
    return [one(nct_id) for nct_id in nct_ids]


@st.composite
def site_rows(draw) -> list[SiteRow]:
    """Spec 1 SiteRows: several per study, varying state and site status."""
    def one(nct_id: str) -> SiteRow:
        state = draw(st.sampled_from(SCORING_SITE_STATES))
        return SiteRow(
            nctId=nct_id,
            facility=draw(scoring_label),
            city=draw(scoring_label),
            state="" if state is None else state,
            zip=draw(st.sampled_from(["02115", "01605", ""])),
            latitude=draw(st.sampled_from(["42.3", ""])),
            longitude=draw(st.sampled_from(["-71.8", ""])),
            siteStatus=draw(st.sampled_from(SCORING_SITE_STATUSES)),
            location_quality=draw(st.sampled_from(["ok", "missing_geo", "out_of_range"])),
        )
    nct_ids = draw(st.lists(st.sampled_from(SCORING_NCT_IDS), max_size=8))
    return [one(nct_id) for nct_id in nct_ids]


# A county's four confidence/value cells, ordered so p_low <= p <= p_high is
# reachable (Req 9.3): draw three values and sort them. Degenerate cases - a
# blank measure cell or a zero population - are mixed in so null propagation
# (Req 9.2) and the zero-population branch are exercised.
@st.composite
def _places_values(draw) -> tuple[str, str, str, str]:
    """(data_value, low_confidence_limit, high_confidence_limit) ordered low<=val<=high."""
    trio = sorted(draw(st.lists(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=3, max_size=3)))
    low, value, high = trio
    # Occasionally blank a cell so the "missing measure value" case appears.
    if draw(st.booleans()):
        return (repr(value), repr(low), repr(high))
    which = draw(st.sampled_from(["value", "low", "high"]))
    cells = {"value": repr(value), "low": repr(low), "high": repr(high)}
    cells[which] = ""
    return (cells["value"], cells["low"], cells["high"])


# The 14 MA counties (data-contract). The strategy draws a subset so the
# "county count != 14" degenerate case (Req 4.10) is common.
MA_COUNTY_FIPS = [
    "25001", "25003", "25005", "25007", "25009", "25011", "25013",
    "25015", "25017", "25019", "25021", "25023", "25025", "25027",
]


@st.composite
def places_rows(draw) -> list[PlacesRow]:
    """Spec 1 PlacesRows for MA counties; may omit a measure or a county."""
    rows: list[PlacesRow] = []
    measures = draw(st.lists(st.sampled_from(SCORING_MEASURE_POOL), unique=True, max_size=4))
    counties = draw(st.lists(st.sampled_from(MA_COUNTY_FIPS), unique=True, max_size=14))
    year = draw(st.sampled_from(YEARS))
    for measure_id in measures:
        for fips in counties:
            value, low, high = draw(_places_values())
            # Zero-population degenerate case (Req 4.6): total pop 0 means null.
            pop = draw(st.sampled_from(["0", "1000", "250000", ""]))
            rows.append(PlacesRow(
                locationname=draw(scoring_label),
                locationid=fips,
                measureid=measure_id,
                measure=draw(scoring_label),
                data_value=value,
                low_confidence_limit=low,
                high_confidence_limit=high,
                totalpop18plus=pop,
                latitude=draw(st.sampled_from(["42.3", ""])),
                longitude=draw(st.sampled_from(["-71.8", ""])),
                year=year,
            ))
    return rows


@st.composite
def disease_matches(draw) -> list[DiseaseMatch]:
    """Spec 2 DiseaseMatch rows: many-to-many (nctId, measureid), mixed statuses."""
    def one() -> DiseaseMatch:
        status = draw(st.sampled_from(MATCH_STATUSES))
        return DiseaseMatch(
            nctId=draw(st.sampled_from(SCORING_NCT_IDS)),
            measureid=draw(st.sampled_from(SCORING_MEASURE_POOL)),
            disease_label=draw(scoring_label),
            match_status=status,
            exclusion_reason="" if status == "included" else draw(
                st.sampled_from(["", "child only", "gestational"])),
            matched_on=draw(st.sampled_from(["mesh", "ancestor", "condition text"])),
            matched_term=draw(scoring_label),
        )
    return [one() for _ in range(draw(st.integers(0, 8)))]


@st.composite
def scoring_inputs(draw) -> dict:
    """One full input set for the Scoring_Exporter: studies, sites, places, matches."""
    return {
        "studies": draw(study_rows()),
        "sites": draw(site_rows()),
        "places": draw(places_rows()),
        "diseases": draw(disease_matches()),
    }
