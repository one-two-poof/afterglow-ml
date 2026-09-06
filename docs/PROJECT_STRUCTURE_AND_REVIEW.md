# Afterglow AI 프로젝트 구조 및 코드 리뷰

> 검토 기준일: 2026-08-23  
> 범위: 애플리케이션, 설정, 배포 워크플로, README, 로컬 테스트  
> 목적: 신규 참여자가 구조와 실행 흐름을 이해하고 개선 우선순위를 판단하기 위한 기준 문서

## 1. 프로젝트 요약

Afterglow AI는 여행 기간, 날짜별 출발지, 방문 목적, 보행 선호도와 피부 시술 정보를 받아 날짜별 장소 3개로 구성된 추천 코스 3개를 만드는 FastAPI 서비스다. 추천 결과를 DB에 저장하고 사용자가 선택한 코스를 피드백으로 기록한다.

현재 핵심은 학습 모델이 아니라 YAML 기반 규칙 점수화와 탐욕적 코스 조합이다. 따라서 현 단계의 정확한 분류는 **규칙 기반 추천 API**다.

| 영역 | 기술 | 역할 |
|---|---|---|
| API | FastAPI | 라우팅, 의존성 주입, OpenAPI |
| 검증 | Pydantic v2 | 요청·응답 계약 |
| DB | SQLAlchemy 2.x | 장소 조회와 추천/선택 저장 |
| 인증 | PyJWT | Bearer JWT 검증 |
| 규칙 | PyYAML | 거리·카테고리·시술·보행 정책 |
| 배포 | GitHub Actions, SSH, systemd | EC2 파일 교체와 재시작 |

## 2. 디렉터리와 모듈 책임

```text
afterglow/
├─ app/
│  ├─ api/                  # HTTP 요청, 인증, 트랜잭션, 오류 변환
│  ├─ config/               # DB 연결과 추천 규칙 YAML
│  ├─ models/               # SQLAlchemy 모델과 일부 내부 dataclass
│  ├─ repositories/         # ORM 조회·저장 캡슐화
│  ├─ rule/                 # 독립적인 점수·필터 규칙
│  ├─ schemas/              # 외부 API Pydantic 계약
│  ├─ service/              # 추천 조정, 코스 생성, 저장, 피드백
│  ├─ utils/                # 설정 로더, 거리 계산, JWT
│  └─ model_server.py       # FastAPI 조립과 lifespan
├─ docs/                    # 추적되는 기술 문서
├─ .github/workflows/       # 운영 배포
├─ tests/                   # 로컬에는 있으나 현재 Git 제외 대상
├─ data/                    # 원천·가공 데이터; Git 제외 대상
└─ requirements.txt
```

### `app/model_server.py`

- FastAPI 인스턴스와 세 라우터를 조립한다.
- 시작 시 `rule_config.yaml`을 프로세스 메모리에 올린다.
- CORS는 `http://localhost:3000`만 허용한다.
- 애플리케이션 조립 지점(composition root)이다.

### `app/api/`

- `recommendation.py`: `POST /api/course`. 인증 → 추천 → 저장 → commit 순서다.
- `feedback.py`: `POST /api/course-selection`. 본인 소유 추천인지 확인하고 선택을 저장한다.
- `health.py`: `GET /api/health`. 프로세스 생존만 응답한다.

API 계층이 트랜잭션 경계를 소유한다. 서비스는 `flush()`까지만 하고 commit/rollback은 라우터가 수행한다.

### `app/schemas/`

- `RecommendationRequest`: 여행일, 목적, 보행 선호, 날짜별 출발지, 시술 목록.
- `RecommendationResponse`: 순위 3개와 날짜별 출발지·장소 목록.
- `CourseFeedbackRequest`: 선택한 추천 DB ID.

여기는 외부 계약이므로 필드 변경은 프런트엔드 호환성 변경이다.

### `app/models/`

- `place.py`: 추천 후보 테이블 `attractions`.
- `start_location.py`: 병원·숙소 테이블 `hospitals_accommodations`.
- `trip.py`: 추천, 시술, 날짜 일정, 일정 장소, 선택 피드백.
- `recommendation.py`: 과거 구조에서 사용한 내부 dataclass이며 현행 서비스에서는 미참조로 보인다.

### `app/repositories/`

- 장소와 출발지: 전체 목록 및 ID 단건 조회.
- 추천: 저장, 소유권 조회, 사용자별 페이지 조회.
- 선택: 저장, 중복 확인, 사용자별 페이지 조회.

