# `POST /api/course` 후속 개선 항목

이 문서는 API 성공을 위한 최소 수정 범위에서 제외한 항목을 기록한다.

## 요청 및 식별자

- `trip_end_date`가 `trip_start_date`보다 빠른 요청을 스키마 단계에서 거부한다.
- `daily_startList`의 날짜 중복과 여행 기간 밖 날짜를 검증한다.
- `treatmentList`의 시술 날짜 허용 범위를 비즈니스 규칙으로 확정한다.
- `start_id`가 DB 내부 `id`인지 카카오 `place_id`인지 확정한다. 현재 추천 로직은 내부 `id`를 사용하지만 Repository의 `get_by_id()`는 카카오 `place_id`를 조회한다.
- `DailyStartItem.start_id`의 Swagger 설명을 실제 식별자 의미에 맞게 수정한다.

## DB 및 데이터 처리

- `DATABASE_URL` 누락 여부를 명시적으로 검사한다.
- `uvicorn`과 PostgreSQL 드라이버를 `requirements.txt`에 명시해 새 환경에서 동일하게 설치되도록 한다.
- 추천 요청마다 장소와 출발지 테이블 전체를 `.all()`로 조회하는 방식을 범위 조회로 변경한다.
- 좌표가 없는 데이터를 `(0.0, 0.0)`으로 대체하지 말고 출발지는 오류 처리하고 후보 장소는 제외한다.
- 위도와 경도의 유효 범위를 검증한다.

## 규칙 및 타입

- `rule_config.yaml`을 서버 시작 시 전용 Pydantic 모델로 검증한다.
- `List[Any]`, `Dict[str, Any]`를 `TreatmentRequest`, `TypedDict` 또는 전용 모델로 교체한다.
- Repository 메서드와 `get_db()`에 구체적인 반환 타입을 선언한다.
- 규칙 설정의 누락된 키나 잘못된 점수 타입에 대한 오류 메시지를 추가한다.

## 코스 생성 로직

- 상위 코스를 만들 때 이전 순위에서 선택한 장소를 전체 후보에서 제거하는 것이 요구사항에 맞는지 확인한다.
- 현재는 장소가 정확히 3개 이상일 때만 일정을 생성한다. 최소 장소 개수를 요구사항으로 명시한다.
- `course_id`가 모든 요청에서 `C00001`부터 반복되는 것이 허용되는지 확인한다.
- 모든 여행 시술을 모든 추천 코스의 `treatment`에 넣는 현재 응답 구조가 원하는 형태인지 확인한다.

## 오류 처리 및 운영

- Pydantic 응답 검증 오류가 `ValueError` 처리에 잡혀 400으로 반환되지 않도록 예외를 구분한다.
- 내부 DB 및 코드 오류 문자열을 응답에 그대로 포함하지 않고 서버 로그에만 남긴다.
- DB 연결까지 확인하는 readiness endpoint를 별도로 둔다.
- 운영 API의 인증, 호출 제한 및 Swagger 공개 범위를 확정한다.

## 테스트

- 현재 테스트는 삭제된 `app.rule.candidate_service`, `app.rule.inference`를 import해 실행되지 않는다.
- `start_id=395` 정상 요청에 대한 API 회귀 테스트를 추가한다.
- 날짜별 출발점 누락, 잘못된 날짜 범위, 잘못된 출발점 ID를 테스트한다.
- 후보 장소 수가 0개, 1개, 2개, 3개 이상인 경우를 테스트한다.
- 각 시술의 `BLOCK` 및 `PENALTY` 경계일을 테스트한다.
