from sqlalchemy import Column, String, Numeric, BigInteger, Boolean, Integer
from app.config.database import Base

class Place(Base):
    __tablename__ = "attractions"

    # 기본 키 (BIGINT)
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)

    # 필수 정보 (place_id 매핑)
    kakao_place_id = Column("place_id", String, nullable=True, index=True)
    place_name = Column(String, nullable=False)

    # 불리언 형태
    is_indoor = Column(Boolean, default=False)
    is_heat_source = Column(Boolean, default=False)
    is_massage_spot = Column(Boolean, default=False)
    
    # 정수형태
    walk_hard = Column(Integer, default=1)

    # 카테고리 및 분류
    primary_type = Column(String, nullable=True)
    primary_type_name = Column(String, nullable=True)
    collection_types = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    category_group_code = Column(String, nullable=True)
    category_group_name = Column(String, nullable=True)

    # 수치형 데이터 (NUMERIC)
    map_x = Column(Numeric(12, 8), nullable=True)
    map_y = Column(Numeric(12, 8), nullable=True)

    # 연락처 및 주소
    phone = Column(String, nullable=True)
    address_name = Column(String, nullable=True)
    road_address_name = Column(String, nullable=True)
    place_url = Column(String, nullable=True)

    def __repr__(self):
        return f"<Place(name='{self.place_name}', id='{self.id}')>"