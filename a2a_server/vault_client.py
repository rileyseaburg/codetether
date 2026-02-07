"""
HashiCorp Vault client for A2A Server.

Provides secure storage for LLM provider API keys and other secrets.
API keys are stored per-user, tied to their Keycloak identity.

Supports both Kubernetes auth (in-cluster) and token auth (local dev).

Configuration (environment variables):
    VAULT_ADDR: Vault server URL (default: http://vault.vault.svc.cluster.local:8200)
    VAULT_TOKEN: Vault token for authentication (local dev)
    VAULT_ROLE: Kubernetes auth role (default: a2a-server)
    VAULT_MOUNT_PATH: KV secrets engine mount path (default: secret)
    VAULT_API_KEYS_PATH: Base path for API keys (default: a2a/users)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Vault configuration
VAULT_ADDR = os.environ.get(
    'VAULT_ADDR', 'http://vault.vault.svc.cluster.local:8200'
)
VAULT_TOKEN = os.environ.get('VAULT_TOKEN', '')
VAULT_ROLE = os.environ.get('VAULT_ROLE', 'a2a-server')
VAULT_MOUNT_PATH = os.environ.get('VAULT_MOUNT_PATH', 'secret')
VAULT_API_KEYS_BASE_PATH = os.environ.get('VAULT_API_KEYS_PATH', 'a2a/users')

# Kubernetes service account token path
K8S_TOKEN_PATH = '/var/run/secrets/kubernetes.io/serviceaccount/token'

# Module state
_vault_token: Optional[str] = None
_token_lock = asyncio.Lock()


# Known providers with their display names and configurations
KNOWN_PROVIDERS = {
    'anthropic': {
        'name': 'Anthropic',
        'npm': '@ai-sdk/anthropic',
        'description': 'Claude models (Opus, Sonnet, Haiku)',
    },
    'openai': {
        'name': 'OpenAI',
        'npm': '@ai-sdk/openai',
        'description': 'GPT-4, GPT-3.5, and other OpenAI models',
    },
    'google': {
        'name': 'Google AI',
        'npm': '@ai-sdk/google',
        'description': 'Gemini and other Google AI models',
    },
    'minimax': {
        'name': 'MiniMax',
        'npm': '@ai-sdk/anthropic',
        'base_url': 'https://api.minimax.io/anthropic/v1',
        'description': 'MiniMax M2 models (Anthropic-compatible API)',
    },
    'minimax-m2': {
        'name': 'MiniMax M2',
        'npm': '@ai-sdk/anthropic',
        'base_url': 'https://api.minimax.io/anthropic/v1',
        'description': 'MiniMax M2.1 early access',
        'models': {
            'MiniMax-M2.1': {
                'name': 'MiniMax M2.1',
                'reasoning': True,
                'temperature': True,
                'tool_call': True,
            },
            'MiniMax-M2': {
                'name': 'MiniMax M2',
                'reasoning': True,
                'temperature': True,
                'tool_call': True,
            },
        },
    },
    'azure': {
        'name': 'Azure OpenAI',
        'npm': '@ai-sdk/azure',
        'description': 'Azure-hosted OpenAI models',
    },
    'azure-anthropic': {
        'name': 'Azure AI Foundry (Anthropic)',
        'npm': '@ai-sdk/anthropic',
        'description': 'Claude models via Azure AI Foundry',
        'requires_base_url': True,
    },
    'deepseek': {
        'name': 'DeepSeek',
        'npm': '@ai-sdk/openai-compatible',
        'base_url': 'https://api.deepseek.com/v1',
        'description': 'DeepSeek Coder and Chat models',
    },
    'groq': {
        'name': 'Groq',
        'npm': '@ai-sdk/groq',
        'description': 'Fast inference with Groq',
    },
    'github-copilot': {
        'name': 'GitHub Copilot',
        'npm': '@ai-sdk/github-copilot',
        'description': 'GitHub Copilot (requires OAuth)',
        'auth_type': 'oauth',
    },
    'zai-coding-plan': {
        'name': 'Z.AI Coding Plan',
        'npm': '@ai-sdk/openai-compatible',
        'base_url': 'https://api.z.ai/v1',
        'description': 'Z.AI GLM models',
    },
}


class VaultClient:
    """Async client for HashiCorp Vault."""

    def __init__(self, addr: str = VAULT_ADDR):
        self.addr = addr.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_token(self) -> Optional[str]:
        """Get Vault token, using Kubernetes auth if available."""
        global _vault_token

        # Return cached token if available
        if self._token:
            return self._token

        async with _token_lock:
            # Check again after acquiring lock
            if _vault_token:
                self._token = _vault_token
                return self._token

            # Try environment variable first
            if VAULT_TOKEN:
                self._token = VAULT_TOKEN
                _vault_token = VAULT_TOKEN
                logger.info('Using Vault token from environment')
                return self._token

            # Try Kubernetes auth
            if os.path.exists(K8S_TOKEN_PATH):
                try:
                    with open(K8S_TOKEN_PATH, 'r') as f:
                        k8s_token = f.read().strip()

                    session = await self._get_session()
                    async with session.post(
                        f'{self.addr}/v1/auth/kubernetes/login',
                        json={'jwt': k8s_token, 'role': VAULT_ROLE},
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._token = data['auth']['client_token']
                            _vault_token = self._token
                            logger.info(
                                'Authenticated with Vault using Kubernetes auth'
                            )
                            return self._token
                        else:
                            error = await resp.text()
                            logger.warning(
                                f'Kubernetes auth failed: {resp.status} - {error}'
                            )
                except Exception as e:
                    logger.warning(f'Kubernetes auth error: {e}')

            logger.warning('No Vault authentication available')
            return None

    async def _request(
        self, method: str, path: str, data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make authenticated request to Vault."""
        token = await self._get_token()
        if not token:
            return None

        session = await self._get_session()
        headers = {'X-Vault-Token': token}

        url = f'{self.addr}/v1/{path}'

        try:
            async with session.request(
                method, url, headers=headers, json=data
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 204:
                    return {}
                elif resp.status == 404:
                    return None
                else:
                    error = await resp.text()
                    logger.error(
                        f'Vault request failed: {resp.status} - {error}'
                    )
                    return None
        except Exception as e:
            logger.error(f'Vault request error: {e}')
            return None

    async def read_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """Read a secret from Vault KV v2."""
        result = await self._request('GET', f'{VAULT_MOUNT_PATH}/data/{path}')
        if result and 'data' in result and 'data' in result['data']:
            return result['data']['data']
        return None

    async def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Write a secret to Vault KV v2."""
        result = await self._request(
            'POST', f'{VAULT_MOUNT_PATH}/data/{path}', {'data': data}
        )
        return result is not None

    async def delete_secret(self, path: str) -> bool:
        """Delete a secret from Vault KV v2."""
        result = await self._request(
            'DELETE', f'{VAULT_MOUNT_PATH}/data/{path}'
        )
        return result is not None

    async def list_secrets(self, path: str) -> List[str]:
        """List secrets at a path in Vault KV v2."""
        result = await self._request(
            'LIST', f'{VAULT_MOUNT_PATH}/metadata/{path}'
        )
        if result and 'data' in result and 'keys' in result['data']:
            return result['data']['keys']
        return []


# Singleton client instance
_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get the singleton Vault client instance."""
    global _client
    if _client is None:
        _client = VaultClient()
    return _client


# =============================================================================
# Per-User API Key Management Functions
# =============================================================================


def _user_api_keys_path(user_id: str) -> str:
    """Get the Vault path for a user's API keys."""
    # Sanitize user_id for use in path
    safe_user_id = user_id.replace('/', '_').replace('\\', '_')
    return f'{VAULT_API_KEYS_BASE_PATH}/{safe_user_id}/api-keys'


async def get_user_api_key(
    user_id: str, provider_id: str
) -> Optional[Dict[str, Any]]:
    """Get an API key for a specific provider for a user."""
    client = get_vault_client()
    path = f'{_user_api_keys_path(user_id)}/{provider_id}'
    return await client.read_secret(path)


async def set_user_api_key(
    user_id: str,
    provider_id: str,
    api_key: str,
    provider_name: Optional[str] = None,
    base_url: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> bool:
    """Store an API key for a provider for a specific user."""
    client = get_vault_client()
    path = f'{_user_api_keys_path(user_id)}/{provider_id}'

    # Get provider info
    provider_info = KNOWN_PROVIDERS.get(provider_id, {})

    data = {
        'api_key': api_key,
        'provider_id': provider_id,
        'provider_name': provider_name
        or provider_info.get('name', provider_id),
        'user_id': user_id,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    # Include base_url if provided or from known providers
    if base_url:
        data['base_url'] = base_url
    elif 'base_url' in provider_info:
        data['base_url'] = provider_info['base_url']

    if metadata:
        data['metadata'] = metadata

    return await client.write_secret(path, data)


async def delete_user_api_key(user_id: str, provider_id: str) -> bool:
    """Delete an API key for a user."""
    client = get_vault_client()
    path = f'{_user_api_keys_path(user_id)}/{provider_id}'
    return await client.delete_secret(path)


async def list_user_api_keys(user_id: str) -> List[str]:
    """List all configured provider IDs for a user."""
    client = get_vault_client()
    path = _user_api_keys_path(user_id)
    keys = await client.list_secrets(path)
    # Remove trailing slashes from list output
    return [k.rstrip('/') for k in keys]


async def get_all_user_api_keys(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Get all API keys for a user."""
    provider_ids = await list_user_api_keys(user_id)

    keys = {}
    for pid in provider_ids:
        key_data = await get_user_api_key(user_id, pid)
        if key_data:
            keys[pid] = key_data

    return keys


async def get_user_agent_auth_json(
    user_id: str,
) -> Dict[str, Dict[str, str]]:
    """Get all API keys for a user formatted as agent auth.json structure."""
    all_keys = await get_all_user_api_keys(user_id)

    auth_json = {}
    for pid, data in all_keys.items():
        auth_json[pid] = {
            'type': 'api',
            'key': data.get('api_key', ''),
        }

    return auth_json


async def get_user_agent_provider_config(
    user_id: str,
) -> Dict[str, Dict[str, Any]]:
    """Get provider configuration for a user's custom providers."""
    all_keys = await get_all_user_api_keys(user_id)

    provider_config = {}
    for pid, data in all_keys.items():
        # Only include custom providers that need special configuration
        if pid in KNOWN_PROVIDERS:
            provider_info = KNOWN_PROVIDERS[pid]
            if 'base_url' in provider_info or 'base_url' in data:
                provider_config[pid] = {
                    'npm': provider_info.get(
                        'npm', '@ai-sdk/openai-compatible'
                    ),
                    'name': provider_info.get('name', pid),
                    'options': {
                        'baseURL': data.get('base_url')
                        or provider_info.get('base_url'),
                    },
                }
                if 'models' in provider_info:
                    provider_config[pid]['models'] = provider_info['models']

    return provider_config


# =============================================================================
# Worker Sync Functions
# =============================================================================


async def get_worker_sync_data(user_id: str) -> Dict[str, Any]:
    """
    Get all data needed for a worker to sync a user's API keys.

    Returns:
        Dict containing:
        - auth: Agent auth.json format
        - providers: Custom provider configurations for agent config
        - updated_at: Timestamp of last update
    """
    auth_json = await get_user_agent_auth_json(user_id)
    provider_config = await get_user_agent_provider_config(user_id)

    return {
        'user_id': user_id,
        'auth': auth_json,
        'providers': provider_config,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Health Check
# =============================================================================


async def check_vault_connection() -> Dict[str, Any]:
    """Check Vault connectivity and authentication status."""
    client = get_vault_client()

    try:
        session = await client._get_session()

        # Check if Vault is reachable
        try:
            async with session.get(f'{client.addr}/v1/sys/health') as resp:
                health = await resp.json() if resp.status == 200 else {}
                connected = resp.status in (200, 429, 472, 473, 501, 503)
        except Exception:
            health = {}
            connected = False

        # Check if we can authenticate
        token = await client._get_token()

        return {
            'connected': connected,
            'authenticated': token is not None,
            'vault_addr': client.addr,
            'health': health,
        }
    except Exception as e:
        return {
            'connected': False,
            'authenticated': False,
            'vault_addr': client.addr,
            'error': str(e),
        }


# =============================================================================
# Test API Key Function
# =============================================================================


async def test_api_key(provider_id: str, api_key: str) -> Dict[str, Any]:
    """Test an API key by making a simple request to the provider."""

    # Define test endpoints for known providers
    test_configs = {
        'anthropic': {
            'url': 'https://api.anthropic.com/v1/messages',
            'headers': {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            'body': {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            },
        },
        'minimax-m2': {
            'url': 'https://api.minimax.io/anthropic/v1/messages',
            'headers': {
                'x-api-key': api_key,
                'content-type': 'application/json',
            },
            'body': {
                'model': 'MiniMax-M2',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            },
        },
        'minimax': {
            'url': 'https://api.minimax.io/anthropic/v1/messages',
            'headers': {
                'x-api-key': api_key,
                'content-type': 'application/json',
            },
            'body': {
                'model': 'MiniMax-M2',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            },
        },
        'openai': {
            'url': 'https://api.openai.com/v1/chat/completions',
            'headers': {
                'Authorization': f'Bearer {api_key}',
                'content-type': 'application/json',
            },
            'body': {
                'model': 'gpt-3.5-turbo',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            },
        },
        'deepseek': {
            'url': 'https://api.deepseek.com/v1/chat/completions',
            'headers': {
                'Authorization': f'Bearer {api_key}',
                'content-type': 'application/json',
            },
            'body': {
                'model': 'deepseek-chat',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            },
        },
    }

    if provider_id not in test_configs:
        return {
            'success': True,
            'message': f'API key saved (no test available for {provider_id})',
            'tested': False,
        }

    config = test_configs[provider_id]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                config['url'],
                headers=config['headers'],
                json=config['body'],
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    return {
                        'success': True,
                        'message': f'API key for {provider_id} is valid',
                        'tested': True,
                    }
                else:
                    error_text = await resp.text()
                    return {
                        'success': False,
                        'message': f'API key test failed: {resp.status}',
                        'error': error_text[:200],
                        'tested': True,
                    }
    except Exception as e:
        return {
            'success': False,
            'message': f'API key test failed: {str(e)}',
            'tested': True,
        }
