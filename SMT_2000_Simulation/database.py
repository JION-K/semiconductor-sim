# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import os

# ---------------------------------------------------------
# [설정] DB 주소 입력 (PostgreSQL)
# 도커로 띄운 경우 보통: postgresql://유저명:비번@localhost:포트/DB명
# ---------------------------------------------------------
# Docker Compose / 로컬 실행 공용:
# - 환경변수 DATABASE_URL 이 있으면 우선 사용
# - 없으면 기존 로컬 기본값 사용
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:kimjion12@localhost:5432/postgres",
)

# 1. 엔진(Engine) 시동: DB와 연결하는 본체
engine = create_engine(DATABASE_URL)

# 2. 세션(Session) 생성기: 실제로 데이터를 넣고 뺄 때 쓰는 '작업 창구'
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. 테이블 생성 함수 (이걸 실행하면 DB에 빈 테이블들이 쫘악 생깁니다!)
def create_tables():
    Base.metadata.create_all(bind=engine)
    print("✅ 데이터베이스 테이블 생성 완료!")