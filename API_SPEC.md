# Afterglow 추천 API 명세서

## 1. 문서 정보

| 항목 | 값 |
|---|---|
| API 이름 | Afterglow Rule-Based Recommendation API |
| API 버전 | 1.0.0 |
| 애플리케이션 엔트리포인트 | `model_server:app` |
| 로컬 기본 URL | `http://localhost:8000` |
| Swagger UI | `GET /docs` |
| OpenAPI JSON | `GET /openapi.json` |
| 인증 | 현재 미적용 |
| 요청/응답 형식 | `application/json` |

실행 예시:

```powershell
uvicorn model_server:app --reload --host 127.0.0.1 --port 8000
```

AWS Elastic Beanstalk에서는 `Procfile`의 다음 명령으로 실행한다.

```text
web: uvicorn model_server:app --host 0.0.0.0 --port 8000
```

## 2. 공통 정책

### 2.1 현재 데이터 소스

| 용도 | 파일 |
|---|---|
| Anchor(병원·숙소) | `data/gangnam_seocho_skin_hospitals_accommodations.csv` |
| 후보 장소 | `data/gangnam_seocho_places_drugstore_attraction_department_culture.csv` |

서버 시작 시 CSV를 메모리에 적재한다. 필수 파일이 없거나 읽을 수 없으면 애플리케이션 시작에 실패한다.

### 2.2 지원 사용자 목적

```text
문화관광
뷰티쇼핑
휴식
```

### 2.3 지원 시술

```text
리프팅
보톡스
비만(약처방)
스킨부스터
윤곽/체형주사
제모
피부관리
피부레이저
필러
필링
```

### 2.4 공통 검증 규칙

- 정의되지 않은 JSON 필드는 허용하지 않는다(`extra=forbid`).
- `user_walk_preference`는 `1~5` 정수다.
- `days_after`는 `0` 이상의 정수다. 시술 당일은 `0`이다.
- 위도는 `-90~90`, 경도는 `-180~180` 범위다.
- Anchor 좌표는 위도와 경도를 모두 전달하거나 둘 다 생략해야 한다.
- 단일 시술 형식과 다중 시술 형식을 한 요청에서 함께 사용할 수 없다.
- 시간 기반 시술 일정에는 UTC 오프셋이 포함된 ISO 8601 시각을 사용해야 한다.

### 2.5 일반적인 HTTP 상태 코드

| 코드 | 의미 |
|---:|---|
| 200 | 요청 처리 성공 |
| 404 | `title`과 정확히 일치하는 Anchor를 찾지 못함 |
| 422 | JSON 형식, 필수 값, 범위 또는 업무 규칙 검증 실패 |
| 500 | 서버 내부 오류 또는 데이터 로딩/처리 오류 |

