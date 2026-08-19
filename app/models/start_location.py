from sqlalchemy import Column, String, Numeric, BigInteger
from app.config.database import Base

class StartLocation(Base):
    __tablename__ = "hospitals_accommodations"

    # 기본 키 (BIGINT)
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)

    # 필수 정보 (place_id 매핑)
    kakao_place_id = Column("place_id", String, nullable=True, index=True)
    place_name = Column(String, nullable=False)
    
    # 카테고리 및 분류
    primary_type = Column(String, nullable=True)
    primary_type_name = Column(String, nullable=True)
    collection_types = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    category_group_code = Column(String, nullable=True)
    category_group_name = Column(String, nullable=True)
    
    # 수치형 데이터 및 스키마에 정의된 속성들
    skin_treatment_confidence = Column(String, nullable=True)
    skin_treatment_signals = Column(String, nullable=True)
    map_x = Column(Numeric(12, 8), nullable=True)
    map_y = Column(Numeric(12, 8), nullable=True)
    
    # 연락처 및 주소
    phone = Column(String, nullable=True)
    address_name = Column(String, nullable=True)
    road_address_name = Column(String, nullable=True)
    place_url = Column(String, nullable=True)

    def __repr__(self):
        return f"<StartLocation(name='{self.place_name}', id='{self.id}')>"