서비스에서 SQLAlchemy 쿼리를 분리한 점은 좋지만 장소 조회가 전체 테이블 단위라 확장 병목이 된다.

### `app/rule/`

- `category.py`: 방문 목적과 주/상세 카테고리 일치 가산점.
- `activity_level.py`: activity_level과 장소 난이도(walk_hard) 차이 가감점.
- `distance.py`: 하버사인 직선거리 가산 및 반경 밖 제외.
- `treatment.py`: 시술 후 경과일과 장소 특성에 따른 차단/감점.

규칙은 후보 딕셔너리의 `score`를 누적하거나 후보를 제거한다. 정책 값은 YAML에서 읽는다.

### `app/service/`

- `inference.py`: 전체 추천 유스케이스를 조정한다.
- `course.py`: 점수순 후보를 카테고리 제약에 맞춰 탐욕 선택한다.
- `recommendation_persistence.py`: 응답 DTO를 ORM 그래프로 변환한다.
- `feedback.py`: 소유권과 기존 선택을 확인해 멱등 저장한다.

### `app/utils/`

- `distance.py`: 위·경도 간 하버사인 직선거리(km).
- `config_loader.py`: YAML을 전역 딕셔너리에 캐시.
- `security.py`: Bearer 형식, JWT 서명, `exp`, 양의 정수 `id` 검증.

## 3. 추천 요청의 실제 흐름

```text
POST /api/course
  → JWT와 요청 스키마 검증
  → 장소/출발지 전체 조회
  → 목적 카테고리 점수
  → 보행 선호 점수
  → 여행 날짜별 반복
      → 출발지 선택
      → 거리 점수 및 반경 필터
      → 시술 BLOCK/PENALTY
      → 점수순으로 장소 3개 × 코스 3개 생성
  → 동일 rank의 날짜 일정을 한 여행 코스로 결합
  → ORM 저장, 생성 ID를 응답에 반영
  → commit
```

코스 생성에는 다음 제약이 있다.

- 하루 코스는 정확히 장소 3개다.
- 한 코스에는 최소 2개 주 카테고리가 필요하다.
- 약국은 최대 1개, 동일 상세 카테고리는 중복하지 않는다.
- 한 응답에서 쓴 장소는 다른 순위나 다른 날짜에 다시 쓰지 않는다.
- 방문 순서는 경로 최적화가 아니라 규칙 점수 내림차순이다.

## 4. 데이터 구조와 트랜잭션

```text
RecommendedCourse
├─ CourseTreatment (N)
├─ DailySchedule (여행 날짜 수)
│  └─ DailySchedulePlace (날짜별 3개)
└─ SelectedCourse (0..N)
```

한 요청의 세 순위는 같은 `requested_at`을 공유하지만 명시적 batch ID는 없다. `save_recommendations()`가 `flush()`로 ID를 확보하고 라우터가 한 번에 commit하므로 정상 경로에서는 추천 전체가 원자적으로 저장된다.

## 5. 리뷰 결과

### Critical — 즉시 해결

1. **테스트가 현행 코드와 단절됐다.** `tests/test_recommendation.py`는 삭제된 `candidate_service`, `course_service`, `place_score`, `treatment_filter`를 import한다. 다른 테스트도 삭제된 `app.rule.inference`와 과거 스키마를 참조한다. 테스트 2개 모두 수집 단계에서 실패한다.
2. **`tests/`가 `.gitignore` 대상이다.** 테스트, `scripts/`, `mdfile/`가 팀과 CI에 공유되지 않는다. 현재 Git 추적 목록에 테스트가 없다.
3. **배포 품질 게이트가 없다.** main push가 테스트·lint·타입 검사 없이 EC2 교체와 재시작으로 이어진다.
4. **한글 텍스트가 광범위하게 손상됐다.** README, 주석, 오류 메시지, Swagger 설명, YAML 키가 대체 문자로 저장돼 있다. 이는 가독성뿐 아니라 enum/규칙 매칭과 클라이언트 응답의 정확성 문제다. 정상 원본이나 정상 커밋에서 복구해야 하며 추측으로 고치면 안 된다.

### High — 다음 기능 개발 전에 해결

