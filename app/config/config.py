import os
from functools import lru_cache
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()


class Config:
    """
    Enterprise-grade configuration with:
    - Validation (fail fast)
    - Safe DB URL construction
    - Type casting
    - Caching support
    """

    # -------------------------
    # Core Environment
    # -------------------------
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # -------------------------
    # Database
    # -------------------------
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: int = int(os.getenv("DB_PORT", 5432))
    DB_NAME: str = os.getenv("DB_NAME")
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")

    # -------------------------
    # Security
    # -------------------------
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

    # -------------------------
    # Validation (FAIL FAST)
    # -------------------------
    @classmethod
    def validate(cls):
        required_fields = [
            "DB_HOST",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "SECRET_KEY",
            "JWT_SECRET",
        ]

        missing = [field for field in required_fields if not getattr(cls, field)]

        if missing:
            raise ValueError(f"❌ Missing required environment variables: {', '.join(missing)}")

    # -------------------------
    # Database URL
    # -------------------------
    @classmethod
    def get_db_url(cls) -> str:
        """
        Safe DB URL with encoded password
        """
        password = quote_plus(cls.DB_PASSWORD)

        return (
            f"postgresql://{cls.DB_USER}:{password}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        )


# -------------------------
# Cached Config Instance
# -------------------------
@lru_cache()
def get_config() -> Config:
    Config.validate()
    return Config
