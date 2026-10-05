"""The configured agent model must be the only model that can be dispatched.

The model reaches a worker through exactly one path:

    GITHUB_APP_MODEL_REF (server env)
      -> github_app.settings.MODEL_REF
      -> task metadata `model_ref` at enqueue time
      -> worker uses the task's model_ref

`CODETETHER_DEFAULT_MODEL` on a worker only applies to tasks that carry no
`model_ref`, so it must never disagree with the server default.

Hardcoded defaults elsewhere are the failure mode this guards: when
`GITHUB_APP_MODEL_REF` was unset, the code silently used a different provider,
which is how work was dispatched to a model nobody selected.
"""

from __future__ import annotations

import importlib
import pathlib
import re

import pytest

# The single approved agent model for this platform.
EXPECTED_MODEL = 'openai-codex/gpt-5.6-luna-fast:max'

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _settings(monkeypatch: pytest.MonkeyPatch, env: str | None = None):
    if env is None:
        monkeypatch.delenv('GITHUB_APP_MODEL_REF', raising=False)
    else:
        monkeypatch.setenv('GITHUB_APP_MODEL_REF', env)
    return importlib.reload(
        importlib.import_module('a2a_server.github_app.settings')
    )


def test_default_model_is_the_approved_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)

    assert settings.DEFAULT_MODEL_REF == EXPECTED_MODEL
    assert settings.MODEL_REF == EXPECTED_MODEL, (
        'with GITHUB_APP_MODEL_REF unset the platform must still dispatch the '
        'approved model, not a hardcoded alternative'
    )


def test_blank_env_still_resolves_to_the_approved_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, '   ')

    assert settings.MODEL_REF == EXPECTED_MODEL


def test_explicit_override_is_honoured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, 'openai-codex/some-other-model:max')

    assert settings.MODEL_REF == 'openai-codex/some-other-model:max', (
        'an operator override must still work; only the unset case is pinned'
    )


def test_no_foreign_provider_defaults_remain_in_shipped_code() -> None:
    """No shipped module may hardcode a non-approved agent model.

    Test fixtures may reference other models, and the RLM sub-call chain is a
    separate feature with its own configuration, so only `a2a_server/` is
    inspected for agent-model values.
    """
    banned = ('openrouter/', 'google/gemini-3-flash-preview')
    offenders: list[str] = []

    for path in (_REPO_ROOT / 'a2a_server').rglob('*.py'):
        text = path.read_text(encoding='utf-8', errors='replace')
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if not re.search(r'model', stripped, re.IGNORECASE):
                continue
            for token in banned:
                if token in stripped:
                    offenders.append(
                        f'{path.relative_to(_REPO_ROOT)}: {stripped[:110]}'
                    )

    assert not offenders, (
        'shipped code hardcodes a non-approved agent model:\n'
        + '\n'.join(offenders)
    )


def test_deploy_config_pins_the_approved_model() -> None:
    """The Argo Application must dispatch the approved model."""
    yaml = pytest.importorskip('yaml')
    manifest = _REPO_ROOT / 'deploy' / 'argocd' / 'application.yaml'
    values = yaml.safe_load(manifest.read_text())['spec']['source']['helm'][
        'valuesObject'
    ]

    assert values['env']['GITHUB_APP_MODEL_REF'] == EXPECTED_MODEL

    harvester = values['harvester']
    assert harvester['defaultModel'] == EXPECTED_MODEL, (
        'the worker value must not disagree with the server default'
    )
    assert harvester['defaultProvider'] == 'openai-codex'
