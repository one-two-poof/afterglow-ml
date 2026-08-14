import unittest

from pydantic import ValidationError

from app.rule.inference import resolve_treatments
from app.schemas.recommendation import PlaceRecommendationRequest


BASE = {
    "title": "anchor",
    "user_purpose": "휴식",
    "user_walk_preference": 2,
    "anchor_latitude": 37.5,
    "anchor_longitude": 127.03,
}


class TreatmentRequestTests(unittest.TestCase):
    def test_legacy_single_treatment_is_preserved(self):
        request = PlaceRecommendationRequest(
            **BASE, treatment="피부레이저", days_after=3
        )
        contexts = resolve_treatments(request)
        self.assertEqual([(c.treatment, c.days_after) for c in contexts], [("피부레이저", 3)])

    def test_same_day_package_creates_two_active_treatments(self):
        request = PlaceRecommendationRequest(
            **BASE,
            recommendation_at="2026-08-14T16:00:00+09:00",
            treatments=[
                {
                    "treatment": "보톡스",
                    "scheduled_at": "2026-08-14T11:00:00+09:00",
                    "package_id": "PKG001",
                },
                {
                    "treatment": "필러",
                    "scheduled_at": "2026-08-14T11:00:00+09:00",
                    "package_id": "PKG001",
                },
            ],
        )
        contexts = resolve_treatments(request)
        self.assertEqual([(c.treatment, c.days_after) for c in contexts], [("보톡스", 0), ("필러", 0)])
        self.assertTrue(all(c.package_id == "PKG001" for c in contexts))

    def test_multi_day_trip_calculates_each_day_and_skips_future_treatment(self):
        request = PlaceRecommendationRequest(
            **BASE,
            recommendation_at="2026-08-16T16:00:00+09:00",
            treatments=[
                {"treatment": "보톡스", "scheduled_at": "2026-08-14T11:00:00+09:00"},
                {"treatment": "피부레이저", "scheduled_at": "2026-08-16T14:00:00+09:00"},
                {"treatment": "제모", "scheduled_at": "2026-08-17T10:00:00+09:00"},
            ],
        )
        contexts = resolve_treatments(request)
        self.assertEqual(
            [(c.treatment, c.days_after) for c in contexts],
            [("보톡스", 2), ("피부레이저", 0)],
        )

    def test_rejects_mixed_legacy_and_multiple_formats(self):
        with self.assertRaises(ValidationError):
            PlaceRecommendationRequest(
                **BASE,
                treatment="보톡스",
                days_after=0,
                treatments=[{"treatment": "필러", "days_after": 0}],
            )

    def test_scheduled_event_requires_recommendation_time(self):
        with self.assertRaises(ValidationError):
            PlaceRecommendationRequest(
                **BASE,
                treatments=[
                    {"treatment": "필러", "scheduled_at": "2026-08-14T11:00:00+09:00"}
                ],
            )


if __name__ == "__main__":
    unittest.main()
