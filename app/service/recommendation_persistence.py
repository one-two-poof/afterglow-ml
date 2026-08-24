from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.trip import (
    CourseTreatment,
    DailySchedule as DailyScheduleModel,
    DailySchedulePlace,
    RecommendedCourse as RecommendedCourseModel,
)
from app.repositories.trip import RecommendedCourseRepository
from app.schemas.recommendation import RecommendationResponse


def save_recommendations(
    response: RecommendationResponse,
    *,
    user_id: int,
    db: Session,
) -> RecommendationResponse:
    courses = response.daily_recommendations
    if len(courses) != 3 or sorted(course.rank for course in courses) != [1, 2, 3]:
        raise ValueError("추천 코스는 정확히 3개여야 합니다.")

    # All three ranks share one timestamp so they can be treated as one request
    # batch even though the schema has no explicit request/batch table.
    requested_at = datetime.now(timezone.utc)
    repository = RecommendedCourseRepository(db)

    for course in courses:
        record = RecommendedCourseModel(
            user_id=user_id,
            requested_at=requested_at,
            rank=course.rank,
            course_id=course.course_id,
            total_distance_km=course.total_distance_km,
            treatments=[
                CourseTreatment(
                    name=getattr(treatment.name, "value", treatment.name),
                    treatment_date=treatment.date,
                )
                for treatment in course.treatment
            ],
            daily_schedules=[
                DailyScheduleModel(
                    schedule_date=schedule.date,
                    start_location_name=schedule.start_location.name,
                    start_location_map_x=schedule.start_location.mapX,
                    start_location_map_y=schedule.start_location.mapY,
                    places=[
                        DailySchedulePlace(
                            visit_order=place.visit_order,
                            place_name=place.place_name,
                            place_category=place.place_category,
                            map_x=place.mapX,
                            map_y=place.mapY,
                            is_indoor=bool(place.is_indoor),
                            walk_hard=place.walk_hard,
                            dist_to_prev_km=place.dist_to_prev_km,
                        )
                        for place in schedule.places
                    ],
                )
                for schedule in course.daily_schedules
            ],
        )
        # flush() assigns the identity before the API transaction commits, so the
        # generated ID can be returned in the same response.
        repository.add(record)
        course.recommended_course_id = record.id
        course.course_id = str(record.id)
        record.course_id = course.course_id

    return response
