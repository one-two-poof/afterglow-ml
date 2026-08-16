import math

def calculate_haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    두 지점의 위도, 경도를 받아 하버사인 공식을 이용해 직선 거리(km)를 계산.
    """
    # 지구의 반지름 (단위: km)
    R = 6371.0

    # 각도를 라디안(Radian)으로 변환
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    
    rad_lat1 = math.radians(lat1)
    rad_lat2 = math.radians(lat2)

    # 하버사인 공식 계산
    a = math.sin(d_lat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(d_lng / 2)**2
    c = 2 * math.asin(math.sqrt(a))

    # 거리 계산 (km)
    distance = R * c
    
    return round(distance, 3)  # 소수점 셋째 자리까지 반올림