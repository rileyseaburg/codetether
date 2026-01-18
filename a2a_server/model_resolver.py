"""
Model Resolver for RLM (Routing Layer Model) subcall model resolution.

This module provides utilities for resolving which model should be used for
subcalls in multi-agent task execution. It implements a priority-based
resolution strategy with fallback chains.

Resolution Priority:
1. Task-level override (subcall_model_ref in task)
2. Server config default (A2A_RLM_DEFAULT_SUBCALL_MODEL_REF env var)
3. Fallback chain (A2A_RLM_FALLBACK_CHAIN env var)
4. Controller fallback (if A2A_RLM_ALLOW_CONTROLLER_FALLBACK=1)

Model Reference Format:
- Normalized: "provider:model" (e.g., "anthropic:claude-sonnet-4", "local:llama3.1:8b")
- OpenCode: "provider/model" (e.g., "anthropic/claude-sonnet-4")

Note: The colon split is done on FIRST colon only to handle model names
with colons (e.g., "local:llama3.1:8b" -> provider="local", model="llama3.1:8b")
"""

from __future__ import annotations

import logging
import os
from typing import List, Literal, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)


# Default fallback chain if not configured
DEFAULT_FALLBACK_CHAIN = 'zai:glm-4.7,openai:gpt-4o-mini,controller'


class ModelResolutionResult(TypedDict):
    """Result of model resolution for subcalls."""

    resolved_subcall_model_ref: str
    resolved_subcall_source: Literal['task', 'config', 'fallback', 'controller']
    resolved_subcall_warning: Optional[str]


class NoEligibleModelError(Exception):
    """Raised when no eligible model is found and controller fallback is not allowed."""

    def __init__(
        self,
        requested_ref: Optional[str] = None,
        available_models: Optional[List[str]] = None,
    ):
        self.requested_ref = requested_ref
        self.available_models = available_models or []
        msg = 'No eligible model found for subcall execution'
        if requested_ref:
            msg += f' (requested: {requested_ref})'
        if available_models:
            msg += f'. Available models: {", ".join(available_models)}'
        else:
            msg += '. No models available on worker.'
        super().__init__(msg)


def parse_normalized_ref(ref: str) -> Tuple[str, str]:
    """
    Parse a normalized model reference into (provider, model).

    Splits on the FIRST colon only to handle model names with colons.

    Args:
        ref: Normalized model reference (e.g., "anthropic:claude-sonnet-4",
             "local:llama3.1:8b", "openai:gpt-4o-mini")

    Returns:
        Tuple of (provider, model)

    Raises:
        ValueError: If the reference format is invalid

    Examples:
        >>> parse_normalized_ref('anthropic:claude-sonnet-4')
        ("anthropic", "claude-sonnet-4")

        >>> parse_normalized_ref('local:llama3.1:8b')
        ("local", "llama3.1:8b")

        >>> parse_normalized_ref('openai:gpt-4o-mini')
        ("openai", "gpt-4o-mini")
    """
    if not ref:
        raise ValueError('Model reference cannot be empty')

    if ':' not in ref:
        raise ValueError(
            f"Invalid model reference format: '{ref}'. "
            "Expected 'provider:model' format (e.g., 'anthropic:claude-sonnet-4')"
        )

    # Split on first colon only
    parts = ref.split(':', 1)
    provider = parts[0].strip()
    model = parts[1].strip()

    if not provider:
        raise ValueError(
            f"Provider cannot be empty in model reference: '{ref}'"
        )
    if not model:
        raise ValueError(f"Model cannot be empty in model reference: '{ref}'")

    return (provider, model)


def to_opencode_format(ref: str) -> str:
    """
    Convert normalized model reference to OpenCode format.

    Converts "provider:model" to "provider/model" format used by OpenCode.

    Args:
        ref: Normalized model reference (e.g., "anthropic:claude-sonnet-4")

    Returns:
        OpenCode format reference (e.g., "anthropic/claude-sonnet-4")

    Examples:
        >>> to_opencode_format('anthropic:claude-sonnet-4')
        "anthropic/claude-sonnet-4"

        >>> to_opencode_format('local:llama3.1:8b')
        "local/llama3.1:8b"
    """
    provider, model = parse_normalized_ref(ref)
    return f'{provider}/{model}'


def from_opencode_format(ref: str) -> str:
    """
    Convert OpenCode format to normalized model reference.

    Converts "provider/model" to "provider:model" format.

    Args:
        ref: OpenCode format reference (e.g., "anthropic/claude-sonnet-4")

    Returns:
        Normalized model reference (e.g., "anthropic:claude-sonnet-4")

    Examples:
        >>> from_opencode_format('anthropic/claude-sonnet-4')
        "anthropic:claude-sonnet-4"

        >>> from_opencode_format('local/llama3.1:8b')
        "local:llama3.1:8b"
    """
    if not ref:
        raise ValueError('Model reference cannot be empty')

    if '/' not in ref:
        raise ValueError(
            f"Invalid OpenCode model reference format: '{ref}'. "
            "Expected 'provider/model' format (e.g., 'anthropic/claude-sonnet-4')"
        )

    # Split on first slash only
    parts = ref.split('/', 1)
    provider = parts[0].strip()
    model = parts[1].strip()

    if not provider:
        raise ValueError(
            f"Provider cannot be empty in model reference: '{ref}'"
        )
    if not model:
        raise ValueError(f"Model cannot be empty in model reference: '{ref}'")

    return f'{provider}:{model}'


def is_model_available(model_ref: str, models_supported: List[str]) -> bool:
    """
    Check if a model reference is available in the worker's supported models.

    Args:
        model_ref: Normalized model reference to check
        models_supported: List of model references the worker supports

    Returns:
        True if the model is available, False otherwise
    """
    if not models_supported:
        return False

    # Exact match
    if model_ref in models_supported:
        return True

    # Try parsing and comparing provider:model
    try:
        provider, model = parse_normalized_ref(model_ref)

        for supported in models_supported:
            try:
                sup_provider, sup_model = parse_normalized_ref(supported)
                if provider == sup_provider and model == sup_model:
                    return True
            except ValueError:
                # Skip invalid entries
                continue
    except ValueError:
        pass

    return False


def get_fallback_chain() -> List[str]:
    """
    Get the fallback chain from environment or default.

    Returns:
        List of model references to try in order
    """
    chain_str = os.environ.get('A2A_RLM_FALLBACK_CHAIN', DEFAULT_FALLBACK_CHAIN)
    return [ref.strip() for ref in chain_str.split(',') if ref.strip()]


def is_controller_fallback_allowed() -> bool:
    """
    Check if controller fallback is allowed.

    Returns:
        True if A2A_RLM_ALLOW_CONTROLLER_FALLBACK=1
    """
    return os.environ.get('A2A_RLM_ALLOW_CONTROLLER_FALLBACK', '0') == '1'


def get_default_subcall_model() -> Optional[str]:
    """
    Get the default subcall model from environment.

    Returns:
        Default model reference or None if not configured
    """
    return os.environ.get('A2A_RLM_DEFAULT_SUBCALL_MODEL_REF')


