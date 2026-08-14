# Afterglow AI

강남·서초 의료관광 장소 및 코스를 추천하는 FastAPI 애플리케이션이다.

## 디렉터리 구조

```text
afterglow-ai/
├── app/
│   ├── __init__.py
│   ├── model_server.py                 # FastAPI 앱 생성, lifespan, 라우터 등록
│   ├── api/
│   │   ├── __init__.py
│   │   └── recommendation.py           # 추천, 상태, 피드백 API 엔드포인트
│   ├── config/
│   │   ├── __init__.py
│   │   ├── base_config.yaml            # 운영 설정값
│   │   ├── policy_config.py            # 시술·점수·코스 정책
│   │   └── settings.py                 # 설정 로딩 및 외부 제공
│   ├── models/
│   │   ├── __init__.py
│   │   └── recommendation.py           # 내부 도메인 모델
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── place_repository.py         # 데이터 접근 인터페이스
│   │   └── csv_place_repository.py     # CSV 구현체
│   ├── rule/
│   │   ├── __init__.py
│   │   ├── inference.py                # 전체 추천 흐름 조정
│   │   ├── candidate_service.py
│   │   ├── course_service.py
│   │   ├── treatment_filter.py
│   │   ├── place_score.py
│   │   ├── distance_service.py
│   │   └── analytics_service.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── recommendation.py           # Request/Response Pydantic 모델
│   └── utils/
│       └── __init__.py
├── data/                               # CSV 원천 및 가공 데이터
├── models/                             # 학습 모델 파일
├── recommendation/                     # 기존 import 경로 호환 래퍼
├── scripts/                            # 수집·정제·학습 스크립트
├── tests/                              # 회귀 테스트
├── model_server.py                     # 기존 구동점 호환 래퍼
├── Procfile
├── requirements.txt
└── README.md
```

## 계층별 책임

```text
HTTP 요청
  → app/api/recommendation.py
  → app/rule/inference.py
  → CandidateService / CourseService
  → PlaceRepository
  → CSV 또는 향후 AWS DB
```

- `model_server.py`는 애플리케이션 생성과 의존성 연결만 담당한다.
- `api/`는 HTTP 입력과 출력만 담당한다.
- `schemas/`는 외부 API 데이터 모델을 담당한다.
- `rule/inference.py`는 Anchor 및 시술 변환 등 전체 추천 흐름을 조정한다.
- `rule/`의 개별 서비스는 후보 선정, 필터, 점수, 코스 구성을 담당한다.
- `repositories/`는 저장 방식과 추천 규칙을 분리한다.
- `config/`는 운영 설정과 추천 정책을 관리한다.

## 실행

```powershell
pip install -r requirements.txt
uvicorn app.model_server:app --reload --host 127.0.0.1 --port 8000
```

기존 명령인 `uvicorn model_server:app`도 호환된다.

## API

```text
GET  /health
POST /recommend/places
POST /recommend/courses
POST /feedback/course-selection
GET  /docs
GET  /openapi.json
```

현재 요청·응답 명세는 기존 API와 호환된다. 여행 기간 기반 신규 요청 모델은 이번 구조 개편 범위에 포함하지 않았다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```
