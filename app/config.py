from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore"
    )

    database_url: str  # postgresql+psycopg://app:app@database/blog
    secret_key: str
    llm_model: str = "test"  
    llm_api_key: str = ""


settings = Settings()  