def resolve_subcall_model_ref(
    models_supported: List[str],
    subcall_model_ref: Optional[str] = None,
) -> ModelResolutionResult:
    """
    Resolve which model should be used for subcall execution.

    Resolution priority:
    1. Task-level override (subcall_model_ref parameter)
    2. Server config default (A2A_RLM_DEFAULT_SUBCALL_MODEL_REF env var)
    3. Fallback chain (A2A_RLM_FALLBACK_CHAIN env var)
    4. Controller fallback (if A2A_RLM_ALLOW_CONTROLLER_FALLBACK=1)

    Args:
        models_supported: List of model references the worker supports
        subcall_model_ref: Task-level model override (highest priority)

    Returns:
        ModelResolutionResult with:
        - resolved_subcall_model_ref: The resolved model reference
        - resolved_subcall_source: Where the resolution came from
        - resolved_subcall_warning: Warning message if using controller fallback

    Raises:
        NoEligibleModelError: If no eligible model found and controller
                              fallback is not allowed

    Examples:
        >>> # Task-level override
        >>> resolve_subcall_model_ref(
        ...     models_supported=['anthropic:claude-sonnet-4'],
        ...     subcall_model_ref='anthropic:claude-sonnet-4',
        ... )
        {
            "resolved_subcall_model_ref": "anthropic:claude-sonnet-4",
            "resolved_subcall_source": "task",
            "resolved_subcall_warning": None
        }

        >>> # Fallback chain
        >>> resolve_subcall_model_ref(
        ...     models_supported=['openai:gpt-4o-mini'], subcall_model_ref=None
        ... )
        {
            "resolved_subcall_model_ref": "openai:gpt-4o-mini",
            "resolved_subcall_source": "fallback",
            "resolved_subcall_warning": None
        }
    """
    # Priority 1: Task-level override
    if subcall_model_ref:
        if is_model_available(subcall_model_ref, models_supported):
            logger.debug(
                f'Resolved subcall model from task override: {subcall_model_ref}'
            )
            return ModelResolutionResult(
                resolved_subcall_model_ref=subcall_model_ref,
                resolved_subcall_source='task',
                resolved_subcall_warning=None,
            )
        else:
            logger.warning(
                f"Task-level subcall_model_ref '{subcall_model_ref}' not available "
                f'on worker. Available: {models_supported}. Trying fallbacks.'
            )

    # Priority 2: Server config default
    default_model = get_default_subcall_model()
    if default_model:
        if is_model_available(default_model, models_supported):
            logger.debug(
                f'Resolved subcall model from config default: {default_model}'
            )
            return ModelResolutionResult(
                resolved_subcall_model_ref=default_model,
                resolved_subcall_source='config',
                resolved_subcall_warning=None,
            )
        else:
            logger.debug(
                f"Config default '{default_model}' not available. Trying fallback chain."
            )

    # Priority 3: Fallback chain
    fallback_chain = get_fallback_chain()
    for ref in fallback_chain:
        # Special "controller" token in fallback chain
        if ref.lower() == 'controller':
            continue  # Handle controller separately after chain

        if is_model_available(ref, models_supported):
            logger.debug(f'Resolved subcall model from fallback chain: {ref}')
            return ModelResolutionResult(
                resolved_subcall_model_ref=ref,
                resolved_subcall_source='fallback',
                resolved_subcall_warning=None,
            )

    # Priority 4: Controller fallback
    if is_controller_fallback_allowed():
        # Use first available model as controller fallback
        if models_supported:
            controller_model = models_supported[0]
            logger.warning(
                f'Using controller fallback model: {controller_model}. '
                'No preferred model was available.'
            )
            return ModelResolutionResult(
                resolved_subcall_model_ref=controller_model,
                resolved_subcall_source='controller',
                resolved_subcall_warning=(
                    f"Using controller fallback model '{controller_model}'. "
                    'No preferred model from task, config, or fallback chain was available.'
                ),
            )

    # No eligible model found
    requested = subcall_model_ref or default_model or 'any from fallback chain'
    raise NoEligibleModelError(
        requested_ref=requested,
        available_models=models_supported,
    )


def resolve_with_worker(
    worker_models: List[str],
    task_subcall_model_ref: Optional[str] = None,
) -> ModelResolutionResult:
    """
    Convenience function to resolve subcall model with worker's models.

    This is the main entry point for model resolution in task execution.

    Args:
        worker_models: List of models the worker supports (from worker.models_supported)
        task_subcall_model_ref: Optional task-level model override

    Returns:
        ModelResolutionResult with resolved model and metadata

    Raises:
        NoEligibleModelError: If no eligible model found
    """
    return resolve_subcall_model_ref(
        models_supported=worker_models,
        subcall_model_ref=task_subcall_model_ref,
    )


__all__ = [
    # Core functions
    'parse_normalized_ref',
    'to_opencode_format',
    'from_opencode_format',
    'is_model_available',
    'resolve_subcall_model_ref',
    'resolve_with_worker',
    # Configuration functions
    'get_fallback_chain',
    'get_default_subcall_model',
    'is_controller_fallback_allowed',
    # Types
    'ModelResolutionResult',
    'NoEligibleModelError',
    # Constants
    'DEFAULT_FALLBACK_CHAIN',
]
