# Spec: 소상공인 데이터를 관광공사 구조로 변환

상태: 승인 및 구현 완료

## Objective

`data/newData/소상공인시장진흥공단_상가(상권)정보_서울_202606.csv`에서 합의된 업종만 선별해 관광공사 `attractions.csv`, `accommodations.csv`, `hospitals.csv`와 동일한 컬럼 구조의 CSV로 변환한다.

원본 파일은 변경하지 않는다. 관광공사와 소상공인 데이터가 같은 장소를 나타내면 관광공사 행을 유지하고 소상공인 행을 제외한다. 결과는 DB 적재 전에 사람이 검토할 수 있어야 하며, 모든 포함·제외 건수와 원인을 보고서로 남긴다.

## Inputs

| 역할 | 파일 |
|---|---|
| 관광공사 숙소 기준 데이터 | `data/newData/accommodations.csv` |
| 관광공사 병원 기준 데이터 | `data/newData/hospitals.csv` |
| 관광공사 장소 기준 데이터 | `data/newData/attractions.csv` |
| 소상공인 원본 | `data/newData/소상공인시장진흥공단_상가(상권)정보_서울_202606.csv` |
| 소상공인 업종 명세 | `data/newData/[붙임]빅데이터플랫폼_업종분류_및_연계표.xlsx` |
| 카페·웰니스 승인 목록 | `data/newData/kakao_cafe_massage_candidates.csv` |

승인 목록은 Kakao 데이터 소스로 사용하지 않는다. 소상공인 행의 포함 여부를 판정하고, 합의된 네 제약값을 보강하는 용도로만 사용한다.

## Outputs

원본과 구분되는 `data/newData/processed/` 아래에 다음 파일을 만든다.

| 파일 | 내용 |
|---|---|
| `small_business_attractions.csv` | 승인된 카페·웰니스·올리브영 |
| `small_business_accommodations.csv` | 승인된 호텔·여관/모텔·펜션 |
| `small_business_hospitals.csv` | 승인된 피부/비뇨기과·성형외과 중 제외 규칙을 통과한 병원 |
| `transformation_audit.csv` | 원천 행별 포함/제외/중복 판정과 원천 `상가업소번호` |
| `transformation_report.json` | 단계별 건수, 유형별 건수, 검증 결과 |

운영 CSV 세 개에는 새 컬럼을 추가하지 않는다. `상가업소번호`는 운영 CSV에 넣지 않고 감사 파일에만 보존한다.

## Category Selection

### Attractions

| 판정 조건 | `primary_type` | `primary_type_name` | 추가 조건 |
|---|---|---|---|
| 소분류코드 `I21201` | `cafe` | `카페` | 승인 목록과 매칭된 행만 포함 |
| 소분류코드 `S20801` | `heat_source` | `찜질방/사우나` | 승인 목록과 매칭된 행만 포함 |
| 소분류코드 `S20802` | `massage_spot` 또는 `spa` | `안마/스파` | 승인 목록과 매칭된 행만 포함; 승인 목록의 두 위험 플래그로 세부 타입 결정 |
| 최종 장소명에 `올리브영` 포함 | `drugstore` | `드럭스토어` | 업종 코드와 무관하게 포함; 명백한 비매장·오탐은 감사 대상으로 제외 가능 |

`S20802`의 `is_heat_source=1` 및 `is_massage_spot=1`이면 `primary_type=spa`, 그렇지 않고 마사지 플래그만 1이면 `massage_spot`으로 정한다. `S20801`도 승인 목록의 검증된 플래그를 최종값으로 사용한다.

화장품점 `G21503`과 약국 `G21501`은 제외한다. 이름에 `올리브영`이 있는 행은 이 전역 제외보다 우선하는 명시적 예외다.

### Accommodations

| 소분류코드 | 업종 | 처리 |
|---|---|---|
| `I10101` | 호텔/리조트 | 포함 |
| `I10102` | 여관/모텔 | 포함 |
| `I10103` | 펜션 | 포함 |

그 밖의 숙박업은 제외한다. 최종 `place_type=ACCOMMODATION`, `primary_type=accommodation`, `primary_type_name=숙소`로 저장한다.

### Hospitals

| 소분류코드 | 업종 | 처리 |
|---|---|---|
| `Q10204` | 피부/비뇨기과 의원 | 조건부 포함 |
| `Q10208` | 성형외과 의원 | 포함 |

`Q10204`의 최종 장소명에 `비뇨`, `비뇨기과`, `남성`, `요로` 중 하나가 포함되면 제외한다. 최종 `place_type=HOSPITAL`, `primary_type=hospital`, `primary_type_name=병원`으로 저장한다.

근거가 없으므로 `skin_treatment_confidence`와 `skin_treatment_signals`는 빈 값으로 둔다.

## Name Normalization

```text
지점명이 비어 있음       -> 상호명
지점명이 정확히 "코리아" -> 상호명
그 외 지점명이 있음      -> "상호명 지점명"
```

앞뒤 공백과 연속 공백은 정리한다. 원본 상호명에 지점명이 이미 포함돼 있으면 같은 문구를 중복해서 붙이지 않는다.

## Approval-list Matching

카페·사우나·마사지는 승인 목록과 다음 순서로 매칭한다.

1. 정규화 장소명과 정규화 도로명주소가 동일
2. 정규화 장소명과 정규화 지번주소가 동일
3. 두 좌표 간 Haversine 거리가 30m 이하이고 정규화 장소명이 유사

주소 정규화는 `서울특별시`/`서울` 차이, 공백, 괄호 표기를 정리한다. 장소명 정규화는 공백·구두점·법인 표기와 확정된 지점명 조립 차이를 정리한다.

매칭이 없거나 복수 후보가 동일한 신뢰도로 남으면 운영 출력에서 제외하고 감사 파일에 각각 `approval_not_matched`, `approval_ambiguous`로 기록한다.

승인 목록에서 사용할 수 있는 컬럼은 다음 네 개뿐이다.

- `is_indoor`
- `is_heat_source`
- `is_massage_spot`
- `walk_hard`

`popularity`, Kakao `place_id`, 장소명, 주소, 좌표, 전화번호, URL, 카테고리, 이미지 등은 최종값으로 사용하지 않는다.

## Duplicate Policy

### 판정 조건

소상공인 내부와 관광공사-소상공인 사이에서 다음 순서로 중복을 찾는다.

1. 정규화 장소명 + 정규화 도로명주소 일치
2. 정규화 장소명 + 정규화 지번주소 일치
3. 좌표 30m 이내 + 정규화 장소명 유사

주소만 같거나 좌표만 가까운 경우에는 같은 건물의 다른 업체일 수 있으므로 중복으로 판정하지 않는다.

### 생존 우선순위

```text
관광공사 > 소상공인
```

관광공사와 중복된 소상공인 행은 제외한다. 소상공인 내부 중복은 판정 근거가 가장 완전한 행 하나만 유지하고 나머지는 감사 파일에 기록한다.

## Column Mapping

### 공통 원천 변환

| 소상공인 원천 | 출력 컬럼 | 규칙 |
|---|---|---|
| `상호명`, `지점명` | `place_name` | Name Normalization 적용 |
| `상권업종대분류명 > 상권업종중분류명 > 상권업종소분류명` | `category_name` | 세 값을 ` > `로 연결. 단, 올리브영 행은 `올리브영`으로 고정 |
| `경도` | `map_x` | 실수 경도 그대로 사용 |
| `위도` | `map_y` | 실수 위도 그대로 사용 |
| `지번주소` | `address_name` | 그대로 사용하되 앞뒤 공백 제거 |
| `도로명주소` | `road_address_name` | 그대로 사용하되 앞뒤 공백 제거 |
| 변환 유형 | `collection_types` | 최종 `primary_type`과 동일하게 설정 |
| 고정값 | `source` | `SMALL_BUSINESS` |
| 변환 실행 시각 | `synced_at` | UTC timezone 포함 시각 |

### 공통 빈 값과 기본값

| 출력 컬럼 | 값 |
|---|---|
| `id` | 빈 값 |
| `place_id` | 빈 값 |
| `tourism_content_id` | 빈 값 |
| `phone` | 빈 값 |
| `place_url` | 빈 값 |
| `image_url` | 빈 값 |
| `image_url_overridden` | `f` |
| `category_group_code` | 빈 값 |
| `category_group_name` | 빈 값 |

`상가업소번호`를 `id`, `place_id` 또는 `tourism_content_id`에 넣지 않는다.

### Attraction 전용

| 출력 컬럼 | 규칙 |
|---|---|
| `is_indoor` | 승인 목록 값; 올리브영은 `t` |
| `is_heat_source` | 승인 목록 값; 올리브영은 `f` |
| `is_massage_spot` | 승인 목록 값; 올리브영은 `f` |
| `is_na` | `f` |
| `walk_hard` | 승인 목록 값; 올리브영은 `2` |
| `popularity` | 빈 값 |

### Attraction constraint mapping

승인 목록의 플래그는 `massage_spot`과 `spa`를 구분할 때만 사용한다. 출력 제약값은 최종 `primary_type`에 따라 아래 값으로 고정한다.