FastAPI/Pydantic 검증 실패 응답은 다음 형태다.

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "user_walk_preference"],
      "msg": "Input should be greater than or equal to 1",
      "input": 0,
      "ctx": {"ge": 1}
    }
  ]
}
```

서비스에서 직접 발생시키는 오류는 다음처럼 문자열 `detail`을 사용할 수 있다.

```json
{
  "detail": "Anchor not found"
}
```

## 3. 공통 추천 요청 모델

`POST /recommend/places`와 `POST /recommend/courses`가 같은 요청 모델을 사용한다.

### 3.1 필드

| 필드 | 타입 | 필수 | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `jwt` | string 또는 null | 아니요 | `null` | 사용자 식별값. 인증에는 사용하지 않으며 분석 로그에는 해시로 변환한다. |
| `title` | string | 예 | 길이 1 이상 | Anchor 이름. 좌표가 없을 때 CSV에서 정확히 일치하는 이름을 조회한다. |
| `treatment` | string 또는 null | 조건부 | 지원 시술 중 하나 | 단일 시술 호환 필드. `days_after`와 함께 사용한다. |
| `days_after` | integer 또는 null | 조건부 | 0 이상 | 단일 시술의 시술 후 경과일. |
| `treatments` | array 또는 null | 조건부 | 1~20개 | 다중 시술 목록. 단일 시술 필드와 동시에 사용할 수 없다. |
| `recommendation_at` | datetime 또는 null | 조건부 | UTC 오프셋 필수 | `scheduled_at` 기반 시술의 추천 평가 시각. |
| `user_purpose` | string | 예 | 지원 목적 중 하나 | 장소 및 코스 목적 적합도 계산에 사용한다. |
| `user_walk_preference` | integer | 예 | 1~5 | 사용자의 도보 허용 수준. |
| `anchor_type` | string 또는 null | 아니요 | `null` | 좌표 직접 입력 시 Anchor 종류를 표시하기 위한 값. |
| `anchor_latitude` | number 또는 null | 아니요 | -90~90 | Anchor 위도. 경도와 함께 전달한다. |
| `anchor_longitude` | number 또는 null | 아니요 | -180~180 | Anchor 경도. 위도와 함께 전달한다. |

### 3.2 시술 입력 방식 A: 단일 시술

`treatment`와 `days_after`를 반드시 함께 전달한다.

```json
{
  "jwt": "U9288",
  "title": "강남OO피부과",
  "treatment": "피부레이저",
  "days_after": 3,
  "user_purpose": "휴식",
  "user_walk_preference": 2
}
```

### 3.3 시술 입력 방식 B: 여러 시술과 경과일

`treatments`를 사용하면 `treatment`, `days_after`를 최상위에 전달하지 않는다.

`TreatmentEventInput` 필드:

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `treatment` | string | 예 | 지원 시술명 |
| `days_after` | integer 또는 null | 조건부 | 시술 후 경과일. `scheduled_at`과 둘 중 하나만 사용한다. |
| `scheduled_at` | datetime 또는 null | 조건부 | 시술 예정/시행 시각. `days_after`와 둘 중 하나만 사용한다. |
| `hospital_name` | string 또는 null | 아니요 | 시술 병원 식별용 메타데이터 |
| `package_id` | string 또는 null | 아니요 | 패키지 예약 식별용 메타데이터 |

```json
{
  "jwt": "U9288",
  "title": "강남OO피부과",
  "treatments": [
    {
      "treatment": "보톡스",
      "days_after": 0,
      "hospital_name": "강남OO피부과",
      "package_id": "PKG-001"
    },
    {
      "treatment": "피부레이저",
      "days_after": 2,
      "hospital_name": "강남OO피부과",
      "package_id": "PKG-001"
    }
  ],
  "user_purpose": "휴식",
  "user_walk_preference": 2
}
```

### 3.4 시술 입력 방식 C: 일정 시각 기반

- `scheduled_at`을 사용하면 최상위 `recommendation_at`이 필수다.
- 두 시각 모두 `+09:00`, `Z` 같은 UTC 오프셋을 포함해야 한다.
- 추천 시각보다 미래인 시술은 아직 활성 시술이 아니므로 해당 추천 평가에서 제외한다.
- 활성 시술의 `days_after`는 시술 장소의 현지 날짜 기준 날짜 차이로 계산한다.

```json
{
  "jwt": "U9288",
  "title": "강남OO피부과",
  "recommendation_at": "2026-08-14T14:00:00+09:00",
  "treatments": [
    {
      "treatment": "필러",
      "scheduled_at": "2026-08-13T11:00:00+09:00",
      "hospital_name": "강남OO피부과"
    },
    {
      "treatment": "보톡스",
      "scheduled_at": "2026-08-16T10:00:00+09:00",
      "hospital_name": "서초OO의원"
    }
  ],
  "user_purpose": "뷰티쇼핑",
  "user_walk_preference": 3
}
```

위 예시에서는 필러만 활성 시술에 포함되고 미래의 보톡스는 제외된다.

### 3.5 Anchor 결정 방식

#### 이름 조회

좌표를 생략하면 `title`을 Anchor CSV의 장소명과 공백 제거·대소문자 무시 방식으로 정확히 비교한다. 부분 검색은 지원하지 않는다.

#### 좌표 직접 입력

```json
{
  "title": "사용자 지정 출발지",
  "anchor_type": "custom",
  "anchor_latitude": 37.4979,
  "anchor_longitude": 127.0276,
  "treatment": "제모",
  "days_after": 1,
  "user_purpose": "문화관광",
  "user_walk_preference": 3
}
```

좌표가 있으면 CSV Anchor 이름 검색을 수행하지 않는다.

## 4. GET `/health`

서버 상태와 시작 시 적재된 데이터 개수를 확인한다.

### 4.1 요청

본문과 쿼리 파라미터가 없다.

```bash
curl http://localhost:8000/health
```

### 4.2 성공 응답 `200 OK`

```json
{
  "status": "ok",
  "service": "rule-based-recommendation",
  "version": "1.0.0",
  "anchor_count": 100,
  "candidate_place_count": 500,
  "catboost_loaded": false
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | string | 정상 시 `ok` |
| `service` | string | 현재 추천 서비스 식별자 |
| `version` | string | API 버전 |
| `anchor_count` | integer | 메모리에 적재된 Anchor 개수 |
| `candidate_place_count` | integer | 유효성 검사를 통과해 적재된 후보 장소 개수 |
| `catboost_loaded` | boolean | 현재 규칙 기반 서비스이므로 `false` |

## 5. POST `/recommend/places`

Anchor 반경 내 후보 장소에 의료 필터와 규칙 기반 점수를 적용해 장소 단위로 반환한다.

### 5.1 쿼리 파라미터

| 이름 | 타입 | 필수 | 기본값 | 범위 | 설명 |
|---|---|---:|---:|---|---|
| `limit` | integer | 아니요 | 20 | 1~100 | 반환할 최대 장소 수 |

### 5.2 처리 정책

1. Anchor를 이름 또는 직접 좌표로 결정한다.
2. 시술 목록을 활성 시술과 경과일로 변환한다.
3. Anchor에서 Haversine 거리로 5km 이내인 장소만 남긴다.
4. 장소 속성으로 위험 신호를 계산한다.
5. 여러 시술 중 가장 강한 상태를 적용한다: `BLOCK > PENALTY > NORMAL`.
6. `BLOCK` 장소는 결과에서 제거한다.
7. 나머지 장소의 목적·시술·거리·도보 점수를 계산한다.
8. `place_score` 내림차순, 거리 오름차순, 장소 ID 오름차순으로 정렬한다.

Place Score:

```text
purpose_score   × 0.35
+ treatment_score × 0.30
+ distance_score  × 0.20
+ walk_score      × 0.15
```

### 5.3 성공 응답 `200 OK`

```json
{
  "status": "success",
  "recommendation_id": "c4514d11-dda4-4a2f-8872-883fb01dc377",
  "data": {
    "anchor": {
      "name": "강남OO피부과",
      "latitude": 37.4979,
      "longitude": 127.0276,
      "anchor_type": "hospital"
    },
    "active_treatments": [
      {
        "treatment": "피부레이저",
        "days_after": 3,
        "hospital_name": null,
        "package_id": null
      }
    ],
    "medical_compatibility_checked": false,
    "candidate_places": [
      {
        "place_id": "P001",
        "place_name": "OO문화시설",
        "place_category": "cultural_facility",
        "category_name": "문화시설 > 미술관",
        "latitude": 37.5001,
        "longitude": 127.0301,
        "is_indoor": true,
        "walk_hard": 1,
        "distance_from_anchor_km": 0.7,
        "filter_status": "NORMAL",
        "risk_signals": [],
        "treatment_evaluations": [
          {
            "treatment": "피부레이저",
            "days_after": 3,
            "status": "NORMAL",
            "matched_risk_signals": [],
            "hospital_name": null,
            "package_id": null
          }
        ],
        "purpose_score": 75.0,
        "treatment_score": 100.0,
        "distance_score": 90.0,
        "walk_score": 100.0,
        "place_score": 89.25,
        "place_url": "https://place.map.kakao.com/123456"
      }
    ]
  }
}
```

### 5.4 응답 필드

#### 최상위

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | string | 정상 처리 시 `success` |
| `recommendation_id` | UUID string | 피드백 API와 연결할 추천 요청 식별자 |
| `data` | object | 추천 결과 |

#### `data.anchor`

| 필드 | 타입 | 설명 |
|---|---|---|
| `name` | string | Anchor 이름 |
| `latitude` | number | 위도 |
| `longitude` | number | 경도 |
| `anchor_type` | string 또는 null | 병원, 숙소 또는 직접 입력한 유형 |

#### `data.active_treatments[]`

| 필드 | 타입 | 설명 |
|---|---|---|
| `treatment` | string | 평가에 실제 사용한 시술명 |
| `days_after` | integer | 평가 시점의 경과일 |
| `hospital_name` | string 또는 null | 요청에서 전달한 병원명 |
| `package_id` | string 또는 null | 요청에서 전달한 패키지 ID |

#### `data.candidate_places[]`

| 필드 | 타입 | 설명 |
|---|---|---|
| `place_id` | string | 카카오 장소 ID |
| `place_name` | string | 장소명 |
| `place_category` | string | 내부 정규화 카테고리 |
| `category_name` | string | 원본 상세 카테고리명 |
| `latitude` | number | 장소 위도 |
| `longitude` | number | 장소 경도 |
| `is_indoor` | boolean | 실내 장소 여부 |
| `walk_hard` | integer | 장소 도보 난이도 |
| `distance_from_anchor_km` | number | Anchor로부터 직선거리(km), 소수점 셋째 자리 반올림 |
| `filter_status` | enum | 최종 상태: `NORMAL` 또는 `PENALTY`. `BLOCK`은 반환되지 않는다. |
| `risk_signals` | string[] | 장소 자체에서 감지한 전체 위험 신호 |
| `treatment_evaluations` | object[] | 각 활성 시술별 평가 결과 |
| `purpose_score` | number | 사용자 목적과 카테고리 적합도(0~100) |
| `treatment_score` | number | `NORMAL=100`, `PENALTY=50` |
| `distance_score` | number | 거리 구간 점수(0~100) |
| `walk_score` | number | 사용자 도보 선호 대비 난이도 점수(10~100) |
| `place_score` | number | 가중 합산 최종 점수, 소수점 둘째 자리 반올림 |
| `place_url` | string | 카카오 장소 상세 URL. 원본 데이터가 없으면 빈 문자열 |

#### `treatment_evaluations[]`

| 필드 | 타입 | 설명 |
|---|---|---|
| `treatment` | string | 평가 시술명 |
| `days_after` | integer | 해당 시술 경과일 |
| `status` | enum | 해당 시술 기준 `NORMAL`, `PENALTY`, `BLOCK` |
| `matched_risk_signals` | string[] | 최종 상태를 유발한 위험 신호 |
| `hospital_name` | string 또는 null | 병원 메타데이터 |
| `package_id` | string 또는 null | 패키지 메타데이터 |

위험 신호 값:

| 값 | 의미 | 현재 감지 기준 |
|---|---|---|
| `HIGH_ACTIVITY` | 고강도 활동 | `walk_hard >= 4` |
| `OUTDOOR_EXPOSURE` | 야외·직사광선 노출 | `is_indoor=false` |
| `HEAT_EXPOSURE` | 사우나·찜질방·온천 | 카테고리 문자열의 관련 키워드 |
| `MASSAGE_PRESSURE` | 마사지·압박 | 카테고리 문자열의 관련 키워드 |

> `medical_compatibility_checked`는 현재 응답 모델 기본값인 `false`로 반환된다. 의료진 검수를 완료했다는 의미가 아니며, 현재 규칙 엔진이 실행되지 않았다는 의미로 해석해서도 안 된다. 클라이언트의 의료 검수 표시 용도로 사용하면 안 된다.

## 6. POST `/recommend/courses`

규칙 기반 후보 장소를 조합하여 장소 3개로 구성된 코스를 반환한다.

### 6.1 쿼리 파라미터

| 이름 | 타입 | 필수 | 기본값 | 범위 | 설명 |
|---|---|---:|---:|---|---|
| `top_n` | integer | 아니요 | 3 | 1~10 | 반환할 최대 코스 수 |

요청 본문은 공통 추천 요청 모델과 같다.

### 6.2 코스 생성 정책

| 정책 | 현재 값 |
|---|---:|
| 코스당 장소 수 | 3 |
| 카테고리별 조합 후보 수 | 최대 12 |
| 한 코스 내 동일 카테고리 | 최대 2개 |
| 한 코스 내 서로 다른 카테고리 | 최소 2개 |
| 한 이동 구간 거리 | 최대 2km |
| Anchor부터 마지막 장소까지 누적 직선거리 | 최대 5km |
| 상위 코스 간 중복 장소 | 최대 1개 |

목적별 추가 조건:

- `휴식`: 코스 3곳 중 실내 장소가 최소 2곳이어야 한다.
- `문화관광`: 문화시설 또는 관광지 카테고리가 최소 1곳이어야 한다.
- `뷰티쇼핑`: 드럭스토어 또는 백화점 카테고리가 최소 1곳이어야 한다.

Course Score:

```text
average_place_score      × 0.60
+ route_score              × 0.20
+ diversity_score          × 0.10
+ purpose_composition_score × 0.10
```

### 6.3 성공 응답 `200 OK`

```json
{
  "status": "success",
  "recommendation_id": "e02d89ae-10fa-49e0-a304-cd10370b38fa",
  "data": {
    "anchor": {
      "name": "강남OO피부과",
      "latitude": 37.4979,
      "longitude": 127.0276,
      "anchor_type": "hospital"
    },
    "active_treatments": [
      {
        "treatment": "피부레이저",
        "days_after": 3,
        "hospital_name": null,
        "package_id": null
      }
    ],
    "medical_compatibility_checked": false,
    "courses": [
      {
        "rank": 1,
        "course_score": 88.45,
        "average_place_score": 90.25,
        "route_score": 80.0,
        "diversity_score": 100.0,
        "purpose_composition_score": 100.0,
        "total_distance_km": 2.35,
        "places": [
          {
            "place_id": "P001",
            "place_name": "OO문화시설",
            "place_category": "cultural_facility",
            "category_name": "문화시설 > 미술관",
            "latitude": 37.5001,
            "longitude": 127.0301,
            "is_indoor": true,
            "walk_hard": 1,
            "distance_from_anchor_km": 0.7,
            "filter_status": "NORMAL",
            "risk_signals": [],
            "treatment_evaluations": [],
            "purpose_score": 75.0,
            "treatment_score": 100.0,
            "distance_score": 90.0,
            "walk_score": 100.0,
            "place_score": 89.25,
            "place_url": "https://place.map.kakao.com/123456",
            "order": 1,
            "distance_from_previous_km": 0.7
          }
        ]
      }
    ]
  }
}
```

`places`의 실제 원소는 장소 추천 응답의 모든 필드와 다음 두 필드를 추가로 가진다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `order` | integer | 방문 순서. 1부터 시작한다. |
| `distance_from_previous_km` | number | `order=1`은 Anchor로부터 거리, 이후는 직전 장소로부터 거리 |

코스 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `rank` | integer | 추천 순위 |
| `course_score` | number | 최종 코스 점수 |
| `average_place_score` | number | 코스 내 세 장소의 Place Score 평균 |
| `route_score` | number | 누적 직선거리 구간 점수 |
| `diversity_score` | number | 세 카테고리면 100, 두 카테고리면 70 |
| `purpose_composition_score` | number | 목적별 필수 구성 충족 정도 |
| `total_distance_km` | number | Anchor에서 방문 순서대로 계산한 누적 직선거리 |
| `places` | array | 방문 순서가 적용된 장소 3개 |

조건을 만족하는 조합이 없으면 오류 대신 다음처럼 빈 배열을 반환할 수 있다.

```json
{
  "status": "success",
  "recommendation_id": "e02d89ae-10fa-49e0-a304-cd10370b38fa",
  "data": {
    "anchor": {
      "name": "강남OO피부과",
      "latitude": 37.4979,
      "longitude": 127.0276,
      "anchor_type": "hospital"
    },
    "active_treatments": [],
    "medical_compatibility_checked": false,
    "courses": []
  }
}
```

## 7. POST `/feedback/course-selection`

추천 코스 선택 또는 미선택 이벤트를 수집한다. 향후 추천 모델 학습에 사용할 수 있도록 `recommendation_id`와 선택 결과를 연결한다.

### 7.1 요청 필드

| 필드 | 타입 | 필수 | 제약 | 설명 |
|---|---|---:|---|---|
| `recommendation_id` | string | 예 | 길이 1 이상 | 코스 추천 응답에서 받은 ID |
| `jwt` | string 또는 null | 아니요 | 없음 | 로그 저장 전에 SHA-256 해시 처리 |
| `event_type` | enum | 예 | `course_selected`, `course_dismissed` | 피드백 종류 |
| `selected_course_rank` | integer 또는 null | 조건부 | 1~10 | 선택 이벤트일 때 필수 |
| `selected_place_ids` | string[] | 아니요 | 최대 3개 | 선택한 코스의 장소 ID 목록 |

### 7.2 코스 선택 요청

```json
{
  "recommendation_id": "e02d89ae-10fa-49e0-a304-cd10370b38fa",
  "jwt": "U9288",
  "event_type": "course_selected",
  "selected_course_rank": 1,
  "selected_place_ids": ["P001", "P002", "P003"]
}
```

### 7.3 코스 미선택 요청

```json
{
  "recommendation_id": "e02d89ae-10fa-49e0-a304-cd10370b38fa",
  "jwt": "U9288",
  "event_type": "course_dismissed",
  "selected_course_rank": null,
  "selected_place_ids": []
}
```

### 7.4 성공 응답 `200 OK`

```json
{
  "status": "accepted"
}
```

### 7.5 현재 저장 방식과 주의사항

- 현재 이벤트는 DB가 아니라 애플리케이션 표준 로그에 JSON 한 줄로 출력된다.
- `jwt` 원문 대신 `ANALYTICS_HASH_SALT` 환경변수와 결합한 SHA-256 해시를 기록한다.
- 운영 환경에서는 `ANALYTICS_HASH_SALT`를 반드시 별도 비밀값으로 설정해야 한다.
- 현재 API는 `recommendation_id`, 순위, 장소 ID가 실제 추천 응답과 일치하는지 DB로 검증하지 않는다.
- `course_dismissed` 요청에 `selected_course_rank`가 포함되는 것을 현재 검증기가 금지하지는 않는다.

## 8. 주요 오류 사례

### 8.1 지원하지 않는 목적

응답: `422 Unprocessable Entity`

```json
{
  "detail": "Unsupported user_purpose"
}
```

### 8.2 지원하지 않는 시술

응답: `422 Unprocessable Entity`

```json
{
  "detail": "Unsupported treatment: 임의시술"
}
```

### 8.3 Anchor를 찾지 못함

응답: `404 Not Found`

```json
{
  "detail": "Anchor not found"
}
```

### 8.4 좌표 한쪽만 전달

응답: `422 Unprocessable Entity`

```json
{
  "detail": "Both anchor coordinates are required"
}
```

### 8.5 단일·다중 시술 형식을 함께 사용

응답: `422 Unprocessable Entity`

대표 검증 메시지:

```text
Use either treatment/days_after or treatments, not both
```

### 8.6 `days_after`와 `scheduled_at`을 동시에 사용하거나 모두 생략

응답: `422 Unprocessable Entity`

대표 검증 메시지:

```text
Provide exactly one of days_after or scheduled_at
```

### 8.7 타임존 없는 일정 시각

응답: `422 Unprocessable Entity`

대표 검증 메시지:

```text
scheduled_at must include a timezone offset
```

## 9. Swagger 테스트 순서

1. 서버를 실행한다.
2. 브라우저에서 `http://localhost:8000/docs`를 연다.
3. `GET /health`의 **Try it out** → **Execute**로 데이터 로딩을 확인한다.
4. `POST /recommend/places`를 열고 `limit=20`과 단일 시술 JSON을 입력한다.
5. 응답의 `recommendation_id`, Anchor, 활성 시술 및 후보 장소 점수를 확인한다.
6. 같은 요청으로 `POST /recommend/courses?top_n=3`을 실행한다.
7. 반환된 `recommendation_id`, 코스 순위와 장소 ID를 이용해 피드백 API를 실행한다.

## 10. 구현 범위와 제한

- 현재 추천 점수는 CatBoost가 아닌 규칙 기반 점수다.
- 장소 및 코스 거리는 실제 도로·도보 경로가 아니라 Haversine 직선거리다.
- 인증과 API 권한 검사가 아직 없다. `jwt`는 인증 토큰으로 검증되지 않는다.
- 피드백은 영구 DB가 아니라 로그로만 출력된다.
- 병원별 사후관리 규칙 override는 아직 구현되어 있지 않다.
- 의료 규칙은 서비스 정책이며 의료진 검수 완료를 의미하지 않는다.
- 후보 데이터는 현재 강남구·서초구 CSV 범위로 한정된다.
