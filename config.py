import os
from dotenv import load_dotenv


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Load the main .env first (to get ENV_FILE)
load_dotenv()

# If ENV_FILE exists, load that specific file too
env_file = os.getenv("ENV_FILE")
if env_file:
    load_dotenv(env_file)

# Application version — keep in sync with CHANGELOG.md.
APP_VERSION = "2.3.0"


class Config:
    APP_VERSION = APP_VERSION
    DEBUG = False
    TESTING = False
    # Dev-only fallback. Production refuses to boot without a real key —
    # see get_config() below.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///:memory:")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_SCHEMA = _env_flag("AUTO_CREATE_SCHEMA", False)

    # Multi-tenant domain configuration
    BASE_DOMAIN = os.getenv("BASE_DOMAIN", "localhost:5000")
    SERVER_NAME = os.getenv("SERVER_NAME", os.getenv("BASE_DOMAIN", "localhost:5000"))

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "mysql://user@localhost/foo")

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///development.db")

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///testing.db")

def get_config(env=None):
    env = env or os.getenv("ENV", "development").lower()

    if env == "production":
        # Fail closed: a guessable SECRET_KEY makes every session cookie and
        # CSRF token forgeable. Refuse to start rather than run insecure.
        if not os.getenv("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY is not set. Generate one with "
                "`python -c \"import secrets; print(secrets.token_hex(32))\"` "
                "and set it in your environment/.env before starting in production."
            )
        return ProductionConfig
    elif env == "testing":
        return TestingConfig
    else:
        return DevelopmentConfig
