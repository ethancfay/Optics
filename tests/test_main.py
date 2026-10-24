"""Tests for pipeline/__main__.py: version check (Req 14.2), CLI and error handling (Req 14.1, 14.8)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import pipeline.__main__ as main_mod
from pipeline.errors import PipelineError

MAIN_PATH = Path(main_mod.__file__)
REPO_ROOT = MAIN_PATH.parent.parent

# Runs pipeline/__main__.py as __main__ in a fresh interpreter with a faked
# sys.version_info. The source is compiled before an audit hook is installed;
# the hook then records every file, directory, process and network event, so
# the parent test can assert the rejection path did no I/O.
_REJECT_PROBE = r"""
import sys, json
src_path, version = sys.argv[1], tuple(json.loads(sys.argv[2]))
with open(src_path, encoding="utf-8") as fh:
    code = compile(fh.read(), src_path, "exec")
events = []
IO_PREFIXES = ("open", "os.", "shutil.", "socket.", "urllib.", "http.", "subprocess.", "import")
def hook(event, args):
    if event.startswith(IO_PREFIXES):
        events.append(event)
sys.addaudithook(hook)
sys.version_info = version
exit_code = None
try:
    exec(code, {"__name__": "__main__", "__file__": src_path})
except SystemExit as exc:
    exit_code = exc.code
