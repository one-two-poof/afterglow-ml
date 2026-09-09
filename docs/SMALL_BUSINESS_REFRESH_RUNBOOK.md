# 소상공인 데이터 갱신·필터링 운영 절차

이 문서는 소상공인시장진흥공단의 서울 상가(상권)정보가 갱신되었을 때, 새 원본을 현재 추천 DB용 CSV 구조로 다시 만드는 절차를 설명한다. 기준 구현은 `scripts/transform_small_business_places.py`이며, 분류 정책의 상세 근거는 `SPEC_SMALL_BUSINESS_TO_TOURISM_DATA.md`를 따른다.

## 1. 결과물과 원본 보존 원칙

- 새 원본 CSV는 수정하지 않는다.
- 관광공사 원본인 `attractions.csv`, `accommodations.csv`, `hospitals.csv`도 수정하지 않는다.
- 변환 결과만 `data/newData/processed`에 생성한다.
- 스크립트를 다시 실행하면 기존 소상공인 변환 결과와 감사·통계 파일을 덮어쓴다. 운영 반영 전에는 필요하면 이전 `processed` 결과를 별도로 보관한다.
- 관광공사 데이터와 소상공인 데이터를 한 CSV로 합치지 않는다. 두 출처 사이의 중복만 검사하며, 중복이면 소상공인 행을 제외한다.

생성 파일은 다음과 같다.

| 파일 | 내용 |
|---|---|
| `small_business_attractions.csv` | 카페, 찜질방/사우나, 안마/스파, 올리브영 |
| `small_business_accommodations.csv` | 호텔/리조트, 여관/모텔, 펜션 |
| `small_business_hospitals.csv` | 피부과 및 성형외과 |
| `transformation_audit.csv` | 후보별 포함·제외 결정과 사유 |
| `transformation_report.json` | 입력·후보·포함·제외 건수와 검증 결과 |

`small_business_accommodations_hospitals.csv`는 별도 편의용 병합 파일이며 현재 변환 스크립트가 자동 생성하지 않는다. 필요하면 7절의 병합 단계를 수행한다.

## 2. 갱신 전에 준비할 파일

`data/newData` 아래에 다음 파일이 있어야 한다.

1. 새 소상공인 서울 상가(상권)정보 CSV
2. `attractions.csv`: 관광공사 관광지 중복 검사 기준
3. `accommodations.csv`: 관광공사 숙소 중복 검사 기준 및 출력 헤더 기준
4. `hospitals.csv`: 관광공사 병원 중복 검사 기준 및 출력 헤더 기준
5. `kakao_cafe_massage_candidates.csv`: 과거에 확정한 카페·찜질방·안마/스파 승인 목록

승인 목록 파일명에 `kakao`가 남아 있지만 카카오의 `place_id`, URL, 전화번호 등은 출력에 복사하지 않는다. 이 파일은 카페·찜질방·안마/스파를 선별하기 위한 화이트리스트로만 쓴다. 새 원본에서 상호명·주소·좌표가 크게 바뀐 장소는 매칭되지 않을 수 있으므로 감사 파일에서 반드시 확인한다.

새 스냅샷은 날짜가 달라지므로 자동 파일 탐색에 의존하지 말고 실행할 때 항상 `--source`로 정확한 파일을 지정한다. 현재 자동 탐색은 `202606` 파일명만 대상으로 한다.

## 3. 포함하는 업종

| 조건 | 출력 | `primary_type` | 처리 |
|---|---|---|---|
| 소분류 코드 `I21201` | 관광지 | `cafe` | 승인 목록과 매칭된 행만 포함 |
| 소분류 코드 `S20801` | 관광지 | `heat_source` | 승인 목록과 매칭된 행만 포함 |
| 소분류 코드 `S20802` | 관광지 | `massage_spot` 또는 `spa` | 승인 목록과 매칭된 행만 포함 |
| 최종 장소명에 `올리브영` 포함 | 관광지 | `drugstore` | 업종 코드와 무관하게 포함 |
| 소분류 코드 `I10101`, `I10102`, `I10103` | 숙소 | `accommodation` | 포함 |
| 소분류 코드 `Q10204`, `Q10208` | 병원 | `hospital` | 포함하되 아래 병원 제외 규칙 적용 |

화장품점과 약국은 일반 업종으로 포함하지 않는다. 단, 최종 장소명에 `올리브영`이 들어간 행은 예외로 포함한다. 그 밖의 업종 코드는 후보 단계에서 제외한다.

## 4. 행 단위 정제 순서

처리 순서는 다음과 같다.

1. `상호명`과 `지점명`으로 최종 장소명을 만든다.
   - 기본: `상호명 지점명`
   - 지점명이 비어 있거나 `코리아`이면 상호명만 사용
   - 상호명이 이미 지점명으로 끝나면 지점명을 다시 붙이지 않음
2. 선택 업종 코드 또는 이름에 `올리브영`이 있는 행만 후보로 만든다.
3. `Q10204` 병원 이름에 `비뇨`, `비뇨기과`, `남성`, `요로`가 있으면 제외한다.
4. 장소명, 지번주소, 도로명주소, 좌표가 모두 있는지 검사한다.
5. 좌표가 서울 범위인 경도 `126.7~127.3`, 위도 `37.4~37.8` 안인지 검사한다.
6. 카페·찜질방·안마/스파는 승인 목록과 매칭한다. 올리브영·숙소·병원은 승인 목록 매칭을 요구하지 않는다.
7. 관광공사 데이터와 중복이면 소상공인 행을 제외한다.
8. 이미 포함한 소상공인 행과 중복이면 뒤에 나온 행을 제외한다.
9. 관광공사 CSV와 동일한 칼럼 순서로 출력한다.

