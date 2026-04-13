import pytest

from a2a_server import git_service
from a2a_server.monitor_api import WorkspaceRegistration


@pytest.mark.asyncio
async def test_issue_git_credentials_uses_host_specific_username(monkeypatch):
    async def fake_get_git_credentials(codebase_id: str):
        assert codebase_id == 'ws-1'
        return {
            'token_type': 'pat',
            'token': 'pat-secret',
            'git_url': 'https://github.com/octo/example.git',
        }

    monkeypatch.setattr(git_service, 'get_git_credentials', fake_get_git_credentials)

    creds = await git_service.issue_git_credentials(
        'ws-1',
        requested_host='github.com',
        requested_path='octo/example.git',
    )

    assert creds is not None
    assert creds['token_type'] == 'pat'
    assert creds['username'] == 'x-access-token'
    assert creds['password'] == 'pat-secret'
    assert creds['host'] == 'github.com'
    assert creds['path'] == 'octo/example.git'


@pytest.mark.asyncio
async def test_issue_git_credentials_mints_github_app_token(monkeypatch):
    async def fake_get_git_credentials(codebase_id: str):
        assert codebase_id == 'ws-gh-app'
        return {
            'token_type': 'github_app',
            'github_installation_id': '12345',
            'github_owner': 'octo',
            'github_repo': 'example',
            'git_url': 'https://github.com/octo/example.git',
        }

    async def fake_mint_token(**kwargs):
        assert kwargs['installation_id'] == '12345'
        assert kwargs['owner'] == 'octo'
        assert kwargs['repo'] == 'example'
        return {
            'token': 'ghs_installation_token',
            'expires_at': '2026-03-08T12:34:56Z',
        }

    monkeypatch.setattr(git_service, 'get_git_credentials', fake_get_git_credentials)
    monkeypatch.setattr(
        git_service,
        'mint_github_app_installation_token',
        fake_mint_token,
    )

    creds = await git_service.issue_git_credentials(
        'ws-gh-app',
        requested_host='github.com',
        requested_path='octo/example.git',
    )

    assert creds is not None
    assert creds['token_type'] == 'github_app'
    assert creds['username'] == 'x-access-token'
    assert creds['password'] == 'ghs_installation_token'
    assert creds['expires_at'] == '2026-03-08T12:34:56Z'


@pytest.mark.asyncio
async def test_issue_git_credentials_rejects_remote_mismatch(monkeypatch):
    async def fake_get_git_credentials(codebase_id: str):
        return {
            'token_type': 'pat',
            'token': 'pat-secret',
            'git_url': 'https://github.com/octo/example.git',
        }

    monkeypatch.setattr(git_service, 'get_git_credentials', fake_get_git_credentials)

    with pytest.raises(ValueError, match='Requested Git host does not match'):
        await git_service.issue_git_credentials(
            'ws-1',
            requested_host='gitlab.com',
            requested_path='octo/example.git',
        )


def test_default_clone_dir_prefers_knative_workspace_base(monkeypatch):
    monkeypatch.setenv('KNATIVE_WORKSPACE_BASE_PATH', '/workspace/repos')
    monkeypatch.setenv('GIT_CLONE_BASE', '/var/lib/codetether/repos')

    assert git_service.default_clone_dir('abc123') == '/workspace/repos/abc123'


def test_workspace_registration_accepts_github_app_auth():
    registration = WorkspaceRegistration(
        name='Example',
        git_url='https://github.com/octo/example.git',
        git_auth={
            'type': 'github_app',
            'github_app': {
                'installation_id': '12345',
                'owner': 'octo',
                'repo': 'example',
            },
        },
    )

    assert registration.git_auth is not None
    assert registration.git_auth.type == 'github_app'
    assert registration.git_auth.github_app is not None
    assert registration.git_auth.github_app.installation_id == '12345'
