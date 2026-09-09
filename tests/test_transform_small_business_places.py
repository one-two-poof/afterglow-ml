import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.transform_small_business_places import (
    ApprovalMatcher,
    build_place_name,
    classify_source_row,
    is_same_place,
    make_output_row,
    transform_directory,
)


def source_row(**overrides):
    row = {
        "상가업소번호": "SRC-1",
        "상호명": "테스트상점",
        "지점명": "강남점",
        "상권업종대분류명": "음식점업",
        "상권업종중분류명": "비알코올 음료점업",
        "상권업종소분류코드": "I21201",
        "상권업종소분류명": "카페",
        "지번주소": "서울특별시 강남구 역삼동 1",
        "도로명주소": "서울특별시 강남구 테헤란로 1",
        "경도": "127.01",
        "위도": "37.50",
    }
    row.update(overrides)
    return row


class PlaceNameTests(unittest.TestCase):
    def test_appends_branch_name(self):
        self.assertEqual(build_place_name("눅스커피", "강남점"), "눅스커피 강남점")

    def test_ignores_korea_branch(self):
        self.assertEqual(build_place_name("눅스커피", "코리아"), "눅스커피")

    def test_does_not_append_a_branch_already_in_the_name(self):
        self.assertEqual(
            build_place_name("눅스커피 강남점", "강남점"),
            "눅스커피 강남점",
        )


class ClassificationTests(unittest.TestCase):
    def test_classifies_approved_attraction_categories(self):
        expected = {
            "I21201": ("attraction", "cafe", "카페"),
            "S20801": ("attraction", "heat_source", "찜질방/사우나"),
            "S20802": ("attraction", "massage_spot", "안마/스파"),
        }
        for code, result in expected.items():
            with self.subTest(code=code):
                self.assertEqual(
                    classify_source_row(source_row(상권업종소분류코드=code)),
                    result,
                )

    def test_olive_young_overrides_the_source_category(self):
        row = source_row(
            상호명="CJ올리브영",
            지점명="홍대점",
            상권업종소분류코드="G21503",
        )
        self.assertEqual(
            classify_source_row(row),
            ("attraction", "drugstore", "드럭스토어"),
        )

    def test_classifies_allowed_accommodations(self):
        for code in ("I10101", "I10102", "I10103"):
            with self.subTest(code=code):
                self.assertEqual(
                    classify_source_row(source_row(상권업종소분류코드=code)),
                    ("accommodation", "accommodation", "숙소"),
                )

    def test_rejects_urology_signals_from_mixed_hospital_code(self):
        row = source_row(
            상호명="서울비뇨기과의원",
            지점명="",
            상권업종소분류코드="Q10204",
        )
        self.assertIsNone(classify_source_row(row))

    def test_classifies_skin_and_plastic_surgery_hospitals(self):
        skin = source_row(
            상호명="맑은피부과의원",
            지점명="",
            상권업종소분류코드="Q10204",
        )
        plastic = source_row(
            상호명="서울성형외과의원",
            지점명="",
            상권업종소분류코드="Q10208",
        )
        self.assertEqual(
            classify_source_row(skin), ("hospital", "hospital", "병원")
        )
        self.assertEqual(
            classify_source_row(plastic), ("hospital", "hospital", "병원")
        )

    def test_rejects_unselected_categories(self):
        self.assertIsNone(
            classify_source_row(source_row(상권업종소분류코드="G21501"))
        )


class OutputMappingTests(unittest.TestCase):
    def test_attraction_constraints_follow_primary_type_rules(self):
        expected_by_type = {
            "cafe": ("t", "f", "f", "1"),
            "heat_source": ("t", "t", "f", "1"),
            "massage_spot": ("t", "f", "t", "1"),
            "spa": ("t", "t", "t", "1"),
            "drugstore": ("t", "f", "f", "2"),
        }
        for primary_type, expected in expected_by_type.items():
            with self.subTest(primary_type=primary_type):
                output = make_output_row(
                    source_row(),
                    destination="attraction",
                    primary_type=primary_type,
                    primary_type_name=primary_type,
                    constraints={
                        "is_indoor": "f",
                        "is_heat_source": "f",
                        "is_massage_spot": "f",
                        "walk_hard": "5",
                    },
                    synced_at="2026-09-10T00:00:00+00:00",
                )
                actual = (
                    output["is_indoor"],
                    output["is_heat_source"],
                    output["is_massage_spot"],
                    output["walk_hard"],
                )
                self.assertEqual(actual, expected)

    def test_attraction_identifiers_are_blank(self):
        output = make_output_row(
            source_row(),
            destination="attraction",
            primary_type="cafe",
            primary_type_name="카페",
            constraints={
                "is_indoor": "t",
                "is_heat_source": "f",
                "is_massage_spot": "f",
                "walk_hard": "1",
            },
            synced_at="2026-09-10T00:00:00+00:00",
        )
        self.assertEqual(output["id"], "")
        self.assertEqual(output["place_id"], "")
        self.assertEqual(output["tourism_content_id"], "")
        self.assertEqual(output["popularity"], "")
        self.assertEqual(output["source"], "SMALL_BUSINESS")
        self.assertEqual(output["place_name"], "테스트상점 강남점")
        self.assertEqual(output["map_x"], "127.01")
        self.assertEqual(output["map_y"], "37.50")

    def test_drugstore_category_name_is_olive_young(self):
        output = make_output_row(
            source_row(상호명="CJ올리브영", 지점명="강남점"),
            destination="attraction",
            primary_type="drugstore",
            primary_type_name="드럭스토어",
            constraints={
                "is_indoor": "t",
                "is_heat_source": "f",
                "is_massage_spot": "f",
                "walk_hard": "2",
            },
            synced_at="2026-09-10T00:00:00+00:00",
        )
        self.assertEqual(output["category_name"], "올리브영")