## 5. 승인 목록 및 중복 매칭 규칙

장소명과 주소는 공백·법인 표기·괄호·일부 기호를 정규화한 후 비교한다. 다음 중 하나를 만족하면 같은 장소로 본다.

- 정규화 장소명이 같고 지번주소 또는 도로명주소가 같음
- 두 좌표의 직선거리가 30m 이하이고 장소명 유사도가 0.72 이상

승인 목록에서 동률인 최상위 후보가 둘 이상이면 임의로 고르지 않고 `approval_ambiguous`로 제외한다. 같은 승인 목록 행에 소상공인 원본 여러 행이 연결되면 최초 한 행만 포함하고 나머지는 `approval_source_duplicate`로 제외한다.

## 6. 관광지 파생값

승인 목록의 플래그는 `S20802`를 `massage_spot`과 `spa`로 나누는 데만 사용한다. 최종 파생값은 유형별로 고정한다.

| 유형 | `is_indoor` | `is_heat_source` | `is_massage_spot` | `walk_hard` |
|---|---:|---:|---:|---:|
| 카페 | `t` | `f` | `f` | `1` |
| 찜질방/사우나 | `t` | `t` | `f` | `1` |
| 안마/스파 (`massage_spot`) | `t` | `f` | `t` | `1` |
| 안마/스파 (`spa`) | `t` | `t` | `t` | `1` |
| 올리브영 | `t` | `f` | `f` | `2` |

모든 관광지의 `is_na`는 `f`, `popularity`는 빈값이다. 올리브영의 `category_name`은 원본 업종 경로 대신 `올리브영`으로 고정한다.

## 7. 실행 방법

PowerShell에서 프로젝트 루트 `C:\afterglow`로 이동한 뒤 실행한다. 아래 파일명은 실제 새 스냅샷 파일명으로 바꾼다.

```powershell
.\.venv\Scripts\python.exe scripts\transform_small_business_places.py `
  --input-dir data\newData `
  --output-dir data\newData\processed `
  --source "data\newData\소상공인시장진흥공단_상가(상권)정보_서울_YYYYMM.csv"
```

숙소와 병원을 하나의 적재 파일로도 써야 한다면 변환이 끝난 뒤 다음을 실행한다.

```powershell
$accommodations = Import-Csv data\newData\processed\small_business_accommodations.csv -Encoding UTF8
$hospitals = Import-Csv data\newData\processed\small_business_hospitals.csv -Encoding UTF8
@($accommodations) + @($hospitals) |
  Export-Csv data\newData\processed\small_business_accommodations_hospitals.csv -NoTypeInformation -Encoding UTF8
```

## 8. 실행 후 필수 검증

먼저 자동 테스트를 실행한다.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_transform_small_business_places -v
```

그다음 `transformation_report.json`에서 아래 `validation` 값이 모두 `0`인지 확인한다.

- `header_mismatches`
- `nonblank_identifier_rows`
- `invalid_required_rows`
- `invalid_attraction_constraint_rows`
- `duplicate_output_rows`

갱신 때마다 이전 스냅샷과 다음 건수를 비교한다.

- `source_rows`
- `candidate_rows`
- `included`와 `included_by_destination`
- `included_by_primary_type`
- `excluded_by_reason`

건수가 크게 변하면 바로 적재하지 말고 `transformation_audit.csv`를 사유별로 확인한다. 특히 다음 항목을 우선 검토한다.

| 감사 사유 | 의미 | 확인할 것 |
|---|---|---|
| `approval_not_matched` | 승인 목록과 일치하지 않음 | 상호·주소 변경, 폐업·신규점, 좌표 변화 |
| `approval_ambiguous` | 승인 후보를 하나로 확정하지 못함 | 동명 지점과 동일 건물 내 점포 |
| `approval_source_duplicate` | 승인 행 하나에 원본 여러 행이 연결됨 | 지점명·주소 및 실제 중복 여부 |
| `tourism_duplicate` | 관광공사 데이터와 중복 | 소상공인 행이 제외된 것이 맞는지 |
| `small_business_duplicate` | 소상공인 데이터 내부 중복 | 최초 포함 행이 대표 행으로 적절한지 |
| `urology_name` | 피부과 혼합 코드에서 비뇨기과 신호 발견 | 제외가 맞는지 |
| `invalid_required_fields` | 필수값·좌표 오류 | 원본 품질 문제와 보정 가능 여부 |

마지막으로 표본 검수한다.

1. 올리브영의 `category_name`이 모두 `올리브영`인지 확인한다.
2. 찜질방/사우나의 열원·마사지 플래그가 각각 `t`, `f`인지 확인한다.
3. `spa`와 `massage_spot` 분리가 승인 목록의 의도와 맞는지 확인한다.
4. 병원에 비뇨기과가 남지 않았는지 검색한다.
5. 숙소에 승인되지 않은 숙박 업종이 들어오지 않았는지 확인한다.

## 9. 새 분류 코드가 등장했을 때

새 원본에서 기존에 없던 업종 코드가 나타나도 임의로 기존 유형에 넣지 않는다. 먼저 업종분류 연계표에서 의미를 확인하고 표본을 검수한 다음 다음 네 곳을 함께 변경한다.

1. `scripts/transform_small_business_places.py`의 허용 코드 및 분류 규칙
2. `tests/test_transform_small_business_places.py`의 분류·출력 테스트
3. `SPEC_SMALL_BUSINESS_TO_TOURISM_DATA.md`의 정책 명세
4. 이 운영 문서의 포함 업종과 검증 항목

변경 후에는 테스트, 전체 변환, 감사 보고서 검토 순서로 다시 검증한다.
