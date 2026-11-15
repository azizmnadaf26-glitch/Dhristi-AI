from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "sqlite:///./screening.db"
    matlab_fake: bool = True
    jwt_secret: str = ""
    auth_enabled: bool = True
    referable_min_grade: int | None = None
    max_upload_mb: int = 15
    password_min_length: int = 10
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    access_token_minutes: int = 15
    refresh_token_hours: int = 8
    cookie_secure: bool = False
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    storage_dir: str = "storage"
    evaluation_targets: dict[str, float] = {}  # e.g. EVALUATION_TARGETS={"accuracy": 0.8} in .env
    min_image_side_px: int = 256
    max_image_pixels: int = 60_000_000
    low_confidence_threshold: float = 0.60
    cors_allowed_origins: str = ""
    rate_limit_login_per_min: int = 10
    rate_limit_upload_per_min: int = 20
    rate_limit_default_per_min: int = 240
    matlab_startup_timeout_s: float = 180
    matlab_job_timeout_s: float = 120
    matlab_sim_timeout_s: float = 600
    max_waiting_analyses: int = 50
    sweep_interval_s: int = 300


settings = Settings()


def validate_settings() -> None:
    """Refuse to start if something is unsafe or missing."""
    if settings.auth_enabled and len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    if settings.referable_min_grade is None or not (0 <= settings.referable_min_grade <= 4):
        raise RuntimeError("REFERABLE_MIN_GRADE must be an integer 0-4")
    if "*" in settings.cors_allowed_origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must list exact origins, never *")
    if settings.app_env == "production":
        if settings.matlab_fake or not settings.auth_enabled:
            raise RuntimeError("Unsafe production config")
        if not settings.cookie_secure:
            raise RuntimeError("COOKIE_SECURE must be true in production")
