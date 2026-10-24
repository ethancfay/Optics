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