| `primary_type` | `is_indoor` | `is_heat_source` | `is_massage_spot` | `walk_hard` |
|---|---:|---:|---:|---:|
| `cafe` | `t` | `f` | `f` | `1` |
| `heat_source` | `t` | `t` | `f` | `1` |
| `massage_spot` | `t` | `f` | `t` | `1` |
| `spa` | `t` | `t` | `t` | `1` |
| `drugstore` | `t` | `f` | `f` | `2` |

## Validation Rules

운영 출력에 들어가는 모든 행은 다음을 만족해야 한다.

- `place_name`, `address_name`, `road_address_name`, `map_x`, `map_y`가 존재한다.
- 좌표가 유한 숫자이며 서울 경계 안에 있다.
- `primary_type`과 `primary_type_name`이 이 명세의 허용 조합이다.
- attraction의 boolean은 `t` 또는 `f`, `walk_hard`는 정수 1~5다.
- `id`, `place_id`, `tourism_content_id`가 비어 있다.
- 운영 출력 내부에 판정된 중복이 없다.
- 관광공사 기준 파일과 판정된 중복이 없다.
- 카페·웰니스는 모두 승인 목록과 유일하게 매칭됐다.
- 모든 소상공인 원천 후보는 포함 또는 구체적인 제외 사유로 감사 파일에 나타난다.

## Implementation Structure

| 파일 | 책임 |
|---|---|
| `scripts/transform_small_business_places.py` | 스트리밍 입력, 라벨링, 매칭, 중복 제거, CSV·보고서 생성 |
| `tests/test_transform_small_business_places.py` | 이름 조립, 업종 판정, 승인 매칭, 중복 우선순위, 컬럼 계약 단위 테스트 |
| `docs/SPEC_SMALL_BUSINESS_TO_TOURISM_DATA.md` | 이 명세 |

554,092행 원본 전체를 메모리에 올리지 않는다. 관광공사 기준 데이터와 승인 목록은 크기가 작으므로 메모리 인덱스를 만들 수 있다. 소상공인 원본은 `csv.DictReader`로 순차 처리한다.

## Commands

```powershell
# 집중 테스트
.\.venv\Scripts\python.exe -m unittest tests.test_transform_small_business_places -v

# 변환 실행
.\.venv\Scripts\python.exe scripts\transform_small_business_places.py `
  --input-dir data\newData `
  --output-dir data\newData\processed

# 전체 테스트
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

추가 패키지는 설치하지 않고 Python 표준 라이브러리만 사용한다.

## Testing Strategy

- 작은 단위 테스트: 업종별 포함/제외, 지점명 처리, 병원 제외어, 출력 기본값
- 매칭 테스트: 주소 정확 매칭, 30m 좌표+유사명, 매칭 실패, 모호한 매칭
- 중복 테스트: 관광공사 우선, 소상공인 내부 대표 행 선택
- 통합 테스트: 임시 CSV 입력에서 세 출력과 감사/보고서 생성
- 전체 데이터 검증: 실제 원본을 변환한 후 보고서의 계약 위반 수가 모두 0인지 확인

## Boundaries

### Always

- 원본 및 관광공사 기준 CSV를 읽기 전용으로 취급한다.
- 운영 출력과 감사 정보를 분리한다.
- 임의의 Kakao 값을 운영 출력에 복사하지 않는다.
- 제외 사유와 단계별 건수를 기록한다.

### Ask First

- DB 또는 CSV 컬럼 구조 변경
- 신규 카테고리 추가
- 30m 거리나 이름 유사도 기준 변경
- 카페·웰니스 승인 목록 밖의 행 채택

### Never

- `상가업소번호`를 기존 식별자 컬럼에 대신 저장하지 않는다.
- 화장품점이나 약국을 드럭스토어로 자동 변환하지 않는다.
- 주소 또는 좌표만으로 중복을 확정하지 않는다.
- 원본 파일을 덮어쓰지 않는다.

## Success Criteria

1. 합의한 업종과 올리브영만 올바른 출력 파일로 분리된다.
2. 카페·웰니스는 승인 목록과 유일하게 매칭된 행만 포함된다.
3. Kakao 데이터는 네 제약값 외에는 최종 출력에 사용되지 않는다.
4. 관광공사와 중복된 소상공인 행이 모두 제거되고 관광공사 행은 변하지 않는다.
5. 세 운영 CSV의 헤더와 컬럼 순서가 각각의 관광공사 기준 CSV와 정확히 같다.
6. 원본 5개 파일은 바이트 단위로 변하지 않는다.
7. 변환 결과를 다시 실행해도 같은 입력과 실행 시각을 제외한 내용이 동일하다.
8. 테스트와 실제 데이터 검증이 통과한다.

## Open Questions

없음. 구현 중 명세와 충돌하는 데이터가 발견되면 추측하지 않고 이 문서를 먼저 갱신해 검토받는다.
