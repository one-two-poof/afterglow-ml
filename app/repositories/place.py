from sqlalchemy.orm import Session
from app.models.place import Place  # DB 모델

class PlaceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        return self.db.query(Place).all()

    def get_by_id(self, place_id: int):
        return self.db.query(Place).filter(Place.kakao_place_id == place_id).first()