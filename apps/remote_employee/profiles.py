"""Stable, distinct voice and personality profiles for remote employees."""

from __future__ import annotations

import hashlib

from typing import Any


VOICES = (
    'Aoede',
    'Charon',
    'Fenrir',
    'Kore',
    'Puck',
    'Zephyr',
    'Leda',
    'Orus',
    'Achernar',
    'Algenib',
    'Callirrhoe',
    'Despina',
    'Gacrux',
    'Iapetus',
    'Pulcherrima',
    'Schedar',
)
TEMPERAMENTS = (
    'warm, incisive, and optimistic',
    'calm, analytical, and quietly confident',
    'energetic, candid, and action oriented',
    'patient, curious, and evidence driven',
    'bold, imaginative, and commercially pragmatic',
    'measured, empathetic, and detail conscious',
    'witty, resourceful, and direct',
    'thoughtful, diplomatic, and systems minded',
)
CADENCES = (
    'crisp sentences with a short pause before recommendations',
    'a relaxed pace with precise technical vocabulary',
    'an upbeat pace with clear numbered next steps',
    'a conversational pace that asks one clarifying question at a time',
    'a concise executive cadence focused on outcomes and risk',
    'a reflective cadence that distinguishes facts from hypotheses',
)
COLLABORATION_STYLES = (
    'surface tradeoffs early and volunteer a concrete next action',
    'invite dissent, summarize decisions, and document owners',
    'delegate bounded work while retaining accountability for the outcome',
    'teach through examples and confirm shared understanding',
    'protect focus time and use meetings only when synchronous debate helps',
    'connect specialists and turn ambiguous goals into measurable work',
)
ACCENTS = ('#42e8d5', '#8b7cff', '#ffb86b', '#5fa8ff', '#ff6b9d', '#84f28f')


def build_profile(
    *,
    name: str,
    role: str,
    seed: str,
    unavailable_voices: set[str] | None = None,
) -> dict[str, Any]:
    """Derive a stable profile while avoiding voices used by the company."""
    unavailable_voices = unavailable_voices or set()
    digest = hashlib.sha256(seed.encode()).digest()
    voice_start = int.from_bytes(digest[:2], 'big') % len(VOICES)
    voice = next(
        (
            VOICES[(voice_start + offset) % len(VOICES)]
            for offset in range(len(VOICES))
            if VOICES[(voice_start + offset) % len(VOICES)]
            not in unavailable_voices
        ),
        VOICES[voice_start],
    )
    temperament = TEMPERAMENTS[digest[2] % len(TEMPERAMENTS)]
    cadence = CADENCES[digest[3] % len(CADENCES)]
    collaboration = COLLABORATION_STYLES[digest[4] % len(COLLABORATION_STYLES)]
    return {
        'voice': voice,
        'temperament': temperament,
        'cadence': cadence,
        'collaboration_style': collaboration,
        'accent': ACCENTS[digest[5] % len(ACCENTS)],
        'greeting': (
            f'Hello, I am {name}, your {role}. I am in the office and ready '
            'to turn our priorities into focused, verifiable work.'
        ),
        'live_model': 'gemini-3.1-flash-live-preview',
        'tts_model': 'gemini-3.1-flash-tts-preview',
    }
