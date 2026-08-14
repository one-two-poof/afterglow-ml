"""병원·숙소와 후보 장소 CSV를 도메인 모델로 변환하는 저장소다."""

from pathlib import Path

import pandas as pd

from app.config.settings import ANCHOR_DATA_FILE, CANDIDATE_DATA_FILES
from app.models.recommendation import Anchor, Place


def _repair_legacy_text(value: object) -> str:
    """과거 Latin-1 경유 과정에서 깨진 UTF-8 문자열이면 복원한다."""
    text = str(value or "").strip()
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired if repaired else text


class CsvPlaceRepository:
    """서버 시작 시 CSV 전체를 읽어 메모리에 보관하는 구현체다."""

    def __init__(self, data_dir: Path):
        """데이터 디렉터리에서 Anchor와 후보 장소를 즉시 적재한다."""
        self.data_dir = data_dir
        self._anchors = self._load_anchors()
        self._places = self._load_places()

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        """필수 CSV를 문자열 중심 DataFrame으로 안전하게 읽는다."""
        if not path.is_file():
            raise RuntimeError(f"Required place data not found: {path}")
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    def _load_anchors(self) -> list[Anchor]:
        """병원·숙소 CSV의 이름과 좌표를 Anchor 객체로 변환한다."""
        frame = self._read(self.data_dir / ANCHOR_DATA_FILE)
        return [
            Anchor(
                name=_repair_legacy_text(row.placeName),
                latitude=float(row.mapY),
                longitude=float(row.mapX),
                anchor_type=row.primaryType,
            )
            for row in frame.itertuples(index=False)
        ]

    def _load_places(self) -> list[Place]:
        """후보 CSV를 검증하고 카카오 장소 ID 기준으로 중복 제거한다."""
        by_id: dict[str, Place] = {}
        for filename in CANDIDATE_DATA_FILES:
            frame = self._read(self.data_dir / filename)
            for row in frame.to_dict("records"):
                # 수집·정제 단계에서 사용할 수 없다고 표시된 행은 제외한다.
                if row.get("isNa", "0") == "1":
                    continue
                indoor = row.get("isIndoor", "")
                walk_hard = row.get("walkHard", "")
                # 추천 안전성과 도보 점수에 필수인 값이 없으면 계산할 수 없다.
                if not indoor or not walk_hard:
                    continue
                try:
                    place = Place(
                        place_id=row["kakaoPlaceId"],
                        place_name=_repair_legacy_text(row["placeName"]),
                        place_category=row["primaryType"],
                        latitude=float(row["mapY"]),
                        longitude=float(row["mapX"]),
                        is_indoor=bool(int(indoor)),
                        walk_hard=int(walk_hard),
                        category_name=_repair_legacy_text(row.get("categoryName", "")),
                        place_url=row.get("placeUrl", ""),
                    )
                # 일부 잘못된 행 때문에 서버 전체가 시작하지 못하는 것을 방지한다.
                except (KeyError, TypeError, ValueError):
                    continue
                # 같은 ID가 여러 파일에 존재하면 먼저 읽은 정제 결과를 유지한다.
                by_id.setdefault(place.place_id, place)
        return list(by_id.values())

    def find_anchor(self, name: str) -> Anchor | None:
        """앞뒤 공백과 영문 대소문자를 무시한 완전 일치로 Anchor를 찾는다."""
        normalized = name.strip().casefold()
        return next((item for item in self._anchors if item.name.casefold() == normalized), None)

    def list_places(self) -> list[Place]:
        """서버 시작 시 적재한 후보 장소 목록을 반환한다."""
        return self._places

    def anchor_count(self) -> int:
        """현재 메모리에 적재된 Anchor 수를 반환한다."""
        return len(self._anchors)
