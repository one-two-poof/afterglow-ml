from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship

from app.config.database import Base


class RecommendedCourse(Base):
    __tablename__ = "trip_recommended_courses"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    requested_at = Column(TIMESTAMP(timezone=True), nullable=False)
    rank = Column(Integer, nullable=False)
    course_id = Column(String(32), nullable=False)
    total_distance_km = Column(Numeric(6, 2), nullable=False)

    treatments = relationship(
        "CourseTreatment",
        back_populates="recommended_course",
        cascade="all, delete-orphan",
    )
    daily_schedules = relationship(
        "DailySchedule",
        back_populates="recommended_course",
        cascade="all, delete-orphan",
        order_by="DailySchedule.schedule_date",
    )
    selections = relationship("SelectedCourse", back_populates="recommended_course")


class CourseTreatment(Base):
    __tablename__ = "trip_course_treatments"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    recommended_course_id = Column(
        BigInteger,
        ForeignKey("trip_recommended_courses.id"),
        nullable=False,
    )
    name = Column(String(128), nullable=False)
    treatment_date = Column(Date, nullable=False)

    recommended_course = relationship("RecommendedCourse", back_populates="treatments")


class DailySchedule(Base):
    __tablename__ = "trip_daily_schedules"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    recommended_course_id = Column(
        BigInteger,
        ForeignKey("trip_recommended_courses.id"),
        nullable=False,
    )
    schedule_date = Column(Date, nullable=False)
    start_location_name = Column(String(256), nullable=False)
    start_location_map_x = Column(Numeric(12, 8), nullable=False)
    start_location_map_y = Column(Numeric(12, 8), nullable=False)

    recommended_course = relationship(
        "RecommendedCourse", back_populates="daily_schedules"
    )
    places = relationship(
        "DailySchedulePlace",
        back_populates="daily_schedule",
        cascade="all, delete-orphan",
        order_by="DailySchedulePlace.visit_order",
    )


class DailySchedulePlace(Base):
    __tablename__ = "trip_daily_schedule_places"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    daily_schedule_id = Column(
        BigInteger,
        ForeignKey("trip_daily_schedules.id"),
        nullable=False,
    )
    visit_order = Column(Integer, nullable=False)
    place_name = Column(String(256), nullable=False)
    place_category = Column(String(64), nullable=False)
    map_x = Column(Numeric(12, 8), nullable=False)
    map_y = Column(Numeric(12, 8), nullable=False)
    is_indoor = Column(Boolean, nullable=False)
    walk_hard = Column(Integer, nullable=False)
    dist_to_prev_km = Column(Numeric(6, 2), nullable=False)

    daily_schedule = relationship("DailySchedule", back_populates="places")


class SelectedCourse(Base):
    __tablename__ = "trip_selected_courses"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    recommended_course_id = Column(
        BigInteger,
        ForeignKey("trip_recommended_courses.id"),
        nullable=False,
    )
    selected_at = Column(TIMESTAMP(timezone=True), nullable=False)

    recommended_course = relationship("RecommendedCourse", back_populates="selections")
