"""Opaque review credential usage and repository/method boundaries."""

import importlib.machinery
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def cli(monkeypatch):
    root = Path(__file__).resolve().parents[1] / 'scripts' / 'harvester'
    monkeypatch.syspath_prepend(str(root))
    loader = importlib.machinery.SourceFileLoader(
        'harvester_cli_test', str(root / 'forgejo-cli')
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(
        module,
        'credentials',
        Mock(
            return_value=(
                'https://forge.example/api/v1',
                'owner/repo',
                'secret-canary',
            )
        ),
    )
    monkeypatch.setattr(
        module, 'request_json', Mock(return_value={'number': 5901})
    )
    return module


def test_opaque_get_needs_no_token_argument(cli, monkeypatch, capsys):
    monkeypatch.setattr(
        'sys.argv', ['forgejo-cli', 'get', '/repos/owner/repo/pulls/5901']
    )
    cli.main()
    output = capsys.readouterr()
    assert (
        '5901' in output.out and 'secret-canary' not in output.out + output.err
    )
    assert (
        cli.request_json.call_args.kwargs['headers']['Authorization']
        == 'token secret-canary'
    )


@pytest.mark.parametrize(
    'args',
    [
        ['get', '/repos/other/repo/pulls/1'],
        ['get', '/repos/owner/repo/../other'],
        ['get', 'https://evil.example/repos/owner/repo'],
        ['--base', 'https://evil.example/api/v1', 'get', '/repos/owner/repo'],
        ['post', '/repos/owner/repo/pulls', '{}'],
    ],
)
def test_scoped_credential_cannot_escape_or_write(
    cli, monkeypatch, capsys, args
):
    monkeypatch.setattr('sys.argv', ['forgejo-cli', *args])
    with pytest.raises(SystemExit):
        cli.main()
    cli.request_json.assert_not_called()
    assert 'secret-canary' not in capsys.readouterr().err


def test_diff_text_is_preserved(cli, monkeypatch, capsys):
    cli.request_json.return_value = 'diff --git a/file b/file\n'
    monkeypatch.setattr(
        'sys.argv', ['forgejo-cli', 'get', '/repos/owner/repo/pulls/5901.diff']
    )
    cli.main()
    assert capsys.readouterr().out.startswith('diff --git')