1. **`DATABASE_URL`이 없으면 import 단계에서 실패한다.** `create_engine(None)`이 즉시 실행된다. 설정 오류를 명시하거나 시작 단계에서 엔진을 구성해야 테스트와 도구가 앱을 import할 수 있다.
2. **날짜 불변식 검증이 부족하다.** 종료일 ≥ 시작일, 기간 내 출발지 정확히 1개, 중복 날짜 금지, 시술일 범위를 Pydantic validator로 검증해야 한다.
3. **결측 좌표를 `(0, 0)`으로 대체한다.** 출발지는 데이터 무결성 오류로 중단하고 후보는 이유를 기록한 뒤 제외해야 한다.
4. **매 요청마다 두 테이블을 전체 조회한다.** 좌표 bounding box, 유효 좌표, 목적 조건을 DB로 내리고 필요한 컬럼만 조회해야 한다.
5. **동선을 최적화하지 않는다.** 점수순 선택 후 거리만 계산하며 최대 구간/총거리 제한도 없다. 상위 K 후보에 nearest-neighbor + 2-opt 또는 제한 조합 탐색을 고려한다.
6. **동시 피드백 중복 가능성이 있다.** 조회 후 삽입만으로는 race를 막지 못한다. `(user_id, recommended_course_id)` UNIQUE와 충돌 멱등 처리가 필요하다.
7. **규칙 설정이 무검증 전역 딕셔너리다.** 시작 시 전용 Pydantic 모델로 타입, 필수 키, 임계값 순서를 검증하고 불변 객체로 제공해야 한다.
8. **실행 의존성이 불완전하다.** README가 요구하는 `uvicorn`과 실제 DB 드라이버가 `requirements.txt`에 없다.

### Medium — 안정화 단계에서 개선

1. camelCase(`daily_startList`, `treatmentList`)와 snake_case가 혼재한다. 외부 alias를 유지하고 내부 이름을 통일한다.
2. `RecommendedCourse.treatment`는 `Field(default_factory=list)`가 의도를 명확히 한다.
3. 미사용으로 보이는 과거 dataclass와 Repository 메서드는 계획된 기능인지 확인 후 정리한다.
4. DB 준비 상태와 규칙 적재를 확인하는 `/ready`가 필요하다.
5. 광범위한 `except Exception` 대신 도메인 예외와 전역 오류 계약을 둔다.
6. request ID, 후보/탈락 수, 처리 시간, 규칙 버전 로그와 메트릭이 없다.
7. CORS origin을 환경별 allowlist로 옮겨야 한다.
8. `mapX/mapY`, `map_x/map_y`, 위도/경도 의미가 혼재한다. 도메인에서는 `latitude/longitude`로 통일하고 외부 alias만 유지한다.
9. `course_id`가 DB 정수 ID의 문자열 복제다. 공개 ID가 필요하면 UUID/ULID와 내부 PK를 분리한다.
10. 요청마다 같은 시술 목록을 모든 rank에 복제한다. 의도된 응답 계약인지 확인하고 요청 batch 모델 도입 시 상위로 이동할 수 있다.

### 배포·운영 위험

- health 실패 시 `app.old`는 남지만 자동 복원과 이전 버전 재시작은 없다.
- 운영 호스트에서 직접 의존성을 설치해 배포 재현성과 롤백이 약하다.
- Alembic 등 DB 마이그레이션 도구와 배포 단계가 보이지 않는다.
- health는 DB 장애나 규칙 설정 이상을 탐지하지 못한다.
- artifact checksum, staging 검증, 환경 승인, dependency cache가 없다.

## 6. 장점과 기술 연장성

- API, 서비스, 규칙, Repository, ORM의 디렉터리 경계가 이미 있다.
- commit을 API 경계에서 수행해 추천 묶음의 원자적 저장이 가능하다.
- JWT가 `exp`, `id`와 서버 설정 알고리즘을 검증한다.
- 계층 조회에 `selectinload`를 써 N+1을 피할 기반이 있다.
- 정책 수치가 YAML에 있어 코드와 규칙 조정을 분리할 수 있다.
- 추천 노출과 선택 데이터를 저장하므로 향후 A/B 테스트와 학습 ranking 기반이 있다.

즉, **기술 연장성은 충분히 남아 있다.** 다만 딕셔너리 중심 계약, 전체 조회, 테스트 단절을 먼저 해결하지 않으면 기능 추가 때 결합도와 회귀 위험이 급격히 커진다.

## 7. 권장 목표 구조

현재 계층을 유지하면서 의존 방향을 선명하게 만드는 점진 개선이 적합하다.

