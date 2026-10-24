"""PLACES_Transformer (design § PLACES_Transformer; Req 6).

Input is the PLACES records in fetch order: `PlacesFetchResult.records` in a
network run, or the pages of `RawCache.places_pages` concatenated in Offline_Mode.
Steps, in this order:

1. keep only records with `stateabbr == "MA"` and `datavaluetypeid == "CrdPrv"`,
   compared exactly; stop if none remain (Req 6.2, 6.7);
2. validate `locationname`, `locationid` and `measureid`, and convert
   `locationid` to a 5-digit County_FIPS; stop on a bad identifier (Req 6.6, 6.8);
3. resolve duplicates on (County_FIPS, `measureid`) by keeping the highest
   numeric `year`, first in fetch order on a tie, and record each resolved pair
   for the fetch log; the run continues (Req 6.3);
4. build the value cells, keeping the source text and checking ranges with
   `Decimal`; a failing value becomes empty (Req 6.1, 6.4);
5. parse `geolocation` as a GeoJSON point (longitude first) or a WKT
   `POINT (lon lat)` string; missing or out of range gives empty coordinates (Req 6.5).

Error messages name the field and the record's `locationname` and `measureid`
where present, never other record content (Req 3.3).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pipeline.errors import PipelineError

_LOCATIONID_RE = re.compile(r"[0-9]{1,5}")
# Plain decimal text only: no whitespace, underscores, NaN or Infinity.
_NUMBER_RE = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_NUM = r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
_WKT_RE = re.compile(r"\s*POINT\s*\(\s*" + _NUM + r"\s+" + _NUM + r"\s*\)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class PlacesRow:
    locationname: str
    locationid: str
    measureid: str
    measure: str
    data_value: str
    low_confidence_limit: str
    high_confidence_limit: str
    totalpop18plus: str
    latitude: str
    longitude: str
    year: str


@dataclass(frozen=True)
class PlacesDuplicate:
    locationid: str   # County_FIPS
    measureid: str
    kept_year: str
    discarded: int


def build_places_rows(records: list[dict]) -> tuple[list[PlacesRow], list[PlacesDuplicate]]:
    """Return one PLACES_Row per (County_FIPS, measureid), plus the resolved duplicates."""
    # Step 1: MA crude prevalence only (Req 6.2).
    retained = [r for r in records if isinstance(r, dict)
                and r.get("stateabbr") == "MA" and r.get("datavaluetypeid") == "CrdPrv"]
    if not retained:
        raise PipelineError("PLACES: no Massachusetts Crude_Prevalence records were found")

    # Step 2: identifiers (Req 6.6, 6.8). Every retained record is checked.
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in retained:
        fips = _validate_identifiers(record)
        groups.setdefault((fips, record["measureid"]), []).append(record)

    # Step 3: duplicates (Req 6.3). dict order keeps first appearance in fetch order.
    rows: list[PlacesRow] = []
    duplicates: list[PlacesDuplicate] = []
    for (fips, measure_id), group in groups.items():
        kept = group[0]
        for candidate in group[1:]:
            if _year_rank(candidate.get("year")) > _year_rank(kept.get("year")):
                kept = candidate
        if len(group) > 1:
            duplicates.append(PlacesDuplicate(fips, measure_id, _text(kept.get("year")),
                                              len(group) - 1))
        rows.append(_build_row(kept, fips))
    return rows, duplicates


def _identifier(record: dict) -> str:
    parts = []
    for key in ("locationname", "measureid"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            parts.append("%s %s" % (key, value))
    return ", ".join(parts) if parts else "record with no locationname or measureid"


def _validate_identifiers(record: dict) -> str:
    """Return the County_FIPS, or stop the run naming the field (Req 6.6)."""
    for key in ("locationname", "locationid", "measureid"):
        value = record.get(key)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise PipelineError("PLACES: field %s is missing or empty (%s)"
                                % (key, _identifier(record)))
    for key in ("locationname", "measureid"):
        if not isinstance(record[key], str):
            raise PipelineError("PLACES: field %s is not a string (%s)"
                                % (key, _identifier(record)))
    raw = record["locationid"]
    # A JSON int is accepted; float and bool are not (design § PLACES_Transformer).
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        text = None
    else:
        text = str(raw)
    if text is None or not _LOCATIONID_RE.fullmatch(text):
        raise PipelineError("PLACES: field locationid is not 1 to 5 decimal digits (%s)"
                            % _identifier(record))
    return text.zfill(5)


def _number(value: object) -> tuple[str, Decimal] | None:
    """Source text and value of a finite number, or None (Req 6.1, 6.4)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value), Decimal(value)
    if isinstance(value, float):
        return (repr(value), Decimal(value)) if math.isfinite(value) else None
    if isinstance(value, str) and _NUMBER_RE.fullmatch(value):
        try:
            number = Decimal(value)
        except InvalidOperation:
            return None
        return (value, number) if number.is_finite() else None
    return None


def _ranged(value: object, low: Decimal | None, high: Decimal | None) -> str:
    parsed = _number(value)
    if parsed is None:
        return ""
    text, number = parsed
    if (low is not None and number < low) or (high is not None and number > high):
        return ""
    return text


def _year_rank(value: object) -> tuple[int, Decimal]:
    """A missing or non-numeric year is older than any numeric year (Req 6.3)."""
    parsed = _number(value)
    return (1, parsed[1]) if parsed is not None else (0, Decimal(0))


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (int, float)):
        parsed = _number(value)
        return parsed[0] if parsed else ""
    return ""


def _geolocation(value: object) -> tuple[str, str]:
    """(latitude, longitude) text from GeoJSON or WKT, or ("", "") (Req 6.5)."""
    lon = lat = None
    if isinstance(value, dict):
        coords = value.get("coordinates")
        if value.get("type") == "Point" and isinstance(coords, list) and len(coords) == 2:
            lon, lat = _number(coords[0]), _number(coords[1])
    elif isinstance(value, str):
        match = _WKT_RE.fullmatch(value)
        if match:
            lon, lat = _number(match.group(1)), _number(match.group(2))
    if lat is None or lon is None:
        return "", ""
    if not (-90 <= lat[1] <= 90 and -180 <= lon[1] <= 180):
        return "", ""
    return lat[0], lon[0]


_ZERO, _HUNDRED = Decimal(0), Decimal(100)


def _build_row(record: dict, fips: str) -> PlacesRow:
    lat, lon = _geolocation(record.get("geolocation"))
    return PlacesRow(
        locationname=record["locationname"],
        locationid=fips,
        measureid=record["measureid"],
        measure=_text(record.get("measure")),
        data_value=_ranged(record.get("data_value"), _ZERO, _HUNDRED),
        low_confidence_limit=_ranged(record.get("low_confidence_limit"), _ZERO, _HUNDRED),
        high_confidence_limit=_ranged(record.get("high_confidence_limit"), _ZERO, _HUNDRED),
        totalpop18plus=_ranged(record.get("totalpop18plus"), _ZERO, None),
        latitude=lat,
        longitude=lon,
        year=_text(record.get("year")),
    )
