"""Contact_Scrubber (design § Contact_Scrubber; Req 3.2, 3.4, 3.5, 3.6).

Removes contact data from a ClinicalTrials.gov page at any nesting depth:

- every key named `centralContacts` or `overallOfficials` (one count per key);
- `contacts` from each dict element of any list stored under a key named
  `locations` (one count per removed `contacts` key);
- the investigator name fields of any dict stored under a key named
  `responsibleParty` (one count per removed field);
- inside each dict element of a `locations` list, every Email_Pattern or
  Phone_Pattern match in a string `facility` or `city` value is replaced with
  `[removed]` (one count per replaced match). The first live run found phone
  numbers written into a facility name (task 11).

The walk is iterative (explicit stack), so deep inputs cannot hit the recursion
limit. `scrub` builds a new tree and never mutates or returns its input.

On any failure the error message holds only the page number and the URL, never
page content (Req 3.3, 3.5).
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.errors import PipelineError
from pipeline.patterns import PATTERNS

ALWAYS_REMOVED = ("centralContacts", "overallOfficials")
LOCATION_CONTACTS_KEY = "contacts"
LOCATION_TEXT_FIELDS = ("facility", "city")
REDACTION = "[removed]"
RESPONSIBLE_PARTY_FIELDS = frozenset(
    {"investigatorFullName", "investigatorTitle", "investigatorAffiliation", "oldNameTitle"}
)

# Names used in manifest.json and fetch_log.json (design § Raw_Store, § Fetch_Log_Writer).
LOG_KEYS = (
    ("centralContacts", "centralContacts"),
    ("overallOfficials", "overallOfficials"),
    ("locations_contacts", "locations[].contacts"),
    ("responsibleParty_investigator", "responsibleParty investigator name fields"),
    ("locations_text", "locations[] facility/city pattern matches"),
)

_SCALARS = (str, int, float, bool, type(None))


@dataclass
class RemovalCounts:
    centralContacts: int = 0
    overallOfficials: int = 0
    locations_contacts: int = 0  # reported as "locations[].contacts"
    responsibleParty_investigator: int = 0
    locations_text: int = 0  # reported as "locations[] facility/city pattern matches"

    def __add__(self, other: "RemovalCounts") -> "RemovalCounts":
        if not isinstance(other, RemovalCounts):
            return NotImplemented
        return RemovalCounts(
            *(getattr(self, attr) + getattr(other, attr) for attr, _ in LOG_KEYS)
        )

    def to_log_dict(self) -> dict[str, int]:
        """Counts keyed by their log names, in the fixed log order."""
        return {name: getattr(self, attr) for attr, name in LOG_KEYS}

    @classmethod
    def from_log_dict(cls, data: object) -> "RemovalCounts":
        """Inverse of `to_log_dict`. Raises ValueError on a malformed value."""
        if not isinstance(data, dict):
            raise ValueError("contact_removals is not an object")
        values = []
        for _, name in LOG_KEYS:
            value = data.get(name)
            if type(value) is not int or value < 0:
                raise ValueError("contact_removals.%s is not a non-negative integer" % name)
            values.append(value)
        return cls(*values)


def scrub(page: object, page_number: int | None = None, url: str | None = None
          ) -> tuple[dict, RemovalCounts]:
    """Return a scrubbed copy of `page` and the removal counts (Req 3.2, 3.4).

    `page_number` and `url` are used only in the error message (Req 3.5).
    """
    try:
        return _scrub(page)
    except Exception:
        raise PipelineError(
            "contact scrub failed on page %s of %s; page not stored"
            % (page_number if page_number is not None else "?", url or "(unknown URL)")
        ) from None


def _scrub(page: object) -> tuple[dict, RemovalCounts]:
    if not isinstance(page, dict):
        raise TypeError("page is not a JSON object")
    counts = RemovalCounts()
    root: dict = {}
    # Each entry: (source container, new empty container to fill,
    #              keys to drop from this dict, keys to drop from dict elements of this list)
    stack: list[tuple[object, object, frozenset, frozenset]] = [
        (page, root, frozenset(), frozenset())
    ]
    while stack:
        src, dst, drop_self, drop_elements = stack.pop()
        if isinstance(src, dict):
            for key, value in src.items():
                if not isinstance(key, str):
                    raise TypeError("non-string key")
                if key in ALWAYS_REMOVED:
                    if key == "centralContacts":
                        counts.centralContacts += 1
                    else:
                        counts.overallOfficials += 1
                    continue
                if key in drop_self:
                    if key == LOCATION_CONTACTS_KEY:
                        counts.locations_contacts += 1
                    else:
                        counts.responsibleParty_investigator += 1
                    continue
                if (LOCATION_CONTACTS_KEY in drop_self and key in LOCATION_TEXT_FIELDS
                        and isinstance(value, str)):
                    # src is a location element: redact contact patterns (Req 3.2).
                    value, replaced = _redact(value)
                    counts.locations_text += replaced
                child_drop_self: frozenset = frozenset()
                child_drop_elements: frozenset = frozenset()
                if key == "locations" and isinstance(value, list):
                    child_drop_elements = frozenset({LOCATION_CONTACTS_KEY})
                elif key == "responsibleParty" and isinstance(value, dict):
                    child_drop_self = RESPONSIBLE_PARTY_FIELDS
                dst[key] = _child(value, stack, child_drop_self, child_drop_elements)  # type: ignore[index]
        else:  # list
            for value in src:  # type: ignore[union-attr]
                elem_drop = drop_elements if isinstance(value, dict) else frozenset()
                dst.append(_child(value, stack, elem_drop, frozenset()))  # type: ignore[union-attr]
    return root, counts


def _redact(text: str) -> tuple[str, int]:
    """Replace every Email_Pattern, then Phone_Pattern, match with REDACTION."""
    total = 0
    for _, regex in PATTERNS:
        text, n = regex.subn(REDACTION, text)
        total += n
    return text, total


def _child(value: object, stack: list, drop_self: frozenset, drop_elements: frozenset) -> object:
    """Return the copy slot for `value`, scheduling containers for later filling."""
    if isinstance(value, dict):
        new: object = {}
    elif isinstance(value, list):
        new = []
    elif isinstance(value, _SCALARS):
        return value
    else:
        raise TypeError("non-JSON value")
    stack.append((value, new, drop_self, drop_elements))
    return new
