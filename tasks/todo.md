# 마포·동작·관악·송파 데이터 수집

## Task 1: 통합 수집기

**Acceptance criteria:**
- [x] 네 구와 대상 카테고리를 설정으로 반복 실행할 수 있다.
- [x] 공식 Local API 응답을 기준 CSV 스키마로 변환한다.
- [x] ID 중복과 대상 구 외 주소를 제거한다.

**Verification:** 단위 테스트와 표본 API 호출

**Dependencies:** 없음

## Task 2: 카테고리 정규화 및 popularity

**Acceptance criteria:**
- [x] 현재 `primaryTypeName` 통합 규칙을 적용한다.
- [x] 카페 5, 찜질·안마/스파 4 기준을 적용한다.
- [x] 상세 API 실패를 별도 상태로 보존한다.

**Verification:** 분류·점수 경계값 단위 테스트

**Dependencies:** Task 1

## Task 3: 네 구 수집

**Acceptance criteria:**
- [x] 네 구별 원본·선별 CSV가 생성된다.
- [x] 카테고리별 수집 수가 보고서에 기록된다.
- [x] 수동 검수 필요 데이터가 구분된다.

**Verification:** 주소, ID, 좌표, 중복 검사

**Dependencies:** Task 1, Task 2

## Task 4: 통합 및 최종 검증

**Acceptance criteria:**
- [x] 네 구 통합 CSV가 생성된다.
- [x] 기존 강남·서초 파일과 스키마가 일치한다.
- [x] `isNa=1`과 중복 ID가 없다.

**Verification:** 자동 검증 보고서

**Dependencies:** Task 3
# Current Task: 고정 primaryTypeName 매핑 명세

- [x] 기존 데이터·코드·문서의 분류 규칙 조사
- [x] 카카오 공식 API 공개 범위와 세부 분류 정책 확인
- [x] 폐쇄형 `primaryTypeName` 목록 확정
- [x] 서비스 범위 전체 매핑·제외·수동 검수 표 작성
- [x] 산·섬·숲 및 `walkHard` 파생 규칙 명시
- [x] 실제 관측 `categoryName` 커버리지 검증
- [x] 기존 수집 규칙 문서에 정규 명세 연결

# 소상공인 데이터 관광공사 구조 변환

## Task 1: 이름·분류·컬럼 변환

**Acceptance criteria:**
- [x] 합의한 업종만 목적별 출력 유형으로 분류된다.
- [x] `코리아` 예외와 지점명 중복 방지를 포함한 장소명 규칙이 적용된다.
- [x] 출력 기본값과 빈 식별자가 명세와 일치한다.

**Verification:** 집중 단위 테스트

**Dependencies:** 없음

## Task 2: 승인 목록 매칭

**Acceptance criteria:**
- [x] 카페·웰니스는 주소 일치 또는 30m+유사명으로 유일하게 매칭된다.
- [x] 승인 목록에서는 네 제약값만 사용된다.
- [x] 미매칭·모호한 매칭은 제외 사유로 기록된다.

**Verification:** 매칭 경계값 및 모호성 단위 테스트

**Dependencies:** Task 1

## Task 3: 중복 제거

**Acceptance criteria:**
- [x] 관광공사와 중복이면 소상공인 행만 제외된다.
- [x] 소상공인 내부 중복은 대표 행 하나만 남는다.
- [x] 주소나 좌표 단독 일치는 중복으로 보지 않는다.

**Verification:** 중복 우선순위 단위 테스트

**Dependencies:** Task 1

## Task 4: 전체 변환과 검증

**Acceptance criteria:**
- [x] 운영 CSV 3개와 감사 CSV·JSON 보고서가 생성된다.
- [x] 운영 CSV 헤더가 관광공사 기준 파일과 정확히 같다.
- [x] 실제 데이터의 계약 위반과 판정된 중복이 0이다.

**Verification:** 임시 파일 통합 테스트 및 실제 전체 변환

**Dependencies:** Task 2, Task 3
