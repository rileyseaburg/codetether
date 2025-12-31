import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    LIVEKIT_URL: str = 'wss://your-livekit-url.livekit.cloud'
    CODETETHER_API_URL: str = 'http://localhost:8000'
    FUNCTIONGEMMA_MODEL_PATH: str = 'google/functiongemma-2b'
    GOOGLE_API_KEY: str = ''
    LOG_LEVEL: str = 'info'

    class Config:
        env_prefix = 'CODETETHER_VOICE_AGENT_'


settings = Settings()
