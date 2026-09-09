"""Transform selected Seoul small-business rows into tourism CSV schemas."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ATTRACTION_CODES = {
    "I21201": ("cafe", "카페"),
    "S20801": ("heat_source", "찜질방/사우나"),
    "S20802": ("massage_spot", "안마/스파"),
}
ATTRACTION_CONSTRAINTS = {
    "cafe": ("t", "f", "f", "1"),
    "heat_source": ("t", "t", "f", "1"),
    "massage_spot": ("t", "f", "t", "1"),
    "spa": ("t", "t", "t", "1"),
    "drugstore": ("t", "f", "f", "2"),
}
ACCOMMODATION_CODES = {"I10101", "I10102", "I10103"}
HOSPITAL_CODES = {"Q10204", "Q10208"}
UROLOGY_EXCLUDES = ("비뇨", "비뇨기과", "남성", "요로")


def _clean_spaces(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_name(value: str | None) -> str:
    text = _clean_spaces(value).lower()
    for corporate_marker in ("(주)", "㈜", "주식회사", "유한회사"):
        text = text.replace(corporate_marker, "")
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def normalize_address(value: str | None) -> str:
    text = _clean_spaces(value).replace("서울특별시", "서울")
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def _value(row: Mapping[str, str], snake: str, korean: str) -> str:
    return _clean_spaces(row.get(snake) or row.get(korean))


def _name(row: Mapping[str, str]) -> str:
    if row.get("place_name"):
        return _clean_spaces(row.get("place_name"))
    return build_place_name(row.get("상호명"), row.get("지점명"))


def _coordinates(row: Mapping[str, str]) -> tuple[float, float] | None:
    try:
        longitude = float(_value(row, "map_x", "경도"))
        latitude = float(_value(row, "map_y", "위도"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None
    return longitude, latitude


def haversine_metres(first: tuple[float, float], second: tuple[float, float]) -> float:
    lng1, lat1 = first
    lng2, lat2 = second
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = lat2_rad - lat1_rad
    delta_lng = math.radians(lng2 - lng1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return 12_742_000 * math.asin(math.sqrt(value))


def _name_similarity(first: str, second: str) -> float:
    left = normalize_name(first)
    right = normalize_name(second)
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return min(len(left), len(right)) / max(len(left), len(right))
    return SequenceMatcher(None, left, right).ratio()


def is_same_place(
    first: Mapping[str, str],
    second: Mapping[str, str],
    *,
    distance_limit_metres: float = 30.0,
    name_similarity_threshold: float = 0.72,
) -> bool:
    first_name = normalize_name(_name(first))
    second_name = normalize_name(_name(second))
    if not first_name or first_name != second_name:
        exact_name = False
    else:
        exact_name = True

    first_addresses = {
        normalize_address(_value(first, "road_address_name", "도로명주소")),
        normalize_address(_value(first, "address_name", "지번주소")),
    } - {""}
    second_addresses = {
        normalize_address(_value(second, "road_address_name", "도로명주소")),
        normalize_address(_value(second, "address_name", "지번주소")),
    } - {""}
    if exact_name and first_addresses.intersection(second_addresses):
        return True

    first_coord = _coordinates(first)
    second_coord = _coordinates(second)
    return bool(
        first_coord
        and second_coord
        and haversine_metres(first_coord, second_coord) <= distance_limit_metres
        and _name_similarity(_name(first), _name(second)) >= name_similarity_threshold
    )


@dataclass(frozen=True)
class ApprovalMatch:
    status: str
    approval: Mapping[str, str] | None = None
    approval_index: int | None = None


class ApprovalMatcher:
    """Find a unique approval record without copying its Kakao identity fields."""

    def __init__(self, approvals: Sequence[Mapping[str, str]]):
        self.approvals = list(approvals)
        self._by_name_address: dict[tuple[str, str], list[int]] = {}
        self._by_grid: dict[tuple[int, int], list[int]] = {}
        for index, approval in enumerate(self.approvals):
            name = normalize_name(_name(approval))
            for address in (
                normalize_address(_value(approval, "road_address_name", "도로명주소")),
                normalize_address(_value(approval, "address_name", "지번주소")),
            ):
                if name and address:
                    self._by_name_address.setdefault((name, address), []).append(index)
            coord = _coordinates(approval)
            if coord:
                self._by_grid.setdefault(self._grid_key(coord), []).append(index)

    @staticmethod
    def _grid_key(coord: tuple[float, float]) -> tuple[int, int]:
        return round(coord[0] * 1000), round(coord[1] * 1000)

    def match(self, source: Mapping[str, str]) -> ApprovalMatch:
        name = normalize_name(_name(source))
        exact: set[int] = set()
        for address in (
            normalize_address(_value(source, "road_address_name", "도로명주소")),
            normalize_address(_value(source, "address_name", "지번주소")),
        ):
            if name and address:
                exact.update(self._by_name_address.get((name, address), []))
        if len(exact) == 1:
            index = next(iter(exact))
            return ApprovalMatch("matched", self.approvals[index], index)
        if len(exact) > 1:
            return ApprovalMatch("ambiguous")

        coord = _coordinates(source)
        if not coord:
            return ApprovalMatch("not_matched")
        grid_x, grid_y = self._grid_key(coord)
        qualified: list[tuple[float, float, int]] = []
        for x in range(grid_x - 1, grid_x + 2):
            for y in range(grid_y - 1, grid_y + 2):
                for index in self._by_grid.get((x, y), []):
                    approval = self.approvals[index]
                    approval_coord = _coordinates(approval)
                    if approval_coord is None:
                        continue
                    distance = haversine_metres(coord, approval_coord)
                    similarity = _name_similarity(_name(source), _name(approval))
                    if distance <= 30.0 and similarity >= 0.72:
                        qualified.append((round(distance, 6), -round(similarity, 6), index))
        if not qualified:
            return ApprovalMatch("not_matched")
        qualified.sort()
        best = qualified[0]
        if len(qualified) > 1 and qualified[1][:2] == best[:2]:
            return ApprovalMatch("ambiguous")
        return ApprovalMatch("matched", self.approvals[best[2]], best[2])


class EntityIndex:
    """Incremental duplicate index using the same conservative entity rules."""

    def __init__(self, rows: Iterable[Mapping[str, str]] = ()):
        self.rows: list[Mapping[str, str]] = []
        self._by_name_address: dict[tuple[str, str], list[int]] = {}
        self._by_grid: dict[tuple[int, int], list[int]] = {}
        for row in rows:
            self.add(row)

    def add(self, row: Mapping[str, str]) -> None:
        index = len(self.rows)
        self.rows.append(row)
        name = normalize_name(_name(row))
        for address in (
            normalize_address(_value(row, "road_address_name", "도로명주소")),
            normalize_address(_value(row, "address_name", "지번주소")),
        ):
            if name and address:
                self._by_name_address.setdefault((name, address), []).append(index)
        coord = _coordinates(row)
        if coord:
            key = ApprovalMatcher._grid_key(coord)
            self._by_grid.setdefault(key, []).append(index)

    def find(self, row: Mapping[str, str]) -> Mapping[str, str] | None:
        name = normalize_name(_name(row))
        candidates: set[int] = set()
        for address in (
            normalize_address(_value(row, "road_address_name", "도로명주소")),
            normalize_address(_value(row, "address_name", "지번주소")),
        ):
            if name and address:
                candidates.update(self._by_name_address.get((name, address), []))
        for index in sorted(candidates):
            if is_same_place(self.rows[index], row):
                return self.rows[index]

        coord = _coordinates(row)
        if coord:
            grid_x, grid_y = ApprovalMatcher._grid_key(coord)
            for x in range(grid_x - 1, grid_x + 2):
                for y in range(grid_y - 1, grid_y + 2):
                    for index in self._by_grid.get((x, y), []):
                        if is_same_place(self.rows[index], row):
                            return self.rows[index]
        return None


def build_place_name(business_name: str | None, branch_name: str | None) -> str:
    """Build the agreed display name without fabricating an identifier."""
    name = _clean_spaces(business_name)
    branch = _clean_spaces(branch_name)
    if not branch or branch == "코리아":
        return name
    if name.endswith(branch):
        return name
    return f"{name} {branch}".strip()


def classify_source_row(row: Mapping[str, str]) -> tuple[str, str, str] | None:
    """Return destination, primary type, and display type for an allowed row."""
    place_name = build_place_name(row.get("상호명"), row.get("지점명"))
    code = _clean_spaces(row.get("상권업종소분류코드"))

    if "올리브영" in place_name:
        return "attraction", "drugstore", "드럭스토어"
    if code in ATTRACTION_CODES:
        primary_type, primary_type_name = ATTRACTION_CODES[code]
        return "attraction", primary_type, primary_type_name
    if code in ACCOMMODATION_CODES:
        return "accommodation", "accommodation", "숙소"
    if code in HOSPITAL_CODES:
        if code == "Q10204" and any(term in place_name for term in UROLOGY_EXCLUDES):
            return None
        return "hospital", "hospital", "병원"
    return None


def make_output_row(
    source: Mapping[str, str],
    *,
    destination: str,
    primary_type: str,
    primary_type_name: str,
    constraints: Mapping[str, str] | None,
    synced_at: str,
) -> dict[str, str]:
    """Map a source row to the union of tourism output fields."""
    output = {
        "id": "",
        "address_name": _clean_spaces(source.get("지번주소")),
        "category_group_code": "",
        "category_group_name": "",
        "category_name": " > ".join(
            filter(
                None,
                (
                    _clean_spaces(source.get("상권업종대분류명")),
                    _clean_spaces(source.get("상권업종중분류명")),
                    _clean_spaces(source.get("상권업종소분류명")),
                ),
            )
        ),
        "collection_types": primary_type,
        "image_url": "",
        "image_url_overridden": "f",
        "map_x": _clean_spaces(source.get("경도")),
        "map_y": _clean_spaces(source.get("위도")),
        "phone": "",
        "place_id": "",
        "place_name": build_place_name(source.get("상호명"), source.get("지점명")),
        "place_url": "",
        "primary_type": primary_type,
        "primary_type_name": primary_type_name,
        "road_address_name": _clean_spaces(source.get("도로명주소")),
        "source": "SMALL_BUSINESS",
        "synced_at": synced_at,
        "tourism_content_id": "",
    }
    if primary_type == "drugstore":
        output["category_name"] = "올리브영"
    if destination in {"accommodation", "hospital"}:
        output["place_type"] = destination.upper()
        output["skin_treatment_confidence"] = ""
        output["skin_treatment_signals"] = ""
    if destination == "attraction":
        values = constraints or {}
        fixed_constraints = ATTRACTION_CONSTRAINTS.get(primary_type)
        if fixed_constraints is not None:
            indoor, heat_source, massage_spot, walk_hard = fixed_constraints
            values = {
                "is_indoor": indoor,
                "is_heat_source": heat_source,
                "is_massage_spot": massage_spot,
                "walk_hard": walk_hard,
            }
        output.update(
            {
                "is_heat_source": str(values.get("is_heat_source", "f")),
                "is_indoor": str(values.get("is_indoor", "t")),
                "is_massage_spot": str(values.get("is_massage_spot", "f")),
                "is_na": "f",
                "walk_hard": str(values.get("walk_hard", "1")),
                "popularity": "",
            }
        )
    return output


AUDIT_FIELDS = [
    "source_place_id",
    "place_name",
    "source_category_code",
    "destination",
    "decision",
    "reason",
]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError(f"CSV header is missing: {path}")
        return list(reader.fieldnames), list(reader)


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _boolean(value: str | None, default: str) -> str:
    normalized = _clean_spaces(value).lower()
    if normalized in {"t", "true", "1", "y", "yes"}:
        return "t"
    if normalized in {"f", "false", "0", "n", "no"}:
        return "f"
    return default


def _approval_constraints(approval: Mapping[str, str]) -> dict[str, str]:
    walk_hard = _clean_spaces(approval.get("walk_hard"))
    if walk_hard not in {"1", "2", "3", "4", "5"}:
        raise ValueError("approval walk_hard must be an integer from 1 to 5")
    return {
        "is_indoor": _boolean(approval.get("is_indoor"), "t"),
        "is_heat_source": _boolean(approval.get("is_heat_source"), "f"),
        "is_massage_spot": _boolean(approval.get("is_massage_spot"), "f"),
        "walk_hard": walk_hard,
    }


def _is_valid_source_row(row: Mapping[str, str]) -> bool:
    if not build_place_name(row.get("상호명"), row.get("지점명")):
        return False
    if not _clean_spaces(row.get("지번주소")) or not _clean_spaces(row.get("도로명주소")):
        return False
    coord = _coordinates(row)
    if coord is None:
        return False
    longitude, latitude = coord
    return 126.7 <= longitude <= 127.3 and 37.4 <= latitude <= 37.8


def _urology_excluded(row: Mapping[str, str]) -> bool:
    return (
        _clean_spaces(row.get("상권업종소분류코드")) == "Q10204"
        and any(
            term in build_place_name(row.get("상호명"), row.get("지점명"))
            for term in UROLOGY_EXCLUDES
        )
    )


def _audit_row(
    source: Mapping[str, str],
    *,
    destination: str,
    decision: str,
    reason: str,
) -> dict[str, str]:
    return {
        "source_place_id": _clean_spaces(source.get("상가업소번호")),
        "place_name": build_place_name(source.get("상호명"), source.get("지점명")),
        "source_category_code": _clean_spaces(source.get("상권업종소분류코드")),
        "destination": destination,
        "decision": decision,
        "reason": reason,
    }


def _validate_outputs(
    outputs: Mapping[str, Sequence[Mapping[str, str]]],
    expected_fields: Mapping[str, Sequence[str]],
    output_dir: Path,
) -> dict[str, int]:
    header_mismatches = 0
    file_names = {
        "attraction": "small_business_attractions.csv",
        "accommodation": "small_business_accommodations.csv",
        "hospital": "small_business_hospitals.csv",
    }
    for destination, file_name in file_names.items():
        with (output_dir / file_name).open("r", encoding="utf-8-sig", newline="") as source:
            actual_fields = next(csv.reader(source))
        header_mismatches += actual_fields != list(expected_fields[destination])

    all_rows = [row for rows in outputs.values() for row in rows]
    nonblank_identifier_rows = sum(
        any(_clean_spaces(row.get(field)) for field in ("id", "place_id", "tourism_content_id"))
        for row in all_rows
    )
    invalid_required_rows = sum(
        not all(
            _clean_spaces(row.get(field))
            for field in (
                "place_name",
                "address_name",
                "road_address_name",
                "map_x",
                "map_y",
            )
        )
        or _coordinates(row) is None
        for row in all_rows
    )
    invalid_attraction_constraint_rows = sum(
        row.get("is_indoor") not in {"t", "f"}
        or row.get("is_heat_source") not in {"t", "f"}
        or row.get("is_massage_spot") not in {"t", "f"}
        or row.get("is_na") != "f"
        or row.get("walk_hard") not in {"1", "2", "3", "4", "5"}
        for row in outputs["attraction"]
    )
    duplicate_output_rows = 0
    for rows in outputs.values():
        index = EntityIndex()
        for row in rows:
            if index.find(row) is not None:
                duplicate_output_rows += 1
            else:
                index.add(row)
    return {
        "header_mismatches": int(header_mismatches),
        "nonblank_identifier_rows": nonblank_identifier_rows,
        "invalid_required_rows": invalid_required_rows,
        "invalid_attraction_constraint_rows": invalid_attraction_constraint_rows,
        "duplicate_output_rows": duplicate_output_rows,
    }


def transform_directory(
    *,
    input_dir: Path,
    output_dir: Path,
    source_path: Path,
    synced_at: str | None = None,
) -> dict[str, object]:
    """Transform one source snapshot and write schema-compatible output files."""
    synced_at = synced_at or datetime.now(timezone.utc).isoformat()
    attraction_fields, tourism_attractions = _read_csv(input_dir / "attractions.csv")
    accommodation_fields, tourism_accommodations = _read_csv(
        input_dir / "accommodations.csv"
    )
    hospital_fields, tourism_hospitals = _read_csv(input_dir / "hospitals.csv")
    _, approvals = _read_csv(input_dir / "kakao_cafe_massage_candidates.csv")
    approval_matcher = ApprovalMatcher(approvals)

    tourism_indexes = {
        "attraction": EntityIndex(tourism_attractions),
        "accommodation": EntityIndex(tourism_accommodations),
        "hospital": EntityIndex(tourism_hospitals),
    }
    small_business_indexes = {
        "attraction": EntityIndex(),
        "accommodation": EntityIndex(),
        "hospital": EntityIndex(),
    }
    outputs: dict[str, list[dict[str, str]]] = {
        "attraction": [],
        "accommodation": [],
        "hospital": [],
    }
    audit: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    included_by_destination: Counter[str] = Counter()
    included_by_primary_type: Counter[str] = Counter()
    excluded_by_reason: Counter[str] = Counter()
    used_approvals: set[int] = set()

    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError(f"CSV header is missing: {source_path}")
        for source_row in reader:
            counts["source_rows"] += 1
            code = _clean_spaces(source_row.get("상권업종소분류코드"))
            name = build_place_name(source_row.get("상호명"), source_row.get("지점명"))
            is_candidate = (
                code in ATTRACTION_CODES
                or code in ACCOMMODATION_CODES
                or code in HOSPITAL_CODES
                or "올리브영" in name
            )
            if not is_candidate:
                continue
            counts["candidate_rows"] += 1

            if _urology_excluded(source_row):
                reason = "urology_name"
                excluded_by_reason[reason] += 1
                audit.append(
                    _audit_row(
                        source_row, destination="hospital", decision="excluded", reason=reason
                    )
                )
                continue
            classification = classify_source_row(source_row)
            if classification is None:
                reason = "unselected_category"
                excluded_by_reason[reason] += 1
                audit.append(
                    _audit_row(
                        source_row, destination="", decision="excluded", reason=reason
                    )
                )
                continue
            destination, primary_type, primary_type_name = classification
            if not _is_valid_source_row(source_row):
                reason = "invalid_required_fields"
                excluded_by_reason[reason] += 1
                audit.append(
                    _audit_row(
                        source_row,
                        destination=destination,
                        decision="excluded",
                        reason=reason,
                    )
                )
                continue

            constraints: dict[str, str] | None = None
            if code in ATTRACTION_CODES and "올리브영" not in name:
                match = approval_matcher.match(source_row)
                if match.status != "matched" or match.approval is None:
                    reason = f"approval_{match.status}"
                    excluded_by_reason[reason] += 1
                    audit.append(
                        _audit_row(
                            source_row,
                            destination=destination,
                            decision="excluded",
                            reason=reason,
                        )
                    )
                    continue
                if match.approval_index is None:
                    raise RuntimeError("matched approval is missing its row index")
                if match.approval_index in used_approvals:
                    reason = "approval_source_duplicate"
                    excluded_by_reason[reason] += 1
                    audit.append(
                        _audit_row(
                            source_row,
                            destination=destination,
                            decision="excluded",
                            reason=reason,
                        )
                    )
                    continue
                constraints = _approval_constraints(match.approval)
                used_approvals.add(match.approval_index)
                if primary_type == "massage_spot" and (
                    constraints["is_heat_source"] == "t"
                    and constraints["is_massage_spot"] == "t"
                ):
                    primary_type = "spa"
            elif primary_type == "drugstore":
                constraints = {
                    "is_indoor": "t",
                    "is_heat_source": "f",
                    "is_massage_spot": "f",
                    "walk_hard": "2",
                }

            output_row = make_output_row(
                source_row,
                destination=destination,
                primary_type=primary_type,
                primary_type_name=primary_type_name,
                constraints=constraints,
                synced_at=synced_at,
            )
            if tourism_indexes[destination].find(output_row) is not None:
                reason = "tourism_duplicate"
                excluded_by_reason[reason] += 1
                audit.append(
                    _audit_row(
                        source_row,
                        destination=destination,
                        decision="excluded",
                        reason=reason,
                    )
                )
                continue
            if small_business_indexes[destination].find(output_row) is not None:
                reason = "small_business_duplicate"
                excluded_by_reason[reason] += 1
                audit.append(
                    _audit_row(
                        source_row,
                        destination=destination,
                        decision="excluded",
                        reason=reason,
                    )
                )
                continue

            outputs[destination].append(output_row)
            small_business_indexes[destination].add(output_row)
            included_by_destination[destination] += 1
            included_by_primary_type[primary_type] += 1
            audit.append(
                _audit_row(
                    source_row,
                    destination=destination,
                    decision="included",
                    reason="included",
                )
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output_dir / "small_business_attractions.csv",
        attraction_fields,
        outputs["attraction"],
    )
    _write_csv(
        output_dir / "small_business_accommodations.csv",
        accommodation_fields,
        outputs["accommodation"],
    )
    _write_csv(
        output_dir / "small_business_hospitals.csv",
        hospital_fields,
        outputs["hospital"],
    )
    _write_csv(output_dir / "transformation_audit.csv", AUDIT_FIELDS, audit)

    expected_fields = {
        "attraction": attraction_fields,
        "accommodation": accommodation_fields,
        "hospital": hospital_fields,
    }

    report: dict[str, object] = {
        "source_rows": counts["source_rows"],
        "candidate_rows": counts["candidate_rows"],
        "included": sum(included_by_destination.values()),
        "included_by_destination": dict(sorted(included_by_destination.items())),
        "included_by_primary_type": dict(sorted(included_by_primary_type.items())),
        "excluded_by_reason": dict(sorted(excluded_by_reason.items())),
        "validation": _validate_outputs(outputs, expected_fields, output_dir),
    }
    (output_dir / "transformation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _default_source_path(input_dir: Path) -> Path:
    matches = sorted(input_dir.glob("*상가(상권)정보*202606.csv"))
    if len(matches) != 1:
        raise ValueError(f"expected one small-business source CSV, found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/newData"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/newData/processed")
    )
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    source_path = args.source or _default_source_path(args.input_dir)
    report = transform_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        source_path=source_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
