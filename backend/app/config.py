from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_name: str = "Bikeable Route Finder"
    cors_origins: str = "http://localhost:5173"
    scoring_config_path: Path = REPO_ROOT / "config" / "scoring" / "v2.yaml"
    data_root: Path = REPO_ROOT / "data"
    default_city_id: str = "fixture"
    elevation_provider: str = "open_meteo"
    elevation_api_url: str = "https://api.open-meteo.com/v1/elevation"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_root / "processed"

    @property
    def raw_data_dir(self) -> Path:
        return self.data_root / "raw"

    @property
    def cache_data_dir(self) -> Path:
        return self.data_root / "cache"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


settings = Settings()
