from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.trip import SelectedCourse
from app.repositories.trip import (
    RecommendedCourseRepository,
    SelectedCourseRepository,
)


class CourseSelectionNotFoundError(ValueError):
    pass


def save_selected_course(*, course_id: int, user_id: int, db: Session) -> None:
    course_repository = RecommendedCourseRepository(db)
    selected_repository = SelectedCourseRepository(db)

    course = course_repository.get_owned_by_id(course_id, user_id)
    if course is None:
        raise CourseSelectionNotFoundError

    existing = selected_repository.get_by_user_and_course(user_id, course_id)
    if existing is not None:
        return

    selected_repository.add(
        SelectedCourse(
            user_id=user_id,
            recommended_course_id=course_id,
            selected_at=datetime.now(timezone.utc),
        )
    )
