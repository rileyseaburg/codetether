"""
Configuration management for A2A Server.
"""

import os
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ServerConfig(BaseModel):
    """Configuration for the A2A server."""

    host: str = '0.0.0.0'
    port: int = 8000
    redis_url: str = 'redis://localhost:6379'
    database_url: str = ''
    auth_enabled: bool = False
    auth_tokens: Optional[Dict[str, str]] = None
    log_level: str = 'INFO'
    # Agent host configuration - use host.docker.internal for container->host communication
    # Accepts AGENT_HOST/AGENT_PORT (preferred) or legacy OPENCODE_HOST/OPENCODE_PORT
    agent_host: str = 'localhost'
    agent_port: int = 9777
    # Backward-compatible aliases
    agent_host: str = 'localhost'
    agent_port: int = 9777


class AgentConfig(BaseModel):
    """Configuration for an A2A agent."""

    name: str
    description: str
    organization: str
    organization_url: str
    base_url: Optional[str] = None
    capabilities_streaming: bool = True
    capabilities_push_notifications: bool = True
    capabilities_state_history: bool = False


def load_config() -> ServerConfig:
    """Load configuration from environment variables."""
    return ServerConfig(
        host=os.getenv('A2A_HOST', '0.0.0.0'),
        port=int(os.getenv('A2A_PORT', '8000')),
        redis_url=os.getenv('A2A_REDIS_URL', 'redis://localhost:6379'),
        database_url=os.getenv('DATABASE_URL', os.getenv('A2A_DATABASE_URL', '')),
        auth_enabled=os.getenv('A2A_AUTH_ENABLED', 'false').lower() == 'true',
        auth_tokens=_parse_auth_tokens(os.getenv('A2A_AUTH_TOKENS')),
        log_level=os.getenv('A2A_LOG_LEVEL', 'INFO'),
        agent_host=os.getenv('AGENT_HOST', 'localhost'),
        agent_port=int(os.getenv('AGENT_PORT', '9777')),
    )


def _parse_auth_tokens(tokens_str: Optional[str]) -> Optional[Dict[str, str]]:
    """Parse auth tokens from environment variable."""
    if not tokens_str:
        return None

    tokens = {}
    for token_pair in tokens_str.split(','):
        if ':' in token_pair:
            name, token = token_pair.split(':', 1)
            tokens[name.strip()] = token.strip()

    return tokens if tokens else None


def create_agent_config(
    name: str,
    description: str,
    organization: str = 'A2A Server',
    organization_url: str = 'https://github.com/rileyseaburg/codetether',
    port: Optional[int] = None,
) -> AgentConfig:
    """Create an agent configuration."""
    base_url = os.getenv('A2A_AGENT_URL')
    if not base_url and port and port != 8000:
        base_url = f'http://localhost:{port}'

    return AgentConfig(
        name=name,
        description=description,
        organization=organization,
        organization_url=organization_url,
        base_url=base_url,
    )
