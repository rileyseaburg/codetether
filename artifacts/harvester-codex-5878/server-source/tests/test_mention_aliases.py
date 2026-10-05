"""Mention handling across bot aliases and issue-body mentions.

Two production gaps motivated these tests:

* `@codetether-bot handle this` was matched by substring, so the shorter
  `codetether` alias matched and left `-bot` in the text intent parsing saw.
* Filing an issue whose body mentions the bot delivers `issues`/`opened`, which
  the webhook discarded, so the bot never responded (issue #4820).
"""

from __future__ import annotations

import importlib

import pytest


def _mention(monkeypatch: pytest.MonkeyPatch, aliases: str | None = None):
    monkeypatch.delenv('CODETETHER_BOT_ALIASES', raising=False)
    if aliases is not None:
        monkeypatch.setenv('CODETETHER_BOT_ALIASES', aliases)
    return importlib.reload(
        importlib.import_module('a2a_server.github_app.mention')
    )


@pytest.mark.parametrize(
    'handle',
    ['@codetether', '@codetether-bot', '@codetether-agent', '@CodeTether-Bot'],
)
def test_every_known_identity_is_a_mention(
    monkeypatch: pytest.MonkeyPatch, handle: str
) -> None:
    mention = _mention(monkeypatch)
    assert mention.mentions_bot(f'{handle} handle this issue') is True


@pytest.mark.parametrize(
    'body',
    [
        'no mention here',
        'email codetether@example.com about it',
        '@codetethering is a different handle',
        '@codetether-botanist is someone else',
        'see https://example.com/@codetether/repo',
    ],
)
def test_near_misses_are_not_mentions(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    mention = _mention(monkeypatch)
    assert mention.mentions_bot(body) is False


def test_alias_does_not_leak_into_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mention = _mention(monkeypatch)

    stripped = mention.strip_mentions('@codetether-bot handle this issue')

    assert 'codetether' not in stripped.lower()
    assert '-bot' not in stripped.lower(), (
        'substring matching used to leave a trailing -bot in the intent text'
    )
    assert 'handle this issue' in stripped


@pytest.mark.parametrize(
    'handle', ['@codetether', '@codetether-bot', '@codetether-agent']
)
def test_fix_requests_recognized_for_all_aliases(
    monkeypatch: pytest.MonkeyPatch, handle: str
) -> None:
    mention = _mention(monkeypatch)
    assert mention.is_fix_request(f'{handle} handle this issue') is True
    assert mention.is_fix_request(f'{handle} please fix the build') is True


def test_bare_mention_is_not_a_fix_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mention = _mention(monkeypatch)
    assert mention.is_fix_request('@codetether-bot what do you think?') is False


def test_fix_request_requires_a_mention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mention = _mention(monkeypatch)
    assert mention.is_fix_request('please fix the build') is False


def test_extra_aliases_are_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mention = _mention(monkeypatch, aliases='ct-helper, @another-bot')

    assert mention.mentions_bot('@ct-helper handle this') is True
    assert mention.mentions_bot('@another-bot handle this') is True
    assert mention.mentions_bot('@codetether handle this') is True, (
        'defaults must survive configuration'
    )


def test_longer_aliases_are_matched_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mention = _mention(monkeypatch)
    aliases = mention.bot_aliases()

    lengths = [len(alias) for alias in aliases]
    assert lengths == sorted(lengths, reverse=True)
