"""추천 규칙이 기대하는 장소 데이터 접근 계약을 정의한다."""

from typing import Protocol

from app.models.recommendation import Anchor, Place


class PlaceRepository(Protocol):
    """CSV·DB 등 저장 기술과 무관한 장소 조회 인터페이스다."""

    def find_anchor(self, name: str) -> Anchor | None:
        """정규화된 이름과 일치하는 출발점을 조회한다."""
        ...

    def list_places(self) -> list[Place]:
        """추천 계산에 사용할 모든 후보 장소를 반환한다."""
        ...

    def anchor_count(self) -> int:
        """상태 확인 API에서 사용할 출발점 총개수를 반환한다."""
        ...
