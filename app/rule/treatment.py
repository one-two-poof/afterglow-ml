import datetime
from typing import Any, Dict, List

from app.utils.config_loader import get_rule_config

def apply_treatment_rule(
    treatment_list: List[Any], # Request로 들어온 treatmentList (name과 date를 가짐)
    target_date: datetime.date, # 현재 순회 중인 여행 날짜
    candidates: Dict[int, Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """
    시술 룰 설정을 가져와 점수를 가산하는 함수
    """
    # 규칙 설정 가져오기
    rule_config = get_rule_config()
    treatment_config = rule_config.get("treatment_rule", {})
    
    penalty_score = treatment_config.get("penalty_score")
    treatment_rules = treatment_config.get("rules", {})

    filtered_candidates = {}

    for place_id, place_info in candidates.items():
        is_blocked = False
        penalized_features: set[str] = set()

        # 장소 특성 추출 (질문자님이 정의하신 기준 적용)
        is_outdoor = int(place_info.get("is_indoor")) == 0
        is_high_activity = int(place_info.get("walk_hard")) >= 4
        is_heat = int(place_info.get("is_heat_source")) == 1
        is_massage = int(place_info.get("is_massage_spot")) == 1

        place_features = {
            "high_activity": is_high_activity,
            "outdoor_exposure": is_outdoor,
            "heat_exposure": is_heat,
            "massage_pressure": is_massage
        }

        # 유저가 받은 시술 리스트를 각각 순회
        for treatment_item in treatment_list:
            treatment_name = treatment_item.name  # 시술 종류
            treatment_date = treatment_item.date  # 해당 시술을 받은 날짜
            
            # 시술일로부터 현재 여행 날짜까지 경과된 일수 계산
            elapsed_days = (target_date - treatment_date).days
            
            # 아직 시술을 받기 전이거나 기간이 지난 경우는 스킵 (경과일이 0 이상일 때만 제약 적용)
            if elapsed_days < 0:
                continue

            rules_for_treatment = treatment_rules.get(treatment_name)
            if not rules_for_treatment:
                continue

            # 제약 항목별 확인
            for feature_key, conditions in rules_for_treatment.items():
                if not conditions:
                    continue

                for condition in conditions:
                    max_day = condition.get("max_day", 0)
                    action = condition.get("action")

                    if elapsed_days <= max_day and place_features.get(feature_key, False):
                        if action == "BLOCK":
                            is_blocked = True
                            break
                        elif action == "PENALTY":
                            penalized_features.add(feature_key)

                if is_blocked:
                    break

            if is_blocked:
                break

        # BLOCK 당한 장소는 제외
        if is_blocked:
            continue

        # 피처당 1회만 반영하고, 장소 전체 벌점은 penalty_score 한 번으로 상한
        place_penalty = penalty_score if penalized_features else 0.0

        # 후보군 유지 및 누적된 페널티 반영
        filtered_candidates[place_id] = place_info.copy()
        filtered_candidates[place_id]["score"] += place_penalty

    return filtered_candidates
