"""Kubernetes service-account provisioning for SPIRE workload identity."""

from http import HTTPStatus

from a2a_server.agent_identity_errors import (
    IdentityConflictError,
    IdentityUpstreamError,
)
from a2a_server.agent_identity_kube_client import ApiException, client, core_api
from a2a_server.agent_identity_kube_ownership import verify
from a2a_server.agent_identity_types import WorkloadIdentity


async def ensure_service_account(
    workload: WorkloadIdentity, persona_id: str, provisioning_id: str
) -> None:
    """Apply the stable service account selected by SPIRE's fallback CRD."""
    api_client = None
    try:
        api_client, core = await core_api()
        metadata = client.V1ObjectMeta(
            name=workload.service_account,
            labels={'app.kubernetes.io/managed-by': 'codetether'},
            annotations={
                'codetether.io/persona-id': persona_id,
                'codetether.io/provisioning-id': provisioning_id,
            },
        )
        body = client.V1ServiceAccount(metadata=metadata)
        try:
            existing = await core.read_namespaced_service_account(
                workload.service_account, workload.namespace
            )
            verify(existing, persona_id, provisioning_id)
            await core.patch_namespaced_service_account(
                workload.service_account, workload.namespace, body
            )
        except ApiException as error:
            if error.status != HTTPStatus.NOT_FOUND:
                raise
            await core.create_namespaced_service_account(
                workload.namespace, body
            )
    except IdentityConflictError:
        raise
    except Exception as error:
        raise IdentityUpstreamError(
            'Kubernetes service-account provisioning failed'
        ) from error
    finally:
        if api_client is not None:
            await api_client.close()
