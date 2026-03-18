from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import AnyUrl


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    ai_analysis_url: AnyUrl = (
        "https://text-convector-germangch.waw0.amvera.tech/api/v1/send_to_ai_analize"
    )
    records_dir: Path = Path("records")
    database_url: str = "sqlite:///./analysis_results.db"
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    openai_model: str = "gpt-audio-mini-2025-12-15"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
