"""추천 점수, 시술 회복 위험, 코스 구성에 사용하는 정적 정책 상수다."""

# 장소 후보 조회 범위와 API 반환 개수 정책이다.
MAX_SEARCH_RADIUS_KM = 5.0
DEFAULT_RESULT_LIMIT = 20
MAX_RESULT_LIMIT = 100
DEFAULT_PURPOSE_SCORE = 50.0

# Place Score의 네 구성 요소 가중치이며 합계는 1.0이다.
SCORE_WEIGHTS = {
    "purpose": 0.35,
    "treatment": 0.30,
    "distance": 0.20,
    "walk": 0.15,
}
# BLOCK은 후보에서 제거되므로 점수표에는 유지 가능한 두 상태만 존재한다.
TREATMENT_SCORE = {"NORMAL": 100.0, "PENALTY": 50.0}

# (거리 상한 km, 점수) 형식이며 반드시 상한 오름차순을 유지한다.
DISTANCE_SCORE_BANDS = (
    (0.5, 100.0), (1.0, 90.0), (2.0, 75.0),
    (3.0, 55.0), (5.0, 30.0),
)
# 장소 난이도가 사용자 선호도를 초과한 단계 수에 따른 도보 점수다.
WALK_SCORE_BY_EXCESS = {0: 100.0, 1: 75.0, 2: 40.0}
WALK_SCORE_LARGE_EXCESS = 10.0

# 사용자 목적별 장소 카테고리 적합도 점수표다.
PURPOSE_CATEGORY_SCORE = {
    "문화관광": {
        "cultural_facility": 100.0,
        "tourist_attraction": 95.0,
        "department_store": 60.0,
        "drugstore": 40.0,
    },
    "뷰티쇼핑": {
        "drugstore": 95.0,
        "department_store": 90.0,
        "cultural_facility": 45.0,
        "tourist_attraction": 35.0,
    },
    "휴식": {
        "cultural_facility": 75.0,
        "department_store": 65.0,
        "drugstore": 60.0,
        "tourist_attraction": 55.0,
    },
}

# 장소에서 추출 가능한 표준 위험 신호 식별자다.
RISK_HIGH_ACTIVITY = "HIGH_ACTIVITY"
RISK_OUTDOOR_EXPOSURE = "OUTDOOR_EXPOSURE"
RISK_HEAT_EXPOSURE = "HEAT_EXPOSURE"
RISK_MASSAGE_PRESSURE = "MASSAGE_PRESSURE"

# 시술별 위험 신호 정책이다.
# 각 항목은 (시작 경과일, 종료 경과일, 상태)이며 양 끝 날짜를 모두 포함한다.
TREATMENT_RISK_RULES = {
    "리프팅": {
        RISK_HIGH_ACTIVITY: ((0, 2, "PENALTY"),),
        RISK_OUTDOOR_EXPOSURE: ((0, 7, "PENALTY"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 7, "PENALTY"),),
    },
    "보톡스": {
        RISK_HIGH_ACTIVITY: ((0, 0, "BLOCK"), (1, 7, "PENALTY")),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 7, "BLOCK"),),
    },
    "필러": {
        RISK_HIGH_ACTIVITY: ((0, 1, "BLOCK"),),
        RISK_OUTDOOR_EXPOSURE: ((0, 3, "PENALTY"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 3, "BLOCK"),),
    },
    "스킨부스터": {
        RISK_HIGH_ACTIVITY: ((0, 7, "BLOCK"),),
        RISK_OUTDOOR_EXPOSURE: ((0, 7, "PENALTY"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 2, "BLOCK"),),
    },
    "윤곽/체형주사": {
        RISK_HIGH_ACTIVITY: ((0, 7, "BLOCK"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 7, "BLOCK"),),
    },
    "필링": {
        RISK_HIGH_ACTIVITY: ((0, 7, "BLOCK"),),
        RISK_OUTDOOR_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 7, "PENALTY"),),
    },
    "피부레이저": {
        RISK_HIGH_ACTIVITY: ((0, 3, "PENALTY"),),
        RISK_OUTDOOR_EXPOSURE: ((0, 3, "BLOCK"), (4, 7, "PENALTY")),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 3, "PENALTY"),),
    },
    "피부관리": {
        RISK_OUTDOOR_EXPOSURE: ((0, 7, "PENALTY"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
        RISK_MASSAGE_PRESSURE: ((0, 2, "PENALTY"),),
    },
    "제모": {
        RISK_OUTDOOR_EXPOSURE: ((0, 7, "PENALTY"),),
        RISK_HEAT_EXPOSURE: ((0, 7, "BLOCK"),),
    },
    "비만(약처방)": {},
}

# 상세 카테고리 문자열에서 열·압력 노출을 탐지할 때 사용하는 키워드다.
HEAT_CATEGORY_KEYWORDS = ("사우나", "찜질방", "온천")
MASSAGE_CATEGORY_KEYWORDS = ("마사지", "경락", "안마", "스파")

# 정책표의 키를 그대로 API 지원 값 풀로 사용해 정의 중복을 방지한다.
VALID_TREATMENTS = set(TREATMENT_RISK_RULES)
VALID_PURPOSES = set(PURPOSE_CATEGORY_SCORE)

# 코스 크기, 후보 축소, 카테고리 다양성 및 거리 제한 정책이다.
COURSE_PLACE_COUNT = 3
DEFAULT_TOP_COURSES = 3
MAX_TOP_COURSES = 10
COURSE_CANDIDATES_PER_CATEGORY = 12
MAX_SAME_CATEGORY_PER_COURSE = 2
MIN_DISTINCT_CATEGORIES = 2
MAX_LEG_DISTANCE_KM = 2.0
MAX_COURSE_DISTANCE_KM = 5.0
MAX_SHARED_PLACES_BETWEEN_TOP_COURSES = 1

# Course Score의 네 구성 요소 가중치이며 합계는 1.0이다.
COURSE_SCORE_WEIGHTS = {
    "places": 0.60,
    "route": 0.20,
    "diversity": 0.10,
    "purpose_composition": 0.10,
}
# 코스 누적 직선거리의 구간별 점수다.
COURSE_DISTANCE_SCORE_BANDS = (
    (1.5, 100.0), (3.0, 80.0), (4.0, 60.0), (5.0, 40.0),
)
# 휴식을 제외한 목적이 코스에 반드시 포함해야 하는 핵심 카테고리다.
PURPOSE_REQUIRED_CATEGORIES = {
    "문화관광": {"cultural_facility", "tourist_attraction"},
    "뷰티쇼핑": {"drugstore", "department_store"},
}
# 휴식 코스 세 장소 중 요구되는 최소 실내 장소 수다.
REST_MIN_INDOOR_PLACES = 2

# CSV Repository가 읽는 운영 데이터 파일명이다. 외부 YAML 값이 있으면 settings에서 덮어쓴다.
ANCHOR_DATA_FILE = "gangnam_seocho_skin_hospitals_accommodations.csv"
CANDIDATE_DATA_FILES = (
    "gangnam_seocho_places_drugstore_attraction_department_culture.csv",
)
