"""
Task orchestration policy for model and worker-personality routing.

This module provides a single decision point that can be reused by API
surfaces when creating tasks.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_COMPLEXITY_QUICK = 'quick'
_COMPLEXITY_STANDARD = 'standard'
_COMPLEXITY_DEEP = 'deep'

_TIER_FAST = 'fast'
_TIER_BALANCED = 'balanced'
_TIER_HEAVY = 'heavy'

_DEFAULT_TIER_BY_COMPLEXITY = {
    _COMPLEXITY_QUICK: _TIER_FAST,
    _COMPLEXITY_STANDARD: _TIER_BALANCED,
    _COMPLEXITY_DEEP: _TIER_HEAVY,
}

_TIER_ORDER = {
    _TIER_FAST: 0,
    _TIER_BALANCED: 1,
    _TIER_HEAVY: 2,
}


@dataclass(frozen=True)
class TaskRoutingDecision:
    """Resolved task routing decision."""

    complexity: str
    model_tier: str
    model_ref: Optional[str]
    model_source: str
    target_agent_name: Optional[str]
    worker_personality: Optional[str]


def _parse_json_env_dict(name: str) -> Dict[str, str]:
    raw = os.environ.get(name)
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except Exception:
        logger.warning(
            'Invalid JSON in %s, ignoring personality/model map', name
        )
        return {}

    if not isinstance(data, dict):
        logger.warning('Expected object JSON in %s, got %s', name, type(data))
        return {}

    parsed: Dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        k = key.strip().lower()
        v = value.strip()
        if k and v:
            parsed[k] = v
    return parsed


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        return default


def _routing_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    value = metadata.get('routing')
    if isinstance(value, dict):
        return value
    return {}


def _metadata_value(metadata: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata.get(key)
    routing = _routing_metadata(metadata)
    for key in keys:
        if key in routing:
            return routing.get(key)
    return None


def _metadata_str(metadata: Dict[str, Any], *keys: str) -> Optional[str]:
    value = _metadata_value(metadata, *keys)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_tier(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower().replace(' ', '_')
    aliases = {
        'quick': _TIER_FAST,
        'fast': _TIER_FAST,
        'small': _TIER_FAST,
        'cheap': _TIER_FAST,
        'standard': _TIER_BALANCED,
        'balanced': _TIER_BALANCED,
        'medium': _TIER_BALANCED,
        'default': _TIER_BALANCED,
        'deep': _TIER_HEAVY,
        'heavy': _TIER_HEAVY,
        'large': _TIER_HEAVY,
        'expensive': _TIER_HEAVY,
    }
    return aliases.get(normalized)


def _tier_min(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if not a:
        return b
    if not b:
        return a
    return a if _TIER_ORDER[a] <= _TIER_ORDER[b] else b


def _tier_max(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if not a:
        return b
    if not b:
        return a
    return a if _TIER_ORDER[a] >= _TIER_ORDER[b] else b


def _clamp_tier(
    tier: str,
    *,
    min_tier: Optional[str] = None,
    max_tier: Optional[str] = None,
) -> str:
    idx = _TIER_ORDER.get(tier, _TIER_ORDER[_TIER_BALANCED])
    if min_tier is not None:
        idx = max(idx, _TIER_ORDER[min_tier])
    if max_tier is not None:
        idx = min(idx, _TIER_ORDER[max_tier])
    for name, tier_idx in _TIER_ORDER.items():
        if tier_idx == idx:
            return name
    return _TIER_BALANCED


def normalize_model_ref(model_value: Optional[str]) -> Optional[str]:
    """
    Normalize model identifiers to provider:model format.

    Accepts:
    - provider:model (already normalized)
    - provider/model
    - user-friendly selectors (best effort, via agent_bridge.resolve_model)
    """
    if not model_value or not isinstance(model_value, str):
        return None

    model_value = model_value.strip()
    if not model_value:
        return None

    if ':' in model_value:
        provider, model = model_value.split(':', 1)
        provider = provider.strip()
        model = model.strip()
        if provider and model:
            return f'{provider}:{model}'
        return None

    if '/' in model_value:
        provider, model = model_value.split('/', 1)
        provider = provider.strip()
        model = model.strip()
        if provider and model:
            return f'{provider}:{model}'
        return None

    # Best effort for user-friendly selectors ("sonnet", "minimax", etc.).
    try:
        from .agent_bridge import resolve_model

        resolved = resolve_model(model_value)
        if resolved and '/' in resolved:
            provider, model = resolved.split('/', 1)
            provider = provider.strip()
            model = model.strip()
            if provider and model:
                return f'{provider}:{model}'
    except Exception:
        pass

    return None


def to_provider_model(model_ref: Optional[str]) -> Optional[str]:
    """Convert provider:model to provider/model."""
    if not model_ref:
        return None
    if ':' in model_ref:
        return model_ref.replace(':', '/', 1)
    return model_ref


def _infer_complexity(
    *,
    prompt: str,
    agent_type: str,
    files: Optional[List[str]],
    metadata: Dict[str, Any],
) -> str:
    explicit = metadata.get('complexity')
    if isinstance(explicit, str):
        explicit = explicit.strip().lower()
        if explicit in (
            _COMPLEXITY_QUICK,
            _COMPLEXITY_STANDARD,
            _COMPLEXITY_DEEP,
        ):
            return explicit

    text = (prompt or '').lower()
    score = 0

    prompt_len = len(prompt or '')
    if prompt_len > 3500:
        score += 4
    elif prompt_len > 1200:
        score += 2
    elif prompt_len < 200:
        score -= 1

    file_count = len(files or [])
    if file_count >= 12:
        score += 3
    elif file_count >= 5:
        score += 1

    if metadata.get('resume_session_id'):
        score += 1

    if agent_type in ('swarm', 'ralph', 'plan', 'architect'):
        score += 2

    deep_hints = (
        'refactor',
        'architecture',
        'distributed',
        'migration',
        'multi-step',
        'orchestrat',
        'incident',
        'root cause',
        'benchmark',
        'performance',
        'security',
        'long running',
    )
    quick_hints = (
        'typo',
        'rename',
        'quick',
        'small',
        'minor',
        'lint',
        'format',
        'readme',
        'one line',
    )

    for hint in deep_hints:
        if hint in text:
            score += 2
    for hint in quick_hints:
        if hint in text:
            score -= 1

    quick_max_score = _env_int('A2A_ROUTING_QUICK_MAX_SCORE', 1)
    deep_min_score = _env_int('A2A_ROUTING_DEEP_MIN_SCORE', 6)

    if score <= quick_max_score:
        return _COMPLEXITY_QUICK
    if score >= deep_min_score:
        return _COMPLEXITY_DEEP
    return _COMPLEXITY_STANDARD


def _resolve_model_tier(
    *,
    complexity: str,
    metadata: Dict[str, Any],
) -> str:
    # 1) Tier from complexity baseline.
    resolved_tier = _DEFAULT_TIER_BY_COMPLEXITY[complexity]

    # 2) Explicit tier override (if present).
    explicit_tier = _normalize_tier(
        _metadata_str(metadata, 'model_tier', 'tier', 'routing_model_tier')
    )
    if explicit_tier:
        resolved_tier = explicit_tier

    min_tier: Optional[str] = None
    max_tier: Optional[str] = None

    # Guardrails by inferred complexity:
    # - quick tasks should stay on fast models unless explicitly forced higher
    # - deep tasks should not drop to tiny models
    if complexity == _COMPLEXITY_QUICK:
        max_tier = _TIER_FAST
    elif complexity == _COMPLEXITY_DEEP:
        min_tier = _TIER_BALANCED

    budget_hint = _metadata_str(
        metadata, 'budget_tier', 'budget', 'routing_budget'
    )
    if budget_hint:
        normalized_budget = budget_hint.lower()
        if normalized_budget in ('low', 'cheap', 'cost', 'minimal', 'strict'):
            max_tier = _tier_min(max_tier, _TIER_BALANCED)
        if normalized_budget in ('minimal', 'strict'):
            max_tier = _tier_min(max_tier, _TIER_FAST)
        if normalized_budget in ('high', 'premium'):
            min_tier = _tier_max(min_tier, _TIER_BALANCED)

    latency_hint = _metadata_str(
        metadata,
        'latency_preference',
        'latency',
        'latency_sla',
        'routing_latency',
    )
    if latency_hint:
        normalized_latency = latency_hint.lower()
        if normalized_latency in ('low', 'urgent', 'realtime', 'realtime_ms'):
            max_tier = _tier_min(max_tier, _TIER_BALANCED)
        if normalized_latency in ('batch', 'throughput', 'quality'):
            min_tier = _tier_max(min_tier, _TIER_BALANCED)

    quality_hint = _metadata_str(
        metadata, 'quality_preference', 'quality', 'routing_quality'
    )
    if quality_hint:
        normalized_quality = quality_hint.lower()
        if normalized_quality in ('max', 'highest', 'best'):
            min_tier = _tier_max(min_tier, _TIER_HEAVY)
        elif normalized_quality in ('high', 'accuracy'):
            min_tier = _tier_max(min_tier, _TIER_BALANCED)

    min_tier = _tier_max(
        min_tier, _normalize_tier(_metadata_str(metadata, 'min_model_tier'))
    )
    max_tier = _tier_min(
        max_tier, _normalize_tier(_metadata_str(metadata, 'max_model_tier'))
    )

    return _clamp_tier(resolved_tier, min_tier=min_tier, max_tier=max_tier)


def _personality_from_inputs(
    metadata: Dict[str, Any], worker_personality: Optional[str]
) -> Optional[str]:
    value = worker_personality
    if not value:
        for key in ('worker_personality', 'personality', 'agent_personality'):
            raw = metadata.get(key)
            if isinstance(raw, str) and raw.strip():
                value = raw
                break
    if not value:
        return None
    value = value.strip()
    return value or None


def _tier_model_map() -> Dict[str, str]:
    return {
        _TIER_FAST: os.environ.get('A2A_ROUTING_MODEL_FAST', '').strip(),
        _TIER_BALANCED: os.environ.get(
            'A2A_ROUTING_MODEL_BALANCED', ''
        ).strip(),
        _TIER_HEAVY: os.environ.get('A2A_ROUTING_MODEL_HEAVY', '').strip(),
    }


def orchestrate_task_route(
    *,
    prompt: str,
    agent_type: str = 'build',
    files: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    model_ref: Optional[str] = None,
    target_agent_name: Optional[str] = None,
    worker_personality: Optional[str] = None,
) -> Tuple[TaskRoutingDecision, Dict[str, Any]]:
    """
    Build a routing decision and return enriched metadata.

    Priority order for model selection:
    1) Explicit model_ref/model provided on request/metadata
    2) Personality-specific mapping via A2A_PERSONALITY_MODEL_MAP
    3) Tier mapping via A2A_ROUTING_MODEL_* (if auto-model enabled)
    """
    source_metadata = dict(metadata or {})
    prompt = prompt or ''

    complexity = _infer_complexity(
        prompt=prompt,
        agent_type=agent_type or 'build',
        files=files,
        metadata=source_metadata,
    )
    model_tier = _resolve_model_tier(
        complexity=complexity,
        metadata=source_metadata,
    )

    personality = _personality_from_inputs(source_metadata, worker_personality)

    # Derive target agent from explicit value, metadata, or personality mapping.
    resolved_target_agent = (
        target_agent_name
        or source_metadata.get('target_agent_name')
        or source_metadata.get('agent_name')
    )
    if not resolved_target_agent and personality:
        personality_to_agent = _parse_json_env_dict(
            'A2A_PERSONALITY_AGENT_MAP'
        )
        resolved_target_agent = personality_to_agent.get(
            personality.lower(), personality
        )

    explicit_model_ref = (
        normalize_model_ref(model_ref)
        or normalize_model_ref(model)
        or normalize_model_ref(source_metadata.get('model_ref'))
        or normalize_model_ref(source_metadata.get('model'))
    )

    resolved_model_ref = explicit_model_ref
    model_source = 'explicit' if explicit_model_ref else 'none'

    if not resolved_model_ref and personality:
        personality_models = _parse_json_env_dict('A2A_PERSONALITY_MODEL_MAP')
        personality_model = personality_models.get(personality.lower())
        resolved_model_ref = normalize_model_ref(personality_model)
        if resolved_model_ref:
            model_source = 'personality_map'

    auto_model_enabled = _env_bool('A2A_ROUTING_AUTO_MODEL', False)
    if not resolved_model_ref and auto_model_enabled:
        tier_models = _tier_model_map()
        tier_model = tier_models.get(model_tier)
        resolved_model_ref = normalize_model_ref(tier_model)
        if resolved_model_ref:
            model_source = 'tier_map'

    decision = TaskRoutingDecision(
        complexity=complexity,
        model_tier=model_tier,
        model_ref=resolved_model_ref,
        model_source=model_source,
        target_agent_name=resolved_target_agent,
        worker_personality=personality,
    )

    enriched_metadata = dict(source_metadata)
    routing_meta = dict(enriched_metadata.get('routing') or {})
    routing_meta.update(
        {
            'complexity': decision.complexity,
            'model_tier': decision.model_tier,
            'model_ref': decision.model_ref,
            'model_source': decision.model_source,
            'target_agent_name': decision.target_agent_name,
            'worker_personality': decision.worker_personality,
            'policy': 'a2a.task_orchestration.v1',
        }
    )
    enriched_metadata['routing'] = routing_meta
    enriched_metadata['complexity'] = decision.complexity
    enriched_metadata['model_tier'] = decision.model_tier

    if decision.worker_personality:
        enriched_metadata.setdefault(
            'worker_personality', decision.worker_personality
        )

    if decision.target_agent_name:
        enriched_metadata.setdefault(
            'target_agent_name', decision.target_agent_name
        )

    if decision.model_ref:
        enriched_metadata['model_ref'] = decision.model_ref
        enriched_metadata.setdefault(
            'model', to_provider_model(decision.model_ref)
        )

    return decision, enriched_metadata


__all__ = [
    'TaskRoutingDecision',
    'normalize_model_ref',
    'to_provider_model',
    'orchestrate_task_route',
]
