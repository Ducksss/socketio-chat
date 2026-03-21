import os


class Settings:
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43800")
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "SeCretKey_CHaNgeMe")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    VERSION: int = int(os.getenv("VERSION", "1"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://root:1234@db/postgres"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    REDIS_CHANNEL: str = os.getenv("REDIS_CHANNEL", "chat:events")


setting = Settings()
