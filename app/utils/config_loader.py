import os
import yaml
from typing import Dict, Any

RULE_CONFIG_PATH = os.getenv("RULE_CONFIG_PATH")
_GLOBAL_RULE_CONFIG: Dict[str, Any] = {}

def load_rule_config() -> None:
    """
    서버 구동 시(Lifespan 등) 단 한 번 호출하여 
    통합 규칙 설정 YAML 파일을 메모리에 적재하는 함수
    """
    global _GLOBAL_RULE_CONFIG
    
    if not RULE_CONFIG_PATH:
        raise ValueError("RULE_CONFIG_PATH 환경 변수가 설정되지 않았습니다.")
        
    if not os.path.exists(RULE_CONFIG_PATH):
        raise FileNotFoundError(f"규칙 설정 파일을 찾을 수 없습니다: {RULE_CONFIG_PATH}")
        
    with open(RULE_CONFIG_PATH, "r", encoding="utf-8") as f:
        _GLOBAL_RULE_CONFIG = yaml.safe_load(f)

def get_rule_config() -> Dict[str, Any]:
    """
    메모리에 캐싱된 규칙 설정을 반환하는 공통 함수
    """
    global _GLOBAL_RULE_CONFIG
    return _GLOBAL_RULE_CONFIG