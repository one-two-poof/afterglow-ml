"""HTTP 표현과 분리된 추천 도메인 내부 데이터 모델을 정의한다."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    """병원·숙소 또는 사용자 지정 코스 출발점이다."""

    name: str
    latitude: float
    longitude: float
    anchor_type: str | None = None


@dataclass(frozen=True)
class Place:
    """추천 규칙 계산에 필요한 최소 장소 속성 모음이다."""

    place_id: str
    place_name: str
    place_category: str
    latitude: float
    longitude: float
    is_indoor: bool
    walk_hard: int
    category_name: str = ""
    place_url: str = ""


@dataclass(frozen=True)
class TreatmentContext:
    """특정 추천 시점에서 계산된 시술명과 경과일 정보다."""

    treatment: str
    days_after: int
    hospital_name: str | None = None
    package_id: str | None = None
