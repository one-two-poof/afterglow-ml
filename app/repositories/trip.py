from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.trip import DailySchedule, RecommendedCourse, SelectedCourse


class RecommendedCourseRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, course: RecommendedCourse) -> RecommendedCourse:
        self.db.add(course)
        self.db.flush()
        return course

    def get_by_id(self, recommended_course_id: int) -> RecommendedCourse | None:
        statement = (
            select(RecommendedCourse)
            .where(RecommendedCourse.id == recommended_course_id)
            .options(
                selectinload(RecommendedCourse.treatments),
                selectinload(RecommendedCourse.daily_schedules).selectinload(
                    DailySchedule.places
                ),
            )
        )
        return self.db.scalar(statement)

    def get_owned_by_id(
        self,
        recommended_course_id: int,
        user_id: int,
    ) -> RecommendedCourse | None:
        statement = select(RecommendedCourse).where(
            RecommendedCourse.id == recommended_course_id,
            RecommendedCourse.user_id == user_id,
        )
        return self.db.scalar(statement)

    def list_by_user_id(
        self,
        user_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RecommendedCourse]:
        statement = (
            select(RecommendedCourse)
            .where(RecommendedCourse.user_id == user_id)
            .options(
                selectinload(RecommendedCourse.treatments),
                selectinload(RecommendedCourse.daily_schedules).selectinload(
                    DailySchedule.places
                ),
            )
            .order_by(
                RecommendedCourse.requested_at.desc(),
                RecommendedCourse.rank.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class SelectedCourseRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, selection: SelectedCourse) -> SelectedCourse:
        self.db.add(selection)
        self.db.flush()
        return selection

    def get_by_id(self, selected_course_id: int) -> SelectedCourse | None:
        return self.db.get(SelectedCourse, selected_course_id)

    def get_by_user_and_course(
        self,
        user_id: int,
        recommended_course_id: int,
    ) -> SelectedCourse | None:
        statement = select(SelectedCourse).where(
            SelectedCourse.user_id == user_id,
            SelectedCourse.recommended_course_id == recommended_course_id,
        )
        return self.db.scalar(statement)

    def list_by_user_id(
        self,
        user_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SelectedCourse]:
        statement = (
            select(SelectedCourse)
            .where(SelectedCourse.user_id == user_id)
            .order_by(SelectedCourse.selected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())
