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
