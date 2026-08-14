import unittest

from app.models.recommendation import Anchor, Place, TreatmentContext
from app.rule.candidate_service import CandidateService
from app.rule.course_service import CourseService
from app.rule.place_score import calculate_place_score, walk_score
from app.rule.treatment_filter import FilterStatus, evaluate_treatments, treatment_filter


ANCHOR = Anchor("anchor", 37.5, 127.0)


def treatment(name="피부관리", days_after=8):
    return TreatmentContext(name, days_after)


class MemoryRepository:
    def __init__(self, places):
        self.places = places

    def list_places(self):
        return self.places


def place(
    place_id="P1",
    *,
    latitude=37.501,
    longitude=127.0,
    category="cultural_facility",
    indoor=True,
    walk_hard=1,
    category_name="",
):
    return Place(
        place_id, place_id, category, latitude, longitude, indoor, walk_hard,
        category_name=category_name,
    )


class TreatmentPolicyTests(unittest.TestCase):
    def test_laser_outdoor_changes_by_day(self):
        outdoor = place(category="tourist_attraction", indoor=False)
        self.assertEqual(treatment_filter("피부레이저", outdoor, 3)[0], FilterStatus.BLOCK)
        self.assertEqual(treatment_filter("피부레이저", outdoor, 4)[0], FilterStatus.PENALTY)
        self.assertEqual(treatment_filter("피부레이저", outdoor, 8)[0], FilterStatus.NORMAL)

    def test_botox_high_activity_changes_by_day(self):
        active = place(walk_hard=5)
        self.assertEqual(treatment_filter("보톡스", active, 0)[0], FilterStatus.BLOCK)
        self.assertEqual(treatment_filter("보톡스", active, 1)[0], FilterStatus.PENALTY)
        self.assertEqual(treatment_filter("보톡스", active, 8)[0], FilterStatus.NORMAL)

    def test_hair_removal_does_not_block_high_activity(self):
        active = place(walk_hard=5)
        self.assertEqual(treatment_filter("제모", active, 0)[0], FilterStatus.NORMAL)

    def test_strongest_overlapping_rule_wins(self):
        outdoor_active = place(category="tourist_attraction", indoor=False, walk_hard=5)
        status, signals = treatment_filter("피부레이저", outdoor_active, 2)
        self.assertEqual(status, FilterStatus.BLOCK)
        self.assertEqual(set(signals), {"HIGH_ACTIVITY", "OUTDOOR_EXPOSURE"})

    def test_massage_pressure_policy(self):
        massage = place(category_name="생활서비스 > 마사지")
        self.assertEqual(treatment_filter("필러", massage, 3)[0], FilterStatus.BLOCK)
        self.assertEqual(treatment_filter("필러", massage, 4)[0], FilterStatus.NORMAL)
        self.assertEqual(treatment_filter("리프팅", massage, 7)[0], FilterStatus.PENALTY)
        self.assertEqual(treatment_filter("리프팅", massage, 8)[0], FilterStatus.NORMAL)

    def test_multiple_treatments_use_strongest_status(self):
        outdoor = place(category="tourist_attraction", indoor=False)
        status, _, evaluations = evaluate_treatments(
            [treatment("제모", 2), treatment("피부레이저", 2)], outdoor
        )
        self.assertEqual(status, FilterStatus.BLOCK)
        self.assertEqual(
            {item["treatment"]: item["status"] for item in evaluations},
            {"제모": "PENALTY", "피부레이저": "BLOCK"},
        )


class PlaceRecommendationTests(unittest.TestCase):
    def test_nearby_indoor_low_intensity_place_scores_high(self):
        item = place()
        status, _ = treatment_filter("피부레이저", item, 2)
        score = calculate_place_score("휴식", 2, item, status, 0.2)
        self.assertEqual(status, FilterStatus.NORMAL)
        self.assertGreaterEqual(score.place_score, 90)

    def test_low_preference_high_walk_hard_gets_strong_penalty(self):
        self.assertEqual(walk_score(1, 5), 10)

    def test_high_preference_does_not_penalize_low_walk_hard(self):
        self.assertEqual(walk_score(5, 1), 100)

    def test_blocked_place_is_removed(self):
        blocked = place(category="tourist_attraction", indoor=False, walk_hard=5)
        service = CandidateService(MemoryRepository([blocked]))
        result = service.recommend(
            anchor=ANCHOR, treatments=[treatment("피부레이저", 2)],
            user_purpose="휴식", user_walk_preference=2, limit=20,
        )
        self.assertEqual(result, [])

    def test_place_beyond_radius_is_removed(self):
        service = CandidateService(MemoryRepository([place(latitude=37.56)]))
        result = service.recommend(
            anchor=ANCHOR, treatments=[treatment()],
            user_purpose="휴식", user_walk_preference=2, limit=20,
        )
        self.assertEqual(result, [])


class CourseRecommendationTests(unittest.TestCase):
    def _service(self, places):
        return CourseService(CandidateService(MemoryRepository(places)))

    def test_course_has_three_places_and_max_two_same_category(self):
        places = [
            place("C1", latitude=37.501),
            place("C2", latitude=37.502),
            place("D1", latitude=37.503, category="drugstore"),
            place("D2", latitude=37.504, category="drugstore"),
        ]
        courses = self._service(places).recommend(
            anchor=ANCHOR, treatments=[treatment()],
            user_purpose="휴식", user_walk_preference=3, top_n=3,
        )
        self.assertTrue(courses)
        for course in courses:
            categories = [p["place_category"] for p in course["places"]]
            self.assertEqual(len(categories), 3)
            self.assertLessEqual(max(categories.count(c) for c in set(categories)), 2)

    def test_course_uses_shortest_order_and_distance_limits(self):
        places = [
            place("A", latitude=37.501, category="cultural_facility"),
            place("B", latitude=37.502, category="drugstore"),
            place("C", latitude=37.503, category="department_store"),
        ]
        course = self._service(places).recommend(
            anchor=ANCHOR, treatments=[treatment()],
            user_purpose="휴식", user_walk_preference=3, top_n=1,
        )[0]
        self.assertEqual([p["place_id"] for p in course["places"]], ["A", "B", "C"])
        self.assertLessEqual(course["total_distance_km"], 5.0)
        self.assertTrue(all(p["distance_from_previous_km"] <= 2.0 for p in course["places"]))

    def test_top_courses_share_at_most_one_place(self):
        places = [
            place("C1", latitude=37.501), place("C2", latitude=37.502),
            place("D1", latitude=37.503, category="drugstore"),
            place("D2", latitude=37.504, category="drugstore"),
            place("B1", latitude=37.505, category="department_store"),
            place("B2", latitude=37.506, category="department_store"),
        ]
        courses = self._service(places).recommend(
            anchor=ANCHOR, treatments=[treatment()],
            user_purpose="휴식", user_walk_preference=3, top_n=3,
        )
        for index, first in enumerate(courses):
            first_ids = {p["place_id"] for p in first["places"]}
            for second in courses[index + 1:]:
                second_ids = {p["place_id"] for p in second["places"]}
                self.assertLessEqual(len(first_ids & second_ids), 1)


if __name__ == "__main__":
    unittest.main()
