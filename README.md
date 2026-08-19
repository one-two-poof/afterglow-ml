# Afterglow AI

강남·서초 의료관광 장소 및 코스를 추천하는 FastAPI 애플리케이션이다.

## 디렉터리 구조

```text
afterglow-ai/
├── app/
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py                 # 서버 상태 확인 API 엔드포인트
│   │   └── recommendation.py         # 추천, 피드백 API 엔드포인트
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── rule_config.yaml          # 통합 규칙 설정 파일 (YAML)
│   │   └── database.py               # DB 연결 및 세션 생성 (SQLAlchemy)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── place.py                  # 추천 장소 ORM 모델
│   │   └── start_location.py         # 출발지 ORM 모델
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── place.py                  # 추천 장소 데이터 접근 레이어
│   │   └── start_location.py         # 출발지 데이터 접근 레이어
│   │
│   ├── rule/
│   │   ├── __init__.py
│   │   ├── category.py               # 카테고리 가산점 규칙
│   │   ├── distance.py               # 거리 계산 및 필터링 규칙
│   │   ├── treatment.py              # 시술별 페널티 계산 및 필터링 규칙
│   │   └── walk_preference.py        # 도보 선호도와 각 장소별 차이 계산 규칙
│   │
│   ├── service/
│   │   ├── __init__.py
│   │   ├── course.py                 # 점수 계산된 장소 후보를 통해 코스 생성
│   │   └── inference.py              # 전체 추천 흐름 조정
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── recommendation.py         # Request/Response Pydantic 모델
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config_loader.py          # 통합 규칙 설정 메모리 캐싱 로더
│   │   └── distance.py               # 거리 계산 유틸 (하버사인 공식)
│   │
│   ├── __init__.py
│   └── model_server.py               # FastAPI 앱 생성, lifespan 설정, 라우터 등록
│
├── data/                             # CSV 원천 및 가공 데이터
├── .github/workflows/                # GitHub Actions 배포 워크플로
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

- `app/model_server.py`: 애플리케이션 생성, lifespan을 통한 전역 설정 로딩(load_rule_config), 라우터 등록 등 구동점 역할만 담당한다.
- `app/api/`: HTTP 요청 입력(Request)과 응답 출력(Response) 검증 및 라우팅만 담당한다.
- `app/schemas/`: 외부 API 통신을 위한 Pydantic 데이터 모델을 정의한다.
- `app/rule/inference.py`: 전체 추천 흐름(후보군 조회, 날짜별 순회, 룰 적용, 코스 조합)을 조정한다.
- `app/rule/`: 카테고리(category.py) 및 거리(distance.py)별 개별 비즈니스 규칙과 점수 산정 로직을 담당한다.
- `app/repositories/`: 데이터베이스와의 상호작용(쿼리 조회 등)을 캡슐화하여 비즈니스 로직과 분리한다.
- `app/config/`: 데이터베이스 세션(database.py) 및 통합 규칙 설정(rule_config.yaml)을 관리한다.
- `app/utils/`: 전역 설정 메모리 캐싱 로더(config_loader.py) 및 하버사인 거리 계산(distance.py) 등의 공통 유틸리티를 제공한다.

## 실행

```powershell
pip install -r requirements.txt
uvicorn app.model_server:app --reload --host 127.0.0.1 --port 8000
```

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
