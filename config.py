from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = ""
    SECRET_KEY: str   = "change-me"
    DEBUG: bool       = False

    # Main Azure OpenAI resource (GPT-4o for text)
    AZURE_OPENAI_API_KEY:     str = ""
    AZURE_OPENAI_ENDPOINT:    str = ""
    AZURE_OPENAI_DEPLOYMENT:  str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"

  


settings = Settings()
