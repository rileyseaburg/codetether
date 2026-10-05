"""Git authentication models for workspace registration."""

from typing import Literal, Optional

from pydantic import BaseModel


class GitHubAppAuth(BaseModel):
    """GitHub App installation metadata for a repository."""

    installation_id: str
    owner: str
    repo: str
    app_id: Optional[str] = None


class GitAuthConfig(BaseModel):
    """Structured Git authentication configuration."""

    type: Literal['pat', 'oauth', 'github_app'] = 'pat'
    token: Optional[str] = None
    github_app: Optional[GitHubAppAuth] = None
