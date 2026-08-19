from sqlalchemy import Column, Integer, String, Float
from app.config.database import Base

class StartLocation(Base):
    __tablename__ = "hospitals_accommodations"                               # DB 테이블 이름

    # 기본 키 id 추가
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 필수 정보
    kakao_place_id = Column(Integer, nullable=True, index=True)     # kakaoPlaceId
    place_name = Column(String, nullable=False)                     # placeName
    
    # 카테고리 및 분류
    primary_type = Column(String, nullable=True)                    # primaryType
    primary_type_name = Column(String, nullable=True)               # primaryTypeName
    collection_types = Column(String, nullable=True)                # collectionTypes
    category_name = Column(String, nullable=True)                   # categoryName
    category_group_code = Column(String, nullable=True)             # categoryGroupCode
    category_group_name = Column(String, nullable=True)             # categoryGroupName
    
    # 수치형 데이터
    skin_treatment_confidence = Column(Float, nullable=True)        # skinTreatmentConfidence
    skin_treatment_signals = Column(String, nullable=True)          # skinTreatmentSignals
    map_x = Column(Float, nullable=True)                            # mapX
    map_y = Column(Float, nullable=True)                            # mapY
    
    # 연락처 및 주소
    phone = Column(String, nullable=True)                           # phone
    address_name = Column(String, nullable=True)                    # addressName
    road_address_name = Column(String, nullable=True)               # roadAddressName
    place_url = Column(String, nullable=True)                       # placeUrl

    def __repr__(self):
        return f"<StartLocation(name='{self.place_name}', id='{self.kakao_place_id}')>"