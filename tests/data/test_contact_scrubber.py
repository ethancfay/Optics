"""Contact_Scrubber tests (Req 3.2, 3.4, 3.5, 13.10; property P6)."""
import copy
import json

import pytest
from hypothesis import given

from pipeline.data.contact_scrubber import RemovalCounts, scrub
from pipeline.data.raw_store import RawStore
from pipeline.errors import PipelineError
from tests.strategies import RP_FIELDS, pages_with_contacts

URL = "https://clinicaltrials.gov/api/v2/studies?pageSize=1000"


def _keys_and_parents(tree):
    """Yield (parent_key, key, value) for every dict entry in the tree."""
    stack = [(None, tree)]
    while stack:
        parent_key, node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                yield parent_key, k, v
                stack.append((k, v))
        elif isinstance(node, list):
            stack.extend((parent_key, item) for item in node)


@given(pages_with_contacts())
def test_p6_scrubber_removes_contacts_at_any_depth(injected):
    """P6 (Req 3.2, 3.4, 13.10): no contact structure or injected value remains; counts are exact."""
    original = copy.deepcopy(injected.page)
    scrubbed, counts = scrub(injected.page, 1, URL)

    assert injected.page == original  # input untouched
    for parent_key, key, value in _keys_and_parents(scrubbed):
        assert key not in ("centralContacts", "overallOfficials")
        assert not (parent_key == "locations" and key == "contacts")
        assert not (parent_key == "responsibleParty" and key in RP_FIELDS)
    text = json.dumps(scrubbed, ensure_ascii=False)
    for value in injected.values:
        assert value not in text
    assert counts == RemovalCounts(**injected.expected)


def test_scrub_example_counts_and_keeps_other_data():
    """Req 3.2, 3.4: one count per removed key or field; non-contact data is kept."""
    page = {
        "studies": [{
            "protocolSection": {
                "contactsLocationsModule": {
                    "centralContacts": [{"name": "A"}],
                    "overallOfficials": [{"name": "B"}],
                    "locations": [
                        {"facility": "F1", "contacts": [{"phone": "617-555-0100"}]},
                        {"facility": "F2"},
                    ],
                },
                "sponsorCollaboratorsModule": {"responsibleParty": {
                    "type": "PRINCIPAL_INVESTIGATOR",
                    "investigatorFullName": "C", "oldNameTitle": "D",
                }},
            },
        }],
        "nextPageToken": "abc",
    }
    scrubbed, counts = scrub(page, 1, URL)
    assert counts == RemovalCounts(1, 1, 1, 2)
    assert scrubbed == {
        "studies": [{
            "protocolSection": {
                "contactsLocationsModule": {"locations": [{"facility": "F1"}, {"facility": "F2"}]},
                "sponsorCollaboratorsModule": {"responsibleParty": {"type": "PRINCIPAL_INVESTIGATOR"}},
            },
        }],
        "nextPageToken": "abc",
    }


def test_scrub_zero_counts_when_nothing_removed():
    """Req 3.4: zero recorded for each type with no removals."""
    _, counts = scrub({"studies": []}, 1, URL)
    assert counts.to_log_dict() == {
        "centralContacts": 0, "overallOfficials": 0, "locations[].contacts": 0,
        "responsibleParty investigator name fields": 0,
    }


def test_scrub_handles_deep_nesting_without_recursion_error():
    deep = {"centralContacts": [{"email": "x@y.org"}]}
    for _ in range(5000):
        deep = {"items": [deep]}
    scrubbed, counts = scrub({"studies": [deep]}, 1, URL)
    assert counts.centralContacts == 1
    node = scrubbed["studies"][0]
    while "items" in node:
        node = node["items"][0]
    assert node == {}


def test_scrub_failure_names_page_and_url_only_and_writes_nothing(tmp_path):
    """Req 3.5: a page the scrubber cannot finish is not stored; message has page and URL only."""
    store = RawStore(tmp_path / "raw")
    store.begin_network_run()
    bad_page = {"studies": [{"centralContacts": [{"email": "secret@example.org"}],
                             "weird": {1, 2}}]}  # a set is not JSON data
    with pytest.raises(PipelineError) as info:
        scrubbed, _ = scrub(bad_page, 3, URL)
        store.write_page("ctgov_q1", 1, scrubbed)  # never reached
    message = str(info.value)
    assert "page 3" in message and URL in message
    assert "secret" not in message and "weird" not in message
    assert list((tmp_path / "raw").iterdir()) == []


def test_scrub_rejects_non_object_page():
    with pytest.raises(PipelineError, match="page 2 of"):
        scrub(["not", "a", "page"], 2, URL)


def test_removal_counts_add_and_round_trip():
    total = RemovalCounts(1, 2, 3, 4) + RemovalCounts(1, 1, 1, 1)
    assert total == RemovalCounts(2, 3, 4, 5)
    assert RemovalCounts.from_log_dict(total.to_log_dict()) == total
