from enum import Enum
from typing import List
from pydantic import BaseModel, Field
import datetime

# =========  추론 Request =========

# 선택지 제한을 위한 Enum 클래스 정의
class TreatmentType(str, Enum):
    lifting = "리프팅"
    botox = "보톡스"
    obesity = "비만(약처방)"
    skin_booster = "스킨부스터"
    contour_injection = "윤곽/체형주사"
    hair_removal = "제모"
    skin_care = "피부관리"
    laser = "피부레이저"
    filler = "필러"
    peeling = "필링"

class UserPurpose(str, Enum):
    culture = "문화관광"
    shopping = "뷰티쇼핑"
    rest = "휴식"

# --- 하위 요청 객체 ---
class DailyStartItem(BaseModel):
    date: datetime.date = Field(..., description="YYYY-MM-DD 날짜")
    start_id: int = Field(..., description="해당 날짜의 시작점 이름 (병원 또는 숙소)")

class TreatmentRequest(BaseModel):
    name: TreatmentType = Field(..., description="시술 항목")
    date: datetime.date = Field(..., description="시술 받는 날짜 (YYYY-MM-DD)")

# --- 최종 요청 객체 ---
class RecommendationRequest(BaseModel):
    trip_start_date: datetime.date = Field(..., description="여행 시작일 (YYYY-MM-DD)")
    trip_end_date: datetime.date = Field(..., description="여행 종료일 (YYYY-MM-DD)")
    user_purpose: UserPurpose = Field(..., description="유저 방문 목적")
    user_walk_preference: int = Field(..., ge=1, le=5, description="도보 선호도 (1~5)")
    daily_startList: List[DailyStartItem] = Field(..., description="날짜별 출발점 정보 리스트")
    treatmentList: List[TreatmentRequest] = Field(..., description="여행 기간 중 받는 시술 목록")


# ========= 추론 Response =========

class StartLocation(BaseModel):
    name: str = Field(..., description="출발점 이름 (병원 또는 숙소)")
    mapX: float = Field(..., description="위도 (Latitude)")
    mapY: float = Field(..., description="경도 (Longitude)")

class TreatmentResponse(BaseModel):
    name: str = Field(..., description="시술 또는 치료 이름")
    date: datetime.date = Field(..., description="시술 예정 날짜 (YYYY-MM-DD)")

class PlaceItem(BaseModel):
    visit_order: int = Field(..., description="방문 순서")
    place_name: str = Field(..., description="장소 이름")
    place_category: str = Field(..., description="장소 카테고리")
    mapX: float = Field(..., description="위도 (Latitude)")
    mapY: float = Field(..., description="경도 (Longitude)")
    is_indoor: int = Field(..., description="실내 여부 (0: 야외, 1: 실내)")
    walk_hard: int = Field(..., description="걷기 난이도 (1 ~ 5)")
    dist_to_prev_km: float = Field(..., description="이전 장소로부터의 거리 (km)")

class RecommendedCourse(BaseModel):
    rank: int = Field(..., description="AI 추천 순위 (1 ~ 3)")
    course_id: str = Field(..., description="추천 코스 고유 ID")
    total_distance_km: float = Field(..., description="코스 내 전체 이동 거리 합산 (km)")
    places: List[PlaceItem] = Field(..., description="코스에 포함된 장소 리스트")

class DailyRecommendation(BaseModel):
    date: datetime.date = Field(..., description="해당 날짜 (YYYY-MM-DD)")
    start_location: StartLocation = Field(..., description="해당 날짜의 출발점 정보")
    treatment: List[TreatmentResponse] = Field(..., description="해당 일정 관련 시술 목록")
    recommended_courses: List[RecommendedCourse] = Field(..., description="해당 날짜의 추천 코스 리스트")

class RecommendationResponse(BaseModel):
    daily_recommendations: List[DailyRecommendation] = Field(..., description="날짜별 추천 코스 리스트")