```text
app/
├─ api/               # HTTP 변환과 상태 코드
├─ application/       # RecommendCourseUseCase, SelectCourseUseCase
├─ domain/
│  ├─ models.py       # Coordinate, Candidate, Treatment, Course
│  ├─ policies/       # 타입이 있는 규칙 인터페이스
│  └─ optimizer.py    # 코스 조합과 경로 최적화
├─ infrastructure/
│  ├─ db/             # ORM, migrations, repositories
│  ├─ auth/           # JWT adapter
│  └─ config/         # 검증된 settings와 rule config
└─ observability/     # logging, metrics, tracing
```

의존 방향은 `API → Application → Domain ← Infrastructure`로 유지한다. `Dict[str, Any]` 후보를 타입이 있는 `Candidate`로 바꾸면 좌표, 필수 속성, 점수 누적을 테스트와 타입 검사로 보호할 수 있고 ML ranker도 같은 인터페이스 구현으로 추가할 수 있다.

## 8. 개선 로드맵

### 0단계: 복구와 기준선

1. 정상 원본/커밋에서 한글 인코딩을 복구한다.
2. `tests/`를 Git에 포함하고 현행 API/서비스 기준 테스트로 교체한다.
3. 테스트 DB fixture와 import 가능한 설정 구조를 만든다.
4. CI에 compile과 unit test를 넣고 lint/type check를 추가한다.
5. `.env.example`에 `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `CORS_ORIGINS` 이름만 기록한다.

### 1단계: 계약과 데이터 안전성

1. 여행 날짜·출발지·시술 validator와 좌표 범위 검증을 추가한다.
2. Alembic과 UNIQUE/FK/index/check constraint를 도입한다.
3. 오류 코드/응답 포맷과 OpenAPI 예제를 표준화한다.
4. 프런트 실제 payload를 contract test로 고정한다.

### 2단계: 추천 품질과 성능

1. 공간 범위 쿼리와 projection으로 후보를 제한한다.
2. 규칙별 점수 내역과 탈락 이유를 진단 모델로 만든다.
3. 장소 수, 다양성, 구간/총거리 제약을 설정화한다.
4. 경로 최적화와 결과 다양성을 독립 모듈로 분리한다.
5. 고정 fixture 회귀 테스트와 성능 benchmark를 만든다.

### 3단계: 운영과 제품 학습

1. readiness, 구조화 로그, metrics, tracing을 추가한다.
2. 요청 batch ID, 규칙/알고리즘 버전, 후보·점수 snapshot을 저장한다.
3. 노출·클릭·선택·이탈 이벤트를 정의한다.
4. 규칙 버전 A/B 테스트와 offline evaluation을 구축한다.
5. 데이터가 충분해지면 규칙 safety filter 뒤에 learning-to-rank를 추가한다.

## 9. 향후 고려 기능

- 영업시간·휴무일·예약 시간과 일정 시간축 통합
- 실제 도보/차량 경로 API 기반 이동시간
- 날씨·우천·미세먼지에 따른 실내외 정책
- 사용자 제외/필수 선호와 카테고리 확장
- 추천 이유 설명(목적, 거리, 시술 안전)
- 규칙 버전의 검토·승인·롤백 도구
- idempotency key, rate limit, 추천 이력 조회·삭제
- 민감한 건강정보의 최소 수집, 암호화, 보존기간과 삭제 정책

## 10. 테스트 전략

| 수준 | 대상 | 핵심 사례 |
|---|---|---|
| 단위 | 네 규칙 | 모든 임계일/거리, 누락 설정, 미지원 값 |
| 단위 | 코스 생성 | 후보 0/1/2/3+, 편중, 약국 중복, 장소 소진 |
| 통합 | Repository/DB | cascade, unique race, rollback, pagination |
| API | 추천 | 인증, 날짜, 출발지, 성공 응답과 저장 원자성 |
| API | 피드백 | 타 사용자 코스, 중복·동시 요청 |
| 운영 | startup/readiness | 설정 누락, DB 단절, 잘못된 YAML |
| 성능 | 추천 전체 | 후보 증가에 따른 p50/p95와 메모리 |

## 11. 검증 결과

```text
python -m compileall -q app
→ 성공

python -m unittest discover -s tests -v
→ 실패: 삭제되거나 이동된 과거 모듈 import 오류 2건

DATABASE_URL 없이 import app.model_server
→ 실패: SQLAlchemy create_engine(None)
```

이번 변경은 런타임 로직을 바꾸지 않았다. 오해하기 쉬운 오케스트레이션, 장소 재사용 범위, 저장 ID 생성, 피드백 멱등성, JWT 알고리즘 신뢰 경계에 의도 주석만 추가했다.
