# Data Collection Plan: 마포·동작·관악·송파

## Overview

강남·서초 기준 데이터와 `docs/DATA_COLLECTION_RULES.md`를 기준으로 네 자치구의 서비스용 장소 데이터를 재현 가능하게 수집한다. 카카오 Local API 원본 수집, 카테고리 정규화, 카테고리별 popularity 기준, 수동 검수 후보 분리, 스키마 검증을 거쳐 구별 파일과 통합 파일을 만든다.

## Architecture Decisions

- 카카오 공식 Local API의 카테고리·키워드 검색을 격자 단위로 호출하고 `addressName`으로 자치구를 확정한다.
- `kakaoPlaceId`를 중복 제거 키로 사용한다.
- 카페는 popularity 5만 최종 후보로 유지하고, 찜질방·사우나·안마/스파는 popularity 4 이상을 수동 검수 후보로 분리한다.
- 문화시설·공원·드럭스토어·백화점은 popularity 일괄 컷을 적용하지 않는다.
- 서점·도서관과 관광·산책형 신규 데이터는 현재 운영 결정에 따라 수집하지 않고, 쇼핑몰은 도입 보류한다.
- 카카오 웹 장소 상세 API를 이용한 popularity 근거 수집은 공식 Local API 계약 밖이므로 실패 행을 0점으로 간주하지 않고 별도 기록한다.

## Task List

### Phase 1: Foundation

- [x] 재사용 가능한 네 구 장소 수집·정규화 스크립트 작성
- [x] 분류·popularity 계산·스키마 검증 단위 테스트 작성

### Checkpoint: Foundation

- [x] 단위 테스트 통과
- [x] 소수 API 표본 호출 및 응답 구조 확인

### Phase 2: Collection

- [x] 마포구 원본 수집 및 카테고리별 선별
- [x] 동작구 원본 수집 및 카테고리별 선별
- [x] 관악구 원본 수집 및 카테고리별 선별
- [x] 송파구 원본 수집 및 카테고리별 선별

### Checkpoint: Collection

- [x] 각 구 주소·ID·좌표·중복 검증
- [x] popularity 실패 행 재시도 및 분리

### Phase 3: Finalization

- [x] 구별 서비스 후보 CSV 생성
- [x] 네 구 통합 CSV와 수집 보고서 생성
- [x] 기존 강남·서초 데이터와의 ID 중복 및 스키마 호환성 확인

### Checkpoint: Complete

- [x] `isNa=1` 0개
- [x] 정수 필드 타입과 컬럼 순서 일치
- [x] 카테고리별 후보·필터·채택 수 보고

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| API 검색 결과 상한으로 고밀도 지역 누락 | 높음 | 작은 격자와 거리 정렬, 경계 중첩 검색 사용 |
| 웹 상세 API 응답 변경 또는 제한 | 높음 | 재시도·실패 분리, Local API 원본 보존 |
| 마사지·복합문화공간·공원 오탐 | 높음 | 엄격한 카테고리/상호 필터와 수동 검수 후보 파일 제공 |
| 외출 중 장시간 실행 중단 | 중간 | 단계별 중간 CSV와 진행 보고서 저장 |

## Official Source

- Kakao Local REST API: https://developers.kakao.com/docs/ko/local/dev-guide
# Current Task: 고정 primaryTypeName 및 Kakao categoryName 매핑 명세

## 목표

지역 확장 수집에서도 `primaryTypeName`을 임의로 추가하거나 변경하지 않도록 폐쇄형 목록과 코드 구현 가능한 매핑 규칙을 정규 문서로 확정한다.

## 작업 순서

1. 기존 실서비스 데이터, 추가 구 수집 결과, 수집 코드, 기존 문서를 대조한다.
2. 카카오 Local API의 공개 범위와 세부 카테고리 사용 제한을 공식 자료로 확인한다.
3. 고정 `primaryTypeName`, `primaryType`, `categoryName` 매칭 방식, 우선순위, 제외·미매핑 정책을 표로 만든다.
4. 산·섬·숲 등 통합 표시명 아래에서도 필요한 원본 세부 정보와 제약값을 재현할 수 있게 정의한다.
5. 실제 관측 카테고리의 커버리지와 규칙 충돌을 검증하고 기존 수집 규칙에서 정규 문서를 연결한다.

## 산출물

- `docs/PRIMARY_TYPE_MAPPING_RULES.md`
- `docs/DATA_COLLECTION_RULES.md`의 정규 매핑 명세 링크

## 완료 결과

- [x] 공식 공개 범위와 정책 확인
- [x] 17개 폐쇄형 표시명과 허용 조합 확정
- [x] 서비스 범위 매핑·제외·미매핑 표 작성
- [x] 산·섬·숲 정보 보존과 walkHard 규칙 정의
- [x] 기존 데이터의 표시명 및 자연 경로 검증
- [x] 기존 수집 규칙 문서와 연결

# Implementation Plan: 소상공인 데이터를 관광공사 구조로 변환

## Overview

승인된 `docs/SPEC_SMALL_BUSINESS_TO_TOURISM_DATA.md`에 따라 55만여 행의 소상공인 원본을 스트리밍으로 읽고, 합의된 업종만 관광공사 CSV 구조로 변환한다. 카페·웰니스 승인 목록 매칭, 관광공사 우선 중복 제거, 원천별 출력 및 감사 보고서를 하나의 재실행 가능한 명령으로 제공한다.

## Architecture Decisions

- Python 표준 라이브러리만 사용해 별도 런타임 의존성을 추가하지 않는다.
- 소상공인 원본은 스트리밍하고 작은 기준 파일만 메모리에 인덱싱한다.
- 순수 함수로 이름·주소 정규화, 분류, 매칭, 중복 판정을 분리해 단위 테스트한다.
- 운영 CSV에는 관광공사와 같은 컬럼만 쓰고 원천 식별자와 제외 근거는 감사 파일에만 쓴다.
- 원본은 읽기 전용이며 모든 생성물은 `data/newData/processed/`에 둔다.

## Dependency Graph

```text
정규화·분류 함수
  -> 승인 목록 매칭
  -> 관광공사/소상공인 중복 판정
  -> 스트리밍 변환과 출력
  -> 실제 데이터 전체 검증
```

## Task List

### Phase 1: Pure transformation rules

- [x] 이름 조립, 업종 분류, 병원 제외어, 출력 기본값을 실패 테스트로 정의한다.
- [x] 테스트를 통과하는 최소 순수 변환 함수를 구현한다.

### Checkpoint: Classification

- [x] 집중 단위 테스트가 모두 통과한다.

### Phase 2: Matching and deduplication

- [x] 승인 목록의 주소 및 30m+유사명 매칭 테스트를 작성하고 구현한다.
- [x] 관광공사 우선과 소상공인 내부 중복 제거 테스트를 작성하고 구현한다.

### Checkpoint: Entity resolution

- [x] 모호한 매칭이 운영 출력으로 들어가지 않음을 검증한다.

### Phase 3: End-to-end conversion

- [x] 임시 입력 파일 기반 통합 테스트를 작성한다.
- [x] 스트리밍 변환 CLI와 세 운영 CSV, 감사 CSV, JSON 보고서 생성을 구현한다.
- [x] 실제 `newData` 전체를 변환한다.

### Checkpoint: Complete

- [x] 출력 헤더와 순서가 관광공사 기준 파일과 정확히 일치한다.
- [x] 식별자 빈 값, 좌표, 허용 타입, 승인 매칭, 중복 검증 위반이 모두 0이다.
- [x] 원본 파일이 변경되지 않았다.
- [x] 기존 테스트의 알려진 과거 모듈 import 실패와 이번 기능 테스트 결과를 구분해 보고한다.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 지점명 차이로 승인 목록 매칭 누락 | 유효 장소 제외 | 정규화·주소·좌표+유사명 단계와 미매칭 감사 보고서 |
| 같은 건물의 다른 업체를 중복 처리 | 정상 장소 손실 | 주소/좌표 단독 판정 금지, 반드시 장소명 조건 결합 |
| 승인 목록 한 행에 여러 원천 행 매칭 | 중복 적재 | Kakao 식별자를 출력하지는 않되 매칭 그룹 내 대표 소상공인 행 한 개만 유지 |
| 전체 원본 메모리 적재 | 메모리 부족 | `csv.DictReader` 스트리밍과 제한된 후보 보관 |
| 소상공인 식별자를 운영 CSV에서 잃음 | 재현성 저하 | 감사 CSV에 원천 ID, 결정, 근거, 최종 출력 키 기록 |

## Verification Commands

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_transform_small_business_places -v
.\.venv\Scripts\python.exe scripts\transform_small_business_places.py --input-dir data\newData --output-dir data\newData\processed
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