class ApprovalMatchingTests(unittest.TestCase):
    def approval(self, **overrides):
        row = {
            "place_id": "K1",
            "place_name": "눅스커피 강남점",
            "address_name": "서울 강남구 역삼동 1",
            "road_address_name": "서울 강남구 테헤란로 1",
            "map_x": "127.01",
            "map_y": "37.50",
            "is_indoor": "t",
            "is_heat_source": "f",
            "is_massage_spot": "f",
            "walk_hard": "1",
        }
        row.update(overrides)
        return row

    def test_matches_normalized_name_and_address(self):
        matcher = ApprovalMatcher([self.approval()])
        result = matcher.match(source_row(상호명="눅스커피", 지점명="강남점"))
        self.assertEqual(result.status, "matched")
        self.assertEqual(result.approval["place_id"], "K1")

    def test_matches_similar_name_within_thirty_metres(self):
        matcher = ApprovalMatcher(
            [self.approval(place_name="눅스 커피 강남", map_x="127.0101")]
        )
        result = matcher.match(
            source_row(
                상호명="눅스커피",
                지점명="강남점",
                도로명주소="서울특별시 강남구 다른로 9",
                지번주소="서울특별시 강남구 다른동 9",
            )
        )
        self.assertEqual(result.status, "matched")

    def test_does_not_match_same_address_with_a_different_name(self):
        matcher = ApprovalMatcher([self.approval(place_name="완전히다른카페")])
        result = matcher.match(source_row())
        self.assertEqual(result.status, "not_matched")

    def test_reports_equally_ranked_multiple_matches_as_ambiguous(self):
        matcher = ApprovalMatcher(
            [self.approval(place_id="K1"), self.approval(place_id="K2")]
        )
        result = matcher.match(source_row(상호명="눅스커피", 지점명="강남점"))
        self.assertEqual(result.status, "ambiguous")


class DuplicateTests(unittest.TestCase):
    def entity(self, **overrides):
        row = {
            "place_name": "서울호텔 강남점",
            "address_name": "서울 강남구 역삼동 1",
            "road_address_name": "서울 강남구 테헤란로 1",
            "map_x": "127.01",
            "map_y": "37.50",
        }
        row.update(overrides)
        return row

    def test_same_normalized_name_and_road_address_is_duplicate(self):
        tourism = self.entity()
        small_business = self.entity(
            place_name="서울 호텔 강남점",
            road_address_name="서울특별시 강남구 테헤란로 1",
        )
        self.assertTrue(is_same_place(tourism, small_business))

    def test_nearby_similar_names_are_duplicates(self):
        tourism = self.entity(place_name="서울호텔 강남")
        small_business = self.entity(map_x="127.0101")
        self.assertTrue(is_same_place(tourism, small_business))

    def test_same_address_with_different_name_is_not_duplicate(self):
        tourism = self.entity(place_name="서울호텔")
        small_business = self.entity(place_name="테헤란카페")
        self.assertFalse(is_same_place(tourism, small_business))