sys.__stdout__.write(json.dumps({
    "exit_code": exit_code,
    "events": events,
    "pipeline_modules": sorted(m for m in sys.modules if m.startswith("pipeline")),
}))
"""


def _run_reject_probe(version):
    proc = subprocess.run(
        [sys.executable, "-c", _REJECT_PROBE, str(MAIN_PATH), json.dumps(list(version))],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    return proc, json.loads(proc.stdout)


@pytest.mark.parametrize("version", [(3, 10, 12, "final", 0), (3, 10, 0, "final", 0), (3, 8, 18, "final", 0)])
def test_version_check_rejects_old_python_without_io(version):
    """Req 14.2: < 3.11 exits non-zero, names both versions, and does no file/network I/O."""
    proc, result = _run_reject_probe(version)
    assert result["exit_code"] == 1
    expected = "Python %d.%d.%d detected; minimum is 3.11\n" % version[:3]
    assert proc.stderr == expected
    assert result["events"] == []
    assert result["pipeline_modules"] == []


@pytest.mark.parametrize(
    "version",
    [(3, 11, 0, "final", 0), (3, 12, 5, "final", 0), (3, 14, 0, "final", 0), (4, 0, 0, "final", 0)],
)
def test_version_check_accepts_311_and_newer(version, monkeypatch, capsys):
    """Req 14.2: 3.11 and every newer version pass the check."""
    monkeypatch.setattr(sys, "version_info", version)
    code = compile(MAIN_PATH.read_text(encoding="utf-8"), str(MAIN_PATH), "exec")
    namespace = {"__name__": "version_probe", "__file__": str(MAIN_PATH)}
    exec(code, namespace)  # raises SystemExit if the check rejects
    assert "run" in namespace
    assert capsys.readouterr().err == ""


def test_main_module_parses_with_old_grammar():
    """Req 14.2: the version check must be reachable on old Pythons, so the file parses under 3.8 grammar."""
    import ast

    ast.parse(MAIN_PATH.read_text(encoding="utf-8"), feature_version=(3, 8))
    assert (REPO_ROOT / "pipeline" / "__init__.py").read_text(encoding="utf-8") == ""


def _paths(tmp_path):
    return main_mod.Paths(tmp_path)


def test_pipeline_error_goes_to_stderr_with_exit_1(monkeypatch, capsys, tmp_path):
    """Req 14.8: a defined error prints its message to stderr, exits 1, and prints no summary."""

    def fail(args, paths, client):
        raise PipelineError("page 3 of https://clinicaltrials.gov/api/v2/studies failed")

    monkeypatch.setattr(main_mod, "_run_stages", fail)
    assert main_mod.run([], _paths(tmp_path), None) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "page 3 of https://clinicaltrials.gov/api/v2/studies failed" in err


def test_unexpected_exception_prints_only_type_name(monkeypatch, capsys, tmp_path):
    """Design § Error model: unexpected errors print only the type name, no message or traceback."""

    def fail(args, paths, client):
        raise KeyError("secret-record-content")

    monkeypatch.setattr(main_mod, "_run_stages", fail)
    assert main_mod.run([], _paths(tmp_path), None) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "KeyError" in err
    assert "secret-record-content" not in err
    assert "Traceback" not in err


def test_offline_flag_is_parsed(monkeypatch, tmp_path):
    """Req 14.1: the single command accepts --offline and passes paths and client through."""
    seen = {}

    def record(args, paths, client):
        seen.update(offline=args.offline, paths=paths, client=client)

    monkeypatch.setattr(main_mod, "_run_stages", record)
    sentinel = object()
    assert main_mod.run(["--offline"], _paths(tmp_path), sentinel) == 0
    assert seen == {"offline": True, "paths": _paths(tmp_path), "client": sentinel}
    assert main_mod.run([], _paths(tmp_path), None) == 0
    assert seen["offline"] is False


def test_unknown_argument_exits_2(tmp_path):
    """Design § Error model: argument errors use the argparse default exit code 2."""
    with pytest.raises(SystemExit) as excinfo:
        main_mod.run(["--bogus"], _paths(tmp_path), None)
    assert excinfo.value.code == 2


def test_paths_layout(tmp_path):
    paths = main_mod.Paths(tmp_path)
    assert paths.raw == tmp_path / "pipeline" / "raw"
    assert paths.processed == tmp_path / "pipeline" / "processed"


# --- End-to-end runs with a fake HTTP_Client (task 11) ---------------------------
#
# The fake client serves canned pages through the HttpClient interface, so it
# never reaches the socket layer (conftest blocks that). Each run uses its own
# project root, so `processed/` and `raw/` are fresh.

import hashlib
import tempfile
import urllib.parse
from datetime import datetime, timezone

from hypothesis import given
from hypothesis import strategies as st

from pipeline.data.http_client import HttpStatusError
from pipeline.io import atomic
from pipeline.io.csv_reader import read_csv
from pipeline.transform.pii_guard import EMAIL, PHONE

TODAY = datetime.now(timezone.utc).date().isoformat()
OUTPUT_FILES = ("studies.csv", "sites.csv", "places_ma.csv")
OLD_OUTPUTS = {
    "studies.csv": b"old studies\n", "sites.csv": b"old sites\n",
    "places_ma.csv": b"old places\n", "fetch_log.json": b"{\"old\": true}\n",
}


def make_study(nct_id, status="RECRUITING", state="Massachusetts", title="A study"):
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": title},
            "statusModule": {"overallStatus": status,
                             "lastUpdatePostDateStruct": {"date": TODAY}},
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE2"]},
            "eligibilityModule": {"healthyVolunteers": False, "minimumAge": "18 Years",
                                  "stdAges": ["ADULT"]},
            "conditionsModule": {"conditions": ["Asthma"]},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Drug A"}]},
            "contactsLocationsModule": {"locations": [{
                "facility": "Site A", "city": "Worcester", "state": state, "zip": "01605",
                "status": "RECRUITING", "geoPoint": {"lat": 42.26, "lon": -71.8},
            }]},
        },
        "derivedSection": {"conditionBrowseModule": {
            "meshes": [{"id": "D001249", "term": "Asthma"}],
            "ancestors": [{"id": "D012140", "term": "Respiratory Tract Diseases"}],
        }},
    }


def make_places(fips="25027", name="Worcester", measure_id="CASTHMA"):
    return {
        "locationname": name, "locationid": fips, "measureid": measure_id,
        "measure": "Current asthma among adults", "data_value": "10.5",
        "low_confidence_limit": "9.8", "high_confidence_limit": "11.2",
        "totalpop18plus": "700000", "year": "2023", "stateabbr": "MA",
        "datavaluetypeid": "CrdPrv",
        "geolocation": {"type": "Point", "coordinates": [-71.9, 42.35]},
    }


def default_sources():
    q1 = [[make_study("NCT00000001"), make_study("NCT00000002")], [make_study("NCT00000003")]]
    q2 = [[make_study("NCT00000004", status="COMPLETED")]]
    places = [[make_places(), make_places("25025", "Suffolk")]]
    return q1, q2, places


class FakeClient:
    """Serves Q1/Q2 pages by pageToken and PLACES pages by $offset."""

    def __init__(self, q1, q2, places, total_override=None, fail=None):
        self.pages = {"q1": q1, "q2": q2}
        self.places = places
        self.total_override = total_override or {}
        self.fail = fail  # (substring of URL, exception to raise)
        self.requests = []

    def get(self, url):
        self.requests.append(url)
        if self.fail and self.fail[0] in url:
            raise self.fail[1]
        parts = urllib.parse.urlsplit(url)
        params = urllib.parse.parse_qs(parts.query)
        if parts.hostname == "data.cdc.gov":
            index = int(params["$offset"][0]) // 1000
            page = self.places[index] if index < len(self.places) else []
            return json.dumps(page).encode("utf-8")
        query = "q2" if params["filter.overallStatus"][0] == "COMPLETED" else "q1"
        pages = self.pages[query]
        token = params.get("pageToken", [None])[0]
        index = 0 if token is None else int(token.split("-")[1])
        body = {"studies": pages[index]}
        if index == 0:
            body["totalCount"] = self.total_override.get(query, sum(len(p) for p in pages))
        if index + 1 < len(pages):
            body["nextPageToken"] = "%s-%d" % (query, index + 1)
        return json.dumps(body).encode("utf-8")


def _seed_processed(root):
    processed = main_mod.Paths(root).processed
    processed.mkdir(parents=True)
    for name, data in OLD_OUTPUTS.items():
        (processed / name).write_bytes(data)


def _hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}


def _no_staging_left(root):
    return not list(main_mod.Paths(root).pipeline_dir.glob(".staging-*"))


def _output_values(processed):
    """(file, field, value) for every output value, list elements included."""
    kinds = {"studies.csv": "studies", "sites.csv": "sites", "places_ma.csv": "places"}
    for name in OUTPUT_FILES:
        for row in read_csv(processed / name, kinds[name]):
            for field, value in row.items():
                for v in (value if isinstance(value, list) else [value]):
                    yield name, field, v


def _has_pattern(values):
    # sites.csv zip is checked against the Email_Pattern only (Req 8.1, 8.3 as amended).
    return any(EMAIL.search(v) or (not (name == "sites.csv" and field == "zip") and PHONE.search(v))
               for name, field, v in values)


def test_network_run_writes_outputs_and_summary(tmp_path, capsys):
    """Req 7.1, 12.1, 14.6, 11.4, 14.7: a full run writes all outputs, prints the summary,
    and still exits 0 with sanity warnings (2 studies < 2,000; 2 counties != 14)."""
    client = FakeClient(*default_sources())
    assert main_mod.run([], main_mod.Paths(tmp_path), client) == 0
    out, err = capsys.readouterr()
    assert out == "studies.csv: 4 rows\nsites.csv: 4 rows\nplaces_ma.csv: 2 rows\n"
    processed = main_mod.Paths(tmp_path).processed
    assert sorted(p.name for p in processed.iterdir()) == sorted(OUTPUT_FILES + ("fetch_log.json",))
    log = json.loads((processed / "fetch_log.json").read_text(encoding="utf-8"))
    assert log["run_mode"] == "network"
    assert log["files"] == {"studies.csv": 4, "sites.csv": 4, "places_ma.csv": 2}
    assert log["clinicaltrials_gov"]["q1"] == {"total_count": 3, "records_fetched": 3}
    assert log["clinicaltrials_gov"]["q2"] == {"total_count": 1, "records_fetched": 1}
    assert len(log["warnings"]) == 2 and all(w in err for w in log["warnings"])
    assert log["urls"]["clinicaltrials_gov"] + log["urls"]["cdc_places"] == client.requests
    # Q1 pages, then Q2, then PLACES (Req 1.1, design § Data flow).
    hosts = ["q2" if "=COMPLETED" in u else "places" if "cdc.gov" in u else "q1"
             for u in client.requests]
    assert hosts == ["q1", "q1", "q2", "places"]
    assert (main_mod.Paths(tmp_path).raw / "manifest.json").exists()
    assert _no_staging_left(tmp_path)


def _q1_with(**kwargs):
    return [[make_study("NCT00000001", **kwargs)]]


_STAGE_FAILURES = {
    # stage: (FakeClient kwargs, expected stderr fragment)
    "http_404": (dict(fail=("clinicaltrials.gov", HttpStatusError("https://clinicaltrials.gov/x", 404))),
                 "HTTP 404"),
    "places_http_error": (dict(fail=("data.cdc.gov", PipelineError("request failed: data.cdc.gov"))),
                          "data.cdc.gov"),
    "total_count": (dict(total_override={"q2": 5}), "Q2: fetched 1 records but totalCount is 5"),
    "no_allowed_state": (dict(q1=_q1_with(state="California"), q2=[[]]), "Allowed_States"),
    "places_empty": (dict(places=[[]]), "no PLACES records"),
    "places_bad_id": (dict(places=[[make_places(fips="25a")]]), "field locationid"),
    "pii": (dict(q1=_q1_with(title="mail zqx@example.org")), "PII_Guard"),
}


def test_facility_phone_is_redacted_before_raw_store(tmp_path, capsys):
    """Req 3.2, 10.6 (amended in task 11): a phone number written into a facility name
    is replaced before the raw write, so the run completes and nothing stores it."""
    study = make_study("NCT00000001")
    loc = study["protocolSection"]["contactsLocationsModule"]["locations"][0]
    loc["facility"] = "Clinic (1-617-555-0100, 1-617-555-0199)"
    loc["zip"] = "01605"
    paths = main_mod.Paths(tmp_path)
    assert main_mod.run([], paths, FakeClient([[study]], [[]], default_sources()[2])) == 0
    for path in list(paths.raw.iterdir()) + list(paths.processed.iterdir()):
        assert "555-01" not in path.read_text(encoding="utf-8")
    log = json.loads((paths.processed / "fetch_log.json").read_text(encoding="utf-8"))
    assert log["contact_removals"]["locations[] facility/city pattern matches"] == 2
    sites = read_csv(paths.processed / "sites.csv", "sites")
    assert sites[0]["facility"] == "Clinic ([removed], [removed])"
    assert sites[0]["zip"] == "01605"


@pytest.mark.parametrize("stage", sorted(_STAGE_FAILURES))
def test_failure_at_each_stage_leaves_processed_unchanged(stage, tmp_path, capsys):
    """Req 8.2, 9.6, 12.9, 14.8: any failure exits 1, prints the error, prints no summary,
    and leaves every file in processed/ byte-identical, with no new files."""
    overrides, fragment = _STAGE_FAILURES[stage]
    overrides = dict(overrides)
    q1, q2, places = default_sources()
    sources = {"q1": q1, "q2": q2, "places": places}
    sources.update({k: overrides.pop(k) for k in list(overrides) if k in sources})
    _seed_processed(tmp_path)
    before = _hashes(main_mod.Paths(tmp_path).processed)
    client = FakeClient(sources["q1"], sources["q2"], sources["places"], **overrides)
    assert main_mod.run([], main_mod.Paths(tmp_path), client) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert fragment in err
    assert "zqx@example.org" not in err
    assert _hashes(main_mod.Paths(tmp_path).processed) == before
    assert _no_staging_left(tmp_path)


def test_csv_write_failure_names_file(tmp_path, monkeypatch, capsys):
    """Req 7.10: a CSV write failure names the file and leaves processed/ unchanged."""
    real = atomic._write_bytes

    def write(path, data):
        if path.name == "places_ma.csv":
            raise OSError(28, "No space left on device")
        real(path, data)

    monkeypatch.setattr(atomic, "_write_bytes", write)
    _seed_processed(tmp_path)
    before = _hashes(main_mod.Paths(tmp_path).processed)
    assert main_mod.run([], main_mod.Paths(tmp_path), FakeClient(*default_sources())) == 1
    out, err = capsys.readouterr()
    assert out == "" and "places_ma.csv" in err
    assert _hashes(main_mod.Paths(tmp_path).processed) == before
    assert _no_staging_left(tmp_path)


def test_fetch_log_write_failure_names_file(tmp_path, monkeypatch, capsys):
    """Req 12.10: a fetch_log.json failure names the file and reason, exits 1, no summary."""
    real = atomic._write_bytes

    def write(path, data):
        if path.name == "fetch_log.json":
            raise PermissionError(13, "Permission denied")
        real(path, data)

    monkeypatch.setattr(atomic, "_write_bytes", write)
    _seed_processed(tmp_path)
    assert main_mod.run([], main_mod.Paths(tmp_path), FakeClient(*default_sources())) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "fetch_log.json (PermissionError: Permission denied)" in err
    processed = main_mod.Paths(tmp_path).processed
    assert (processed / "fetch_log.json").read_bytes() == OLD_OUTPUTS["fetch_log.json"]


def test_offline_with_empty_raw_names_both_sources(tmp_path, capsys):
    """Req 10.4: --offline with no cache stops before any output and names both sources."""
    _seed_processed(tmp_path)
    before = _hashes(main_mod.Paths(tmp_path).processed)
    assert main_mod.run(["--offline"], main_mod.Paths(tmp_path), None) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "ClinicalTrials.gov and PLACES" in err
    assert _hashes(main_mod.Paths(tmp_path).processed) == before


def test_offline_run_builds_no_client_and_rescrubs(tmp_path, monkeypatch, capsys):
    """Req 10.3, 14.4, 3.6: the offline path never builds an HTTP_Client, re-scrubs the
    raw pages, and adds the re-scrub removals to the stored totals."""
    paths = main_mod.Paths(tmp_path)
    assert main_mod.run([], paths, FakeClient(*default_sources())) == 0
    network_log = json.loads((paths.processed / "fetch_log.json").read_text(encoding="utf-8"))

    page_file = paths.raw / "ctgov_q1_page_001.json"
    page = json.loads(page_file.read_text(encoding="utf-8"))
    page["studies"][0]["protocolSection"]["contactsLocationsModule"]["centralContacts"] = []
    page_file.write_text(json.dumps(page), encoding="utf-8")

    def no_client(*args, **kwargs):
        raise AssertionError("HttpClient built in Offline_Mode")

    monkeypatch.setattr(main_mod, "HttpClient", no_client)
    capsys.readouterr()
    assert main_mod.run(["--offline"], paths, None) == 0
    offline_log = json.loads((paths.processed / "fetch_log.json").read_text(encoding="utf-8"))
    assert offline_log["run_mode"] == "offline"
    assert offline_log["fetch_date"] == network_log["fetch_date"]
    assert offline_log["urls"] == network_log["urls"]
    assert offline_log["contact_removals"]["centralContacts"] == (
        network_log["contact_removals"]["centralContacts"] + 1)
    assert capsys.readouterr().out.startswith("studies.csv: 4 rows\n")


# --- Properties P1 and P2 (Req 8.3, 8.6, 13.1, 13.9) ------------------------------

_local = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789._+-", min_size=1, max_size=8)
_domain = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=8)
emails = st.builds(lambda a, b, c: "%s@%s.%s" % (a, b, c), _local, _domain,
                   st.sampled_from(["org", "com", "edu", "io"]))
_d = st.text(alphabet="0123456789", min_size=1, max_size=1)
phones = st.builds(
    lambda fmt, digits: fmt.format(*digits),
    st.sampled_from(["{0}{1}{2}-{3}{4}{5}-{6}{7}{8}{9}", "({0}{1}{2}) {3}{4}{5}-{6}{7}{8}{9}",
                     "+1 {0}{1}{2}.{3}{4}{5}.{6}{7}{8}{9}", "{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}"]),
    st.lists(_d, min_size=10, max_size=10),
)
contact_values = st.one_of(emails, phones, st.just("Dr ZQX Person"))
contact_people = st.fixed_dictionaries({"name": st.just("ZQX Person"),
                                        "email": emails, "phone": phones})

# Contact_Data structures (removed by the Contact_Scrubber).
CONTACT_TARGETS = ["centralContacts", "overallOfficials", "location_contacts", "responsibleParty"]
# Ordinary string fields that reach the outputs.
STUDY_TARGETS = ["briefTitle", "condition", "interventionName", "meshTerm", "facility", "city",
                 "zip", "siteStatus", "minimumAge"]
PLACES_TARGETS = ["measure", "locationname", "year"]


def _inject(study, target, value, person):
    ps = study["protocolSection"]
    loc = ps["contactsLocationsModule"]["locations"][0]
    if target == "centralContacts":
        ps["contactsLocationsModule"]["centralContacts"] = [person]
    elif target == "overallOfficials":
        ps["contactsLocationsModule"]["overallOfficials"] = [person]
    elif target == "location_contacts":
        loc["contacts"] = [person]
    elif target == "responsibleParty":
        ps["sponsorCollaboratorsModule"] = {"responsibleParty": {
            "type": "PRINCIPAL_INVESTIGATOR", "investigatorFullName": value,
            "investigatorAffiliation": value}}
    elif target == "briefTitle":
        ps["identificationModule"]["briefTitle"] = value
    elif target == "condition":
        ps["conditionsModule"]["conditions"].append(value)
    elif target == "interventionName":
        ps["armsInterventionsModule"]["interventions"][0]["name"] = value
    elif target == "meshTerm":
        study["derivedSection"]["conditionBrowseModule"]["meshes"][0]["term"] = value
    elif target == "facility":
        loc["facility"] = value
    elif target == "city":
        loc["city"] = value
    elif target == "zip":
        loc["zip"] = value
    elif target == "siteStatus":
        loc["status"] = value
    elif target == "minimumAge":
        ps["eligibilityModule"]["minimumAge"] = value


@st.composite
def injected_sources(draw, contacts_only):
    """Q1/Q2/PLACES pages with contact values injected at drawn places."""
    study_targets = CONTACT_TARGETS if contacts_only else CONTACT_TARGETS + STUDY_TARGETS
    n = draw(st.integers(1, 4))
    studies = [make_study("NCT%08d" % (i + 1), status=draw(st.sampled_from(["RECRUITING", "COMPLETED"])))
               for i in range(n)]
    for study in studies:
        for target in draw(st.lists(st.sampled_from(study_targets), unique=True, max_size=4)):
            _inject(study, target, draw(contact_values), draw(contact_people))
    split = draw(st.integers(0, n))
    q1 = [studies[:split]]
    q2 = [studies[split:]]
    places = [make_places(), make_places("25025", "Suffolk")]
    if not contacts_only:
        for record in places:
            for target in draw(st.lists(st.sampled_from(PLACES_TARGETS), unique=True, max_size=2)):
                record[target] = draw(contact_values)
    return q1, q2, [places]


def _run_in_fresh_root(sources):
    with tempfile.TemporaryDirectory() as root:
        root = Path(root)
        _seed_processed(root)
        processed = main_mod.Paths(root).processed
        before = _hashes(processed)
        code = main_mod.run([], main_mod.Paths(root), FakeClient(*sources))
        after = _hashes(processed)
        values = list(_output_values(processed)) if code == 0 else []
        return code, before, after, values


@given(injected_sources(contacts_only=False))
def test_p1_stop_unchanged_or_clean_outputs(sources):
    """P1 (Req 8.3, 13.1): with contact values injected anywhere, the run either stops with
    processed/ unchanged, or completes with no Email_Pattern / Phone_Pattern match."""
    code, before, after, values = _run_in_fresh_root(sources)
    if code != 0:
        assert after == before
    else:
        assert not _has_pattern(values)


@given(injected_sources(contacts_only=True))
def test_p2_contacts_only_in_contact_structures_exit_0_and_clean(sources):
    """P2 (Req 8.6, 13.9): contact values only inside Contact_Data structures give exit 0
    and clean outputs."""
    code, before, after, values = _run_in_fresh_root(sources)
    assert code == 0
    assert values and not _has_pattern(values)
