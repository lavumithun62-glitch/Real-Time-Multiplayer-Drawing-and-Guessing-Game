from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Realtime Drawing Guessing Game"
    environment: str = "development"
    secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./drawing_game.db"
    cors_origins: str = "http://localhost:5173"
    room_min_players: int = 2
    round_seconds: int = 80
    total_rounds: int = 3
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def cors_list(self): return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
settings = Settings()
