"""Runtime backends for the LiveKit voice agent.

Supports:
- Google Gemini realtime audio
- OpenAI-compatible chat LLMs (for GLM-5 via Z.AI or local OpenAI-style gateways)
- Local Qwen voice API for STT/TTS
"""

from __future__ import annotations

import io
import json
import logging
import os
import uuid
import wave
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import aiohttp
import httpx
import livekit.rtc as rtc
import openai
from livekit.agents import llm, stt, tts
from livekit.agents._exceptions import APIError
from livekit.agents.inference import llm as inference_llm
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.agents.utils import is_given

logger = logging.getLogger(__name__)

DEFAULT_QWEN_VOICE_ID = "960f89fc"
DEFAULT_VOICE_API_URL = "http://127.0.0.1:8000"
DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"
LEGACY_GOOGLE_VOICE_IDS = {"puck", "charon", "kore", "fenrir", "aoede"}


@dataclass(frozen=True)
class VoiceRuntimeConfig:
    backend: str
    requested_voice_id: str
    tts_voice_id: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    llm_provider: str
    voice_api_url: str


def resolve_runtime_backend() -> str:
    """Resolve the configured runtime backend."""
    raw = (
        os.getenv("VOICE_AGENT_BACKEND")
        or os.getenv("CODETETHER_VOICE_AGENT_BACKEND")
        or "google-realtime"
    ).strip().lower()

    aliases = {
        "google": "google-realtime",
        "gemini": "google-realtime",
        "gemini-realtime": "google-realtime",
        "google-realtime": "google-realtime",
        "glm-qwen": "glm-qwen",
        "glm5-qwen": "glm-qwen",
        "glm-5-qwen": "glm-qwen",
        "zai-qwen": "glm-qwen",
    }
    return aliases.get(raw, raw)


