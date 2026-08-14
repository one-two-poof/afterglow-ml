"""정적 정책과 외부 설정 파일을 합쳐 애플리케이션 설정으로 제공한다."""

import json
from pathlib import Path

# 세밀한 시술·점수 정책은 Python 상수로 관리하고 이 모듈에서 한 번에 노출한다.
from app.config.policy_config import *  # noqa: F403


# JSON은 YAML 1.2의 하위 문법이므로 별도 패키지 없이 표준 json 모듈로 읽는다.
CONFIG_PATH = Path(__file__).with_name("base_config.yaml")
with CONFIG_PATH.open(encoding="utf-8") as config_file:
    BASE_CONFIG = json.load(config_file)

# 외부 파일 값은 사용 지점에서 타입이 흔들리지 않도록 명시적으로 변환한다.
APP_TITLE = BASE_CONFIG["app"]["title"]
APP_VERSION = str(BASE_CONFIG["app"]["version"])
ANCHOR_DATA_FILE = BASE_CONFIG["data"]["anchor_file"]
CANDIDATE_DATA_FILES = tuple(BASE_CONFIG["data"]["candidate_files"])
MAX_SEARCH_RADIUS_KM = float(BASE_CONFIG["recommendation"]["max_search_radius_km"])
DEFAULT_RESULT_LIMIT = int(BASE_CONFIG["recommendation"]["default_result_limit"])
MAX_RESULT_LIMIT = int(BASE_CONFIG["recommendation"]["max_result_limit"])
DEFAULT_TOP_COURSES = int(BASE_CONFIG["recommendation"]["default_top_courses"])
MAX_TOP_COURSES = int(BASE_CONFIG["recommendation"]["max_top_courses"])
