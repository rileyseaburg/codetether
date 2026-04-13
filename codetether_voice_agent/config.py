import os

try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover - lightweight fallback
    class BaseSettings:
        def __init__(self, **kwargs):
            annotations = getattr(self.__class__, '__annotations__', {})
            config = getattr(self.__class__, 'Config', None)
            env_prefix = getattr(config, 'env_prefix', '')

            for field_name in annotations:
                env_name = f'{env_prefix}{field_name}'
                default = getattr(self.__class__, field_name, None)
                value = kwargs.get(field_name, os.getenv(env_name, default))
                setattr(self, field_name, value)


class Settings(BaseSettings):
    LIVEKIT_URL: str = 'wss://your-livekit-url.livekit.cloud'
    CODETETHER_API_URL: str = 'http://localhost:8000'
    VOICE_AGENT_BACKEND: str = 'google-realtime'
    VOICE_AGENT_LLM_MODEL: str = 'gemini-3.1-flash-live-preview'
    VOICE_AGENT_LLM_BASE_URL: str = 'https://api.z.ai/api/paas/v4'
    CODETETHER_VOICE_API_URL: str = 'http://127.0.0.1:8000'
    VOICE_AGENT_DEFAULT_VOICE_ID: str = '960f89fc'
    GOOGLE_API_KEY: str = ''
    ZAI_API_KEY: str = ''
    LOG_LEVEL: str = 'info'

    class Config:
        env_prefix = 'CODETETHER_VOICE_AGENT_'


settings = Settings()
