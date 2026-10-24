"""Load and validate the Rules_Config `pipeline/mapping/rules.py`.

Condition-grouping Req 2.4-2.9 and 11.9 (design § Rules loader).

- `load_rules` imports the module. An import failure or missing / ill-typed
  `DISEASES` / `SAMPLE_SEED` raises `ConfigError("rules.py: ...")` (Req 2.9).
- `validate` is pure: it collects every failed Req 2.5 / 2.6 check and raises
  one `ConfigError` with one line per check. Each line starts with the
  measureid, or `Rules_Config` for file-level and seed checks (Req 2.7).
"""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import Literal

from pipeline.errors import ConfigError

SUPPORTED_MEASURES = ("CASTHMA", "HIGHCHOL", "DIABETES", "BPHIGH", "DEPRESSION")
RESERVED_REASONS = ("child_only", "unparseable_age", "healthy_volunteers_only", "ancestor_only")
ANCESTOR_ONLY_STATUSES = ("included", "questionable")

MAX_DISEASES = 5
MAX_LABEL_CHARS = 100
MAX_TERM_CHARS = 200
SEED_MAX = 2**32 - 1

_REASON_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")
_KEYS = (
    "measureid",
    "disease_label",
    "ancestor_only_status",
    "recall_query_term",
    "include",
    "exclude",
    "questionable",
)
_FILE = "Rules_Config"
_RULES_FILE = "rules.py"

TermKind = Literal["include", "exclude", "questionable"]


@dataclass(frozen=True)
class Term:
    text: str
    norm: str
    kind: TermKind
    reason: str  # "" for include terms


@dataclass(frozen=True)
class Disease:
    measureid: str
    label: str
    ancestor_only_status: str
    recall_query_term: str
    terms: tuple[Term, ...]


@dataclass(frozen=True)
class RulesConfig:
    diseases: tuple[Disease, ...]  # sorted by measureid
    seed: int


def normalize(text: str) -> str:
    """Normalized_Text: Unicode case fold, whitespace runs collapsed, trimmed."""
    return " ".join(text.casefold().split())


