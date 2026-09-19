from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/runtime/orbital.db"
    nasa_api_key: str = "DEMO_KEY"
    spacetrack_username: str = ""
    spacetrack_password: str = ""
    spacetrack_archive: str = "data/private/gp_history.json"
    auto_refresh: bool = True
    cache_dir: str = "data/runtime"
    disabled_sources: str = ""
    frozen_sources: str = ""
    admin_token: str = ""
    noaa_request_timeout_seconds: float = 10
    noaa_cache_ttl_seconds: int = 120
    proton_data_stale_minutes: int = 30


settings = Settings()
ALGORITHM_VERSION = "2.1.0"