class DirectoryTransformationTests(unittest.TestCase):
    ATTRACTION_FIELDS = [
        "id", "address_name", "category_group_code", "category_group_name",
        "category_name", "collection_types", "image_url", "image_url_overridden",
        "is_heat_source", "is_indoor", "is_massage_spot", "is_na", "map_x",
        "map_y", "phone", "place_id", "place_name", "place_url", "primary_type",
        "primary_type_name", "road_address_name", "source", "synced_at", "walk_hard",
        "tourism_content_id", "popularity",
    ]
    START_FIELDS = [
        "id", "address_name", "category_group_code", "category_group_name",
        "category_name", "collection_types", "image_url", "image_url_overridden",
        "map_x", "map_y", "phone", "place_id", "place_name", "place_type",
        "place_url", "primary_type", "primary_type_name", "road_address_name",
        "skin_treatment_confidence", "skin_treatment_signals", "source", "synced_at",
        "tourism_content_id",
    ]

    def write_csv(self, path, fields, rows):
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_writes_three_schema_compatible_outputs_and_audit_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_csv(root / "attractions.csv", self.ATTRACTION_FIELDS, [])
            self.write_csv(
                root / "accommodations.csv",
                self.START_FIELDS,
                [{
                    "place_name": "중복호텔 강남점",
                    "address_name": "서울 강남구 역삼동 1",
                    "road_address_name": "서울 강남구 테헤란로 1",
                    "map_x": "127.01",
                    "map_y": "37.50",
                }],
            )
            self.write_csv(root / "hospitals.csv", self.START_FIELDS, [])
            approval_fields = [
                "place_id", "place_name", "address_name", "road_address_name",
                "map_x", "map_y", "is_indoor", "is_heat_source",
                "is_massage_spot", "walk_hard",
            ]
            self.write_csv(
                root / "kakao_cafe_massage_candidates.csv",
                approval_fields,
                [{
                    "place_id": "K1",
                    "place_name": "승인카페 강남점",
                    "address_name": "서울 강남구 역삼동 2",
                    "road_address_name": "서울 강남구 테헤란로 2",
                    "map_x": "127.011",
                    "map_y": "37.501",
                    "is_indoor": "t",
                    "is_heat_source": "f",
                    "is_massage_spot": "f",
                    "walk_hard": "1",
                }],
            )
            raw_fields = list(source_row())
            rows = [
                source_row(
                    상가업소번호="CAFE",
                    상호명="승인카페",
                    지점명="강남점",
                    지번주소="서울특별시 강남구 역삼동 2",
                    도로명주소="서울특별시 강남구 테헤란로 2",
                    경도="127.011",
                    위도="37.501",
                ),
                source_row(
                    상가업소번호="OLIVE",
                    상호명="올리브영",
                    지점명="역삼점",
                    상권업종소분류코드="G22199",
                ),
                source_row(
                    상가업소번호="DUP-HOTEL",
                    상호명="중복호텔",
                    지점명="강남점",
                    상권업종소분류코드="I10101",
                ),
                source_row(
                    상가업소번호="HOSPITAL",
                    상호명="미소성형외과의원",
                    지점명="",
                    상권업종소분류코드="Q10208",
                ),
                source_row(
                    상가업소번호="UROLOGY",
                    상호명="서울비뇨기과의원",
                    지점명="",
                    상권업종소분류코드="Q10204",
                ),
            ]
            self.write_csv(root / "source.csv", raw_fields, rows)

            output = root / "processed"
            report = transform_directory(
                input_dir=root,
                output_dir=output,
                source_path=root / "source.csv",
                synced_at="2026-09-10T00:00:00+00:00",
            )

            with (output / "small_business_attractions.csv").open(
                encoding="utf-8-sig", newline=""
            ) as source:
                reader = csv.DictReader(source)
                attractions = list(reader)
                self.assertEqual(reader.fieldnames, self.ATTRACTION_FIELDS)
            with (output / "small_business_accommodations.csv").open(
                encoding="utf-8-sig", newline=""
            ) as source:
                accommodations = list(csv.DictReader(source))
            with (output / "small_business_hospitals.csv").open(
                encoding="utf-8-sig", newline=""
            ) as source:
                hospitals = list(csv.DictReader(source))

            self.assertEqual(
                [row["place_name"] for row in attractions],
                ["승인카페 강남점", "올리브영 역삼점"],
            )
            self.assertEqual(accommodations, [])
            self.assertEqual([row["place_name"] for row in hospitals], ["미소성형외과의원"])
            self.assertEqual(report["included"], 3)
            self.assertEqual(report["included_by_primary_type"]["cafe"], 1)
            self.assertEqual(report["included_by_primary_type"]["drugstore"], 1)
            self.assertEqual(report["included_by_primary_type"]["hospital"], 1)
            self.assertEqual(report["excluded_by_reason"]["tourism_duplicate"], 1)
            self.assertEqual(report["excluded_by_reason"]["urology_name"], 1)
            self.assertEqual(
                report["validation"],
                {
                    "header_mismatches": 0,
                    "nonblank_identifier_rows": 0,
                    "invalid_required_rows": 0,
                    "invalid_attraction_constraint_rows": 0,
                    "duplicate_output_rows": 0,
                },
            )
            self.assertTrue((output / "transformation_audit.csv").exists())
            saved_report = json.loads(
                (output / "transformation_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved_report, report)


if __name__ == "__main__":
    unittest.main()
