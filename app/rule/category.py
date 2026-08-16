from typing import Dict, Any
from app.utils.config_loader import get_rule_config

def apply_category_rule(user_purpose: str, candidates: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    통합 전역 설정에서 카테고리 룰 설정을 가져와 점수를 가산하는 함수
    """
    # 규칙 설정 가져오기
    rule_config = get_rule_config()
    
    # 규칙 설정에서 category_rule 섹션만 추출
    category_config = rule_config.get("category_rule", {})
    purpose_primary_mapping = category_config.get("purpose_primary_mapping", {})
    purpose_keywords = category_config.get("purpose_keywords", {})

    # user_purpose를 통해 그에 맞는 카테고리를 설정 파일에서 가져오기
    preferred_primary = purpose_primary_mapping.get(user_purpose, [])
    preferred_keywords = purpose_keywords.get(user_purpose, [])

    # 장소 후보군에서 각 장소의 주력 카테고리와 디테일 카테고리 얻은 후 preferred와 비교해서 점수 계산
    for place_id, place_info in candidates.items():
        primary_category = place_info.get("place_category", "")  
        detail_category = place_info.get("category_detail", "")   
        
        score_increment = 0.0
        
        if primary_category in preferred_primary:
            score_increment += 6.0
            
        if detail_category and any(keyword in detail_category for keyword in preferred_keywords):
            score_increment += 3.0
            
        place_info["score"] += score_increment
        
    return candidates