from sqlalchemy.orm import Session
from app.models.start_location import StartLocation  # DB 모델

class StartLocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        return self.db.query(StartLocation).all()

    def get_by_id(self, start_location_id: int):
        return self.db.query(StartLocation).filter(StartLocation.id == start_location_id).first()