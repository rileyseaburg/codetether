"""Kubernetes async client initialization for identity provisioning."""

import os

from a2a_server.agent_identity_errors import IdentityConfigurationError


try:
    from kubernetes_asyncio import client, config
    from kubernetes_asyncio.client.rest import ApiException
except ImportError:
    client = None
    config = None
    ApiException = Exception


async def core_api() -> tuple[object, object]:
    """Return an owned API client and configured Core API."""
    if client is None or config is None:
        raise IdentityConfigurationError('kubernetes_asyncio is not installed')
    try:
        config.load_incluster_config()
    except config.ConfigException:
        await config.load_kube_config(
            config_file=os.environ.get('KUBECONFIG') or None
        )
    api_client = client.ApiClient()
    return api_client, client.CoreV1Api(api_client)