def load_rules(module_name: str = "pipeline.mapping.rules") -> RulesConfig:
    """Import the Rules_Config module and validate it (Req 2.5-2.9)."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name is not None and (
            exc.name == module_name or module_name.startswith(exc.name + ".")
        ):
            raise ConfigError("%s: file not found" % _RULES_FILE) from None
        raise ConfigError("%s: cannot be imported (ModuleNotFoundError)" % _RULES_FILE) from None
    except Exception as exc:  # any failure while importing the data module
        raise ConfigError(
            "%s: cannot be imported (%s)" % (_RULES_FILE, type(exc).__name__)
        ) from None

    for name in ("DISEASES", "SAMPLE_SEED"):
        if not hasattr(module, name):
            raise ConfigError("%s: %s is not defined" % (_RULES_FILE, name))
    diseases_obj = getattr(module, "DISEASES")
    seed_obj = getattr(module, "SAMPLE_SEED")
    if not isinstance(diseases_obj, list):
        raise ConfigError("%s: DISEASES must be a list" % _RULES_FILE)
    if not all(isinstance(entry, dict) for entry in diseases_obj):
        raise ConfigError("%s: every DISEASES entry must be a dict" % _RULES_FILE)
    if type(seed_obj) is not int:
        raise ConfigError("%s: SAMPLE_SEED must be an int" % _RULES_FILE)
    return validate(diseases_obj, seed_obj)


def validate(diseases_obj: object, seed_obj: object) -> RulesConfig:
    """Check every Req 2.5 / 2.6 / 11.9 rule; raise one ConfigError listing all failures."""
    errors: list[str] = []

    if type(seed_obj) is not int or not 0 <= seed_obj <= SEED_MAX:
        errors.append(
            "%s: SAMPLE_SEED must be an integer from 0 to %d" % (_FILE, SEED_MAX)
        )

    diseases: list[Disease] = []
    if not isinstance(diseases_obj, list):
        errors.append("%s: DISEASES must be a list" % _FILE)
    else:
        if not 1 <= len(diseases_obj) <= MAX_DISEASES:
            errors.append(
                "%s: must contain 1 to %d disease definitions (found %d)"
                % (_FILE, MAX_DISEASES, len(diseases_obj))
            )
        seen_ids: set[str] = set()
        reported_dupes: set[str] = set()
        for index, entry in enumerate(diseases_obj, start=1):
            disease = _validate_disease(index, entry, errors)
            measureid = entry.get("measureid") if isinstance(entry, dict) else None
            if isinstance(measureid, str) and measureid in SUPPORTED_MEASURES:
                if measureid in seen_ids and measureid not in reported_dupes:
                    errors.append("%s: measureid appears more than once" % measureid)
                    reported_dupes.add(measureid)
                seen_ids.add(measureid)
            if disease is not None:
                diseases.append(disease)

    if errors:
        raise ConfigError(errors)
    diseases.sort(key=lambda d: d.measureid)
    return RulesConfig(diseases=tuple(diseases), seed=seed_obj)  # type: ignore[arg-type]


def _validate_disease(index: int, entry: object, errors: list[str]) -> Disease | None:
    """Validate one Disease_Definition. Appends failures; returns None if any."""
    start = len(errors)
    if not isinstance(entry, dict):
        errors.append("%s: disease definition %d must be a dict" % (_FILE, index))
        return None

    measureid = entry.get("measureid")
    if isinstance(measureid, str) and measureid in SUPPORTED_MEASURES:
        who = measureid
    else:
        who = "%s: disease definition %d" % (_FILE, index)
        errors.append("%s: measureid must be one of %s" % (who, ", ".join(SUPPORTED_MEASURES)))

    for key in _KEYS:
        if key not in entry:
            errors.append("%s: missing key %r" % (who, key))
    for key in sorted(k for k in entry if k not in _KEYS):
        errors.append("%s: unknown key %r" % (who, str(key)))

    label = entry.get("disease_label")
    if "disease_label" in entry and not _text_ok(label, MAX_LABEL_CHARS):
        errors.append(
            "%s: disease_label must be a string of 1 to %d characters after normalization"
            % (who, MAX_LABEL_CHARS)
        )

    status = entry.get("ancestor_only_status")
    if "ancestor_only_status" in entry and status not in ANCESTOR_ONLY_STATUSES:
        errors.append("%s: ancestor_only_status must be 'included' or 'questionable'" % who)

    recall = entry.get("recall_query_term")
    if "recall_query_term" in entry and not _text_ok(recall, MAX_TERM_CHARS):
        errors.append(
            "%s: recall_query_term must be a string of 1 to %d characters after normalization"
            % (who, MAX_TERM_CHARS)
        )

    terms: list[Term] = []
    include = entry.get("include")
    if "include" in entry:
        if not isinstance(include, list):
            errors.append("%s: include must be a list of strings" % who)
        else:
            if not include:
                errors.append("%s: include must have at least one term" % who)
            for pos, term in enumerate(include, start=1):
                if _term_ok(who, "include", pos, term, errors):
                    terms.append(Term(term, normalize(term), "include", ""))

    for kind in ("exclude", "questionable"):
        if kind not in entry:
            continue
        items = entry[kind]
        if not isinstance(items, list):
            errors.append("%s: %s must be a list of (term, reason) tuples" % (who, kind))
            continue
        for pos, item in enumerate(items, start=1):
            if not (isinstance(item, (tuple, list)) and len(item) == 2):
                errors.append(
                    "%s: %s entry %d must be a (term, reason) tuple" % (who, kind, pos)
                )
                continue
            term, reason = item
            term_ok = _term_ok(who, kind, pos, term, errors)
            reason_ok = _reason_ok(who, kind, pos, reason, errors)
            if term_ok and reason_ok:
                terms.append(Term(term, normalize(term), kind, reason))  # type: ignore[arg-type]

    # Req 2.6: duplicates within one list or across lists, as Normalized_Text.
    seen: dict[str, str] = {}
    reported: set[str] = set()
    for term in terms:
        if term.norm in seen:
            if term.norm not in reported:
                errors.append(
                    "%s: duplicated term %r (in %s and %s)"
                    % (who, term.text, seen[term.norm], term.kind)
                )
                reported.add(term.norm)
        else:
            seen[term.norm] = term.kind

    if len(errors) > start:
        return None
    return Disease(
        measureid=measureid,  # type: ignore[arg-type]
        label=label,  # type: ignore[arg-type]
        ancestor_only_status=status,  # type: ignore[arg-type]
        recall_query_term=recall,  # type: ignore[arg-type]
        terms=tuple(terms),
    )


def _text_ok(value: object, max_chars: int) -> bool:
    return isinstance(value, str) and 1 <= len(normalize(value)) <= max_chars


def _term_ok(who: str, kind: str, pos: int, term: object, errors: list[str]) -> bool:
    if _text_ok(term, MAX_TERM_CHARS):
        return True
    errors.append(
        "%s: %s term %d must be a string of 1 to %d characters after normalization"
        % (who, kind, pos, MAX_TERM_CHARS)
    )
    return False


def _reason_ok(who: str, kind: str, pos: int, reason: object, errors: list[str]) -> bool:
    if not isinstance(reason, str) or _REASON_RE.fullmatch(reason) is None:
        errors.append(
            "%s: %s entry %d reason code must be 1 to 40 characters of a-z, 0-9 and _, "
            "starting with a letter" % (who, kind, pos)
        )
        return False
    if reason in RESERVED_REASONS:
        errors.append(
            "%s: %s entry %d uses reserved reason code %r" % (who, kind, pos, reason)
        )
        return False
    return True
