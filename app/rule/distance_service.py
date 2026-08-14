"""좌표 간 직선거리와 거리 구간별 추천 점수를 계산한다."""

from math import asin, cos, radians, sin, sqrt

from app.config.settings import DISTANCE_SCORE_BANDS


# 국제적으로 널리 사용하는 지구 평균 반지름(km)이다.
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위·경도 좌표 사이의 Haversine 대권거리를 km로 반환한다."""
    # 삼각함수는 라디안 단위를 사용하므로 입력 각도를 먼저 변환한다.
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, (lat1, lon1, lat2, lon2))
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    value = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(value))


def distance_score(distance_km: float) -> float:
    """가까울수록 높은 점수를 주는 설정 기반 거리 점수를 반환한다."""
    # 상한이 작은 구간부터 검사하므로 처음 일치한 값이 정확한 구간이다.
    for upper_bound, score in DISTANCE_SCORE_BANDS:
        if distance_km <= upper_bound:
            return score
    return 0.0
