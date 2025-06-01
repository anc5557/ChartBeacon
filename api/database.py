import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# 환경에 따른 DATABASE_URL 설정
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production" or os.getenv("DOCKER_ENV"):
    # 도커 환경에서는 postgres 호스트명 사용
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://chartbeacon:chartbeacon123@postgres:5432/chartbeacon",
    )
else:
    # 로컬 개발환경에서는 localhost 사용
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://chartbeacon:chartbeacon123@localhost:5432/chartbeacon",
    )

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
