from codetether_voice_agent.runtime_backends import (
    DEFAULT_QWEN_VOICE_ID,
    DEFAULT_VOICE_API_URL,
    DEFAULT_ZAI_BASE_URL,
    resolve_qwen_voice_id,
    resolve_runtime_backend,
    resolve_runtime_config,
)


def _clear_voice_env(monkeypatch):
    for key in [
        "VOICE_AGENT_BACKEND",
        "CODETETHER_VOICE_AGENT_BACKEND",
        "VOICE_AGENT_LLM_MODEL",
        "VOICE_AGENT_LLM_BASE_URL",
        "VOICE_AGENT_LLM_API_KEY",
        "VOICE_AGENT_LLM_PROVIDER",
        "VOICE_AGENT_DEFAULT_VOICE_ID",
        "VOICE_AGENT_QWEN_VOICE_MAP",
        "CODETETHER_VOICE_API_URL",
        "ZAI_API_KEY",
        "OPENAI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_runtime_backend_defaults_to_glm_qwen(monkeypatch):
    _clear_voice_env(monkeypatch)

    assert resolve_runtime_backend() == "glm-qwen"


def test_runtime_config_maps_legacy_voice_ids_to_default_qwen_voice(monkeypatch):
    _clear_voice_env(monkeypatch)

    config = resolve_runtime_config("puck")

    assert config.backend == "glm-qwen"
    assert config.requested_voice_id == "puck"
    assert config.tts_voice_id == DEFAULT_QWEN_VOICE_ID
    assert config.llm_model == "glm-5"
    assert config.llm_base_url == DEFAULT_ZAI_BASE_URL
    assert config.voice_api_url == DEFAULT_VOICE_API_URL


def test_runtime_config_uses_empty_api_key_for_local_openai_compatible_gateway(monkeypatch):
    _clear_voice_env(monkeypatch)
    monkeypatch.setenv("VOICE_AGENT_LLM_BASE_URL", "http://127.0.0.1:8001/v1")

    config = resolve_runtime_config("960f89fc")

    assert config.llm_api_key == "EMPTY"


def test_qwen_voice_map_overrides_requested_voice(monkeypatch):
    _clear_voice_env(monkeypatch)
    monkeypatch.setenv(
        "VOICE_AGENT_QWEN_VOICE_MAP",
        '{"puck":"voice-riley-local","charon":"voice-deep-local"}',
    )

    assert resolve_qwen_voice_id("puck") == "voice-riley-local"
    assert resolve_qwen_voice_id("charon") == "voice-deep-local"


def test_google_backend_alias_is_normalized(monkeypatch):
    _clear_voice_env(monkeypatch)
    monkeypatch.setenv("VOICE_AGENT_BACKEND", "google")

    assert resolve_runtime_backend() == "google-realtime"
