from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "CART3R Chess Companion API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/chess_companion"
    jwt_secret_key: str = "CHANGE-ME-TO-A-LONG-RANDOM-SECRET-BEFORE-DEPLOYMENT"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    stockfish_path: str = "stockfish"
    stockfish_depth: int = 14
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