def resolve_runtime_config(requested_voice_id: str) -> VoiceRuntimeConfig:
    """Build the active runtime configuration from environment variables."""
    backend = resolve_runtime_backend()
    llm_base_url = (
        os.getenv("VOICE_AGENT_LLM_BASE_URL") or DEFAULT_ZAI_BASE_URL
    ).strip().rstrip("/")
    llm_api_key = (
        os.getenv("VOICE_AGENT_LLM_API_KEY")
        or os.getenv("ZAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()

    if not llm_api_key and _looks_local_gateway(llm_base_url):
        llm_api_key = "EMPTY"

    return VoiceRuntimeConfig(
        backend=backend,
        requested_voice_id=requested_voice_id or DEFAULT_QWEN_VOICE_ID,
        tts_voice_id=resolve_qwen_voice_id(requested_voice_id),
        llm_model=(
            os.getenv("VOICE_AGENT_LLM_MODEL")
            or DEFAULT_GEMINI_LIVE_MODEL
        ).strip(),
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_provider=(os.getenv("VOICE_AGENT_LLM_PROVIDER") or "zai").strip(),
        voice_api_url=(
            os.getenv("CODETETHER_VOICE_API_URL") or DEFAULT_VOICE_API_URL
        ).strip().rstrip("/"),
    )


def resolve_qwen_voice_id(requested_voice_id: str | None) -> str:
    """Map the requested voice ID to a concrete Qwen voice profile ID."""
    default_voice_id = (
        os.getenv("VOICE_AGENT_DEFAULT_VOICE_ID") or DEFAULT_QWEN_VOICE_ID
    ).strip()
    requested = (requested_voice_id or "").strip()
    if not requested:
        return default_voice_id

    voice_map = _load_qwen_voice_map()
    if requested in voice_map:
        return voice_map[requested]

    if requested in LEGACY_GOOGLE_VOICE_IDS:
        return default_voice_id

    return requested


def _load_qwen_voice_map() -> dict[str, str]:
    raw = (os.getenv("VOICE_AGENT_QWEN_VOICE_MAP") or "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid VOICE_AGENT_QWEN_VOICE_MAP JSON; ignoring")
        return {}

    if not isinstance(parsed, dict):
        logger.warning("VOICE_AGENT_QWEN_VOICE_MAP must be a JSON object; ignoring")
        return {}

    return {
        str(key).strip(): str(value).strip()
        for key, value in parsed.items()
        if str(key).strip() and str(value).strip()
    }


def _looks_local_gateway(base_url: str) -> bool:
    normalized = base_url.lower()
    return any(
        token in normalized
        for token in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")
    )


class OpenAICompatibleLLM(llm.LLM):
    """OpenAI-compatible chat LLM wrapper for LiveKit Agent sessions."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        provider: str = "openai-compatible",
        strict_tool_schema: bool = False,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._model = model
        self._provider = provider
        self._strict_tool_schema = strict_tool_schema
        self._extra_kwargs = extra_kwargs or {}
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=60.0, write=60.0, pool=60.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=50,
                    keepalive_expiry=120,
                ),
            ),
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.FunctionTool | llm.RawFunctionTool | llm.ProviderTool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> inference_llm.LLMStream:
        extra = dict(self._extra_kwargs)
        if is_given(extra_kwargs):
            extra.update(extra_kwargs)

        if is_given(parallel_tool_calls):
            extra["parallel_tool_calls"] = parallel_tool_calls

        if is_given(tool_choice):
            if isinstance(tool_choice, dict):
                extra["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_choice["function"]["name"]},
                }
            else:
                extra["tool_choice"] = tool_choice

        return inference_llm.LLMStream(
            self,
            model=self._model,
            provider=None,
            strict_tool_schema=self._strict_tool_schema,
            client=self._client,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            extra_kwargs=extra,
            provider_fmt="openai",
        )

    async def aclose(self) -> None:
        await self._client.close()


class QwenLocalTTS(tts.TTS):
    """Wrap the local Qwen voice API as a LiveKit TTS provider."""

    def __init__(
        self,
        *,
        base_url: str,
        voice_id: str,
        language: str = "english",
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1,
        )
        self._base_url = base_url.rstrip("/")
        self._voice_id = voice_id
        self._language = language
        self._session: aiohttp.ClientSession | None = None

    @property
    def model(self) -> str:
        return "qwen-tts"

    @property
    def provider(self) -> str:
        return "qwen-local"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        return _QwenTTSChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    async def aclose(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


class _QwenTTSChunkedStream(tts.ChunkedStream):
    _tts: QwenLocalTTS

    async def _run(self, output_emitter: tts.tts.AudioEmitter) -> None:
        if not self.input_text.strip():
            return

        session = await self._tts._get_session()
        form = aiohttp.FormData()
        form.add_field("text", self.input_text)
        form.add_field("language", self._tts._language)

        voice_id = quote(self._tts._voice_id, safe="")
        url = f"{self._tts._base_url}/voices/{voice_id}/speak"
        async with session.post(url, data=form) as response:
            body = await response.read()
            if response.status >= 400:
                raise APIError(
                    f"Qwen TTS returned {response.status}: {body.decode('utf-8', errors='ignore')}"
                )

            request_id = response.headers.get("x-job-id") or uuid.uuid4().hex
            sample_rate, num_channels = _inspect_wav_bytes(
                body,
                fallback_sample_rate=self._tts.sample_rate,
                fallback_channels=self._tts.num_channels,
            )
            output_emitter.initialize(
                request_id=request_id,
                sample_rate=sample_rate,
                num_channels=num_channels,
                mime_type="audio/wav",
            )
            output_emitter.push(body)


class QwenLocalSTT(stt.STT):
    """Wrap the local Qwen transcription endpoint as a LiveKit STT provider."""

    def __init__(
        self,
        *,
        base_url: str,
        default_language: str = "english",
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,
                interim_results=False,
            )
        )
        self._base_url = base_url.rstrip("/")
        self._default_language = default_language
        self._session: aiohttp.ClientSession | None = None

    @property
    def model(self) -> str:
        return "qwen-transcribe"

    @property
    def provider(self) -> str:
        return "qwen-local"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    async def _recognize_impl(
        self,
        buffer: stt.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        session = await self._get_session()
        frame = rtc.combine_audio_frames(buffer)
        wav_bytes = frame.to_wav_bytes()

        form = aiohttp.FormData()
        form.add_field(
            "audio_file",
            wav_bytes,
            filename="audio.wav",
            content_type="audio/wav",
        )

        url = f"{self._base_url}/transcribe"
        async with session.post(url, data=form) as response:
            request_id = response.headers.get("x-job-id") or uuid.uuid4().hex
            if response.status >= 400:
                body = await response.text()
                raise APIError(f"Qwen STT returned {response.status}: {body}")

            body = await response.json()
            text = str(body.get("transcription", "")).strip()
            resolved_language = (
                language if is_given(language) and language else self._default_language
            )

            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                request_id=request_id,
                alternatives=[
                    stt.SpeechData(
                        language=resolved_language or self._default_language,
                        text=text,
                        confidence=1.0,
                    )
                ],
            )

    async def aclose(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


def _inspect_wav_bytes(
    audio_bytes: bytes,
    *,
    fallback_sample_rate: int,
    fallback_channels: int,
) -> tuple[int, int]:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            return wav_file.getframerate(), wav_file.getnchannels()
    except wave.Error:
        logger.warning(
            "Failed to inspect WAV header from Qwen TTS response; using fallback audio settings"
        )
        return fallback_sample_rate, fallback_channels
