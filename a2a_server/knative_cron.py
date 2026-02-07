"""
Knative-first cron reconciliation.

This module maps persisted cronjobs to Kubernetes CronJob resources so schedule
execution is driven by the cluster scheduler, not by an in-process loop.
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .database import get_pool, get_tenant_by_id
from .knative_spawner import KNATIVE_ENABLED, KUBERNETES_NAMESPACE

logger = logging.getLogger(__name__)


try:
    from kubernetes_asyncio import client, config
    from kubernetes_asyncio.client.rest import ApiException

    K8S_ASYNC_AVAILABLE = True
except ImportError:
    client = None  # type: ignore
    config = None  # type: ignore
    ApiException = Exception  # type: ignore
    K8S_ASYNC_AVAILABLE = False


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_str(name: str, default: str = '') -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def get_cron_driver() -> str:
    """
    Resolve active cron driver.

    `app`: in-process scheduler.
    `knative`: Kubernetes CronJob scheduler.
    `disabled`: no scheduler.
    """
    configured = _env_str('CRON_DRIVER', 'auto').lower()
    if configured in ('app', 'knative', 'disabled'):
        return configured
    return 'knative' if KNATIVE_ENABLED else 'app'


def is_knative_cron_requested() -> bool:
    """Return True when Knative cron is the active runtime driver."""
    return get_cron_driver() == 'knative'


def is_knative_cron_available() -> bool:
    """Return True when Knative cron can run with current runtime dependencies."""
    if not is_knative_cron_requested():
        return False
    if not KNATIVE_ENABLED:
        return False
    if not K8S_ASYNC_AVAILABLE:
        return False
    return True


class KnativeCronError(Exception):
    """Base exception for Knative cron operations."""


@dataclass
class CronReconcileResult:
    """Result of reconciling a single cronjob resource."""

    job_id: str
    action: str
    namespace: str
    resource_name: str


@dataclass
class CronReconcileSummary:
    """Summary of reconciling all cronjob resources."""

    checked: int = 0
    reconciled: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checked': self.checked,
            'reconciled': self.reconciled,
            'failed': self.failed,
            'errors': list(self.errors),
        }


class KnativeCronManager:
    """Manages Kubernetes CronJob resources for persisted cronjobs."""

    def __init__(self, default_namespace: str = KUBERNETES_NAMESPACE):
        self.default_namespace = default_namespace
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._api_client = None
        self._batch_api = None
        self._core_api = None

    async def _init_client(self) -> None:
        if self._initialized:
            return
        if not K8S_ASYNC_AVAILABLE:
            raise KnativeCronError(
                'kubernetes_asyncio is not installed; Knative cron unavailable'
            )

        async with self._init_lock:
            if self._initialized:
                return
            try:
                try:
                    config.load_incluster_config()
                    logger.info('Knative cron: loaded in-cluster kube config')
                except config.ConfigException:
                    kubeconfig_path = os.environ.get(
                        'KUBECONFIG', os.path.expanduser('~/.kube/config')
                    )
                    await config.load_kube_config(config_file=kubeconfig_path)
                    logger.info(
                        'Knative cron: loaded kubeconfig from %s',
                        kubeconfig_path,
                    )
            except Exception as e:
                raise KnativeCronError(
                    f'Failed to initialize Kubernetes config: {e}'
                ) from e

            self._api_client = client.ApiClient()
            self._batch_api = client.BatchV1Api(self._api_client)
            self._core_api = client.CoreV1Api(self._api_client)
            self._initialized = True

    def _cronjob_name(self, job_id: str) -> str:
        digest = hashlib.sha1(job_id.encode('utf-8')).hexdigest()[:20]
        return f'ct-cron-{digest}'

    async def _resolve_namespace(self, tenant_id: Optional[str]) -> str:
        default_ns = _env_str('CRON_DEFAULT_NAMESPACE', self.default_namespace)
        use_tenant_namespace = _env_bool('CRON_TENANT_NAMESPACE_MODE', False)

        if not use_tenant_namespace or not tenant_id:
            return default_ns

        tenant = await get_tenant_by_id(tenant_id)
        if not tenant:
            return default_ns

        tenant_namespace = tenant.get('k8s_namespace')
        if not tenant_namespace:
            return default_ns

        allow_cross_ns = _env_bool('CRON_ALLOW_CROSS_NAMESPACE', False)
        if not allow_cross_ns and tenant_namespace != default_ns:
            logger.warning(
                'Knative cron: tenant namespace %s ignored for tenant %s because CRON_ALLOW_CROSS_NAMESPACE=false',
                tenant_namespace,
                tenant_id,
            )
            return default_ns

        return str(tenant_namespace)

    async def _ensure_namespace_exists(self, namespace: str) -> None:
        if self._core_api is None:
            raise KnativeCronError('Kubernetes client not initialized')
        try:
            await self._core_api.read_namespace(name=namespace)
        except ApiException as e:
            if getattr(e, 'status', None) == 404:
                raise KnativeCronError(
                    f'Namespace "{namespace}" not found for cronjob resource'
                ) from e
            raise KnativeCronError(
                f'Failed to resolve namespace "{namespace}": {e}'
            ) from e

    def _build_cronjob_body(
        self,
        *,
        job_id: str,
        cron_expression: str,
        timezone: Optional[str],
        enabled: bool,
        tenant_id: Optional[str],
        namespace: str,
    ) -> Dict[str, Any]:
        internal_token = _env_str('CRON_INTERNAL_TOKEN', '')
        if not internal_token:
            raise KnativeCronError(
                'CRON_INTERNAL_TOKEN must be set when CRON_DRIVER=knative'
            )

        trigger_base_url = _env_str(
            'CRON_TRIGGER_BASE_URL', 'http://127.0.0.1:8000'
        )
        cron_image = _env_str('CRON_JOB_IMAGE', 'curlimages/curl:8.11.1')
        service_account = _env_str('CRON_JOB_SERVICE_ACCOUNT', '')
        name = self._cronjob_name(job_id)
        tenant_label = tenant_id or 'global'

        pod_spec: Dict[str, Any] = {
            'restartPolicy': 'Never',
            'containers': [
                {
                    'name': 'trigger',
                    'image': cron_image,
                    'imagePullPolicy': 'IfNotPresent',
                    'env': [
                        {
                            'name': 'CRON_TRIGGER_BASE_URL',
                            'value': trigger_base_url,
                        },
                        {'name': 'CRON_INTERNAL_TOKEN', 'value': internal_token},
                        {'name': 'CRONJOB_ID', 'value': job_id},
                    ],
                    'command': [
                        '/bin/sh',
                        '-c',
                        (
                            'set -euo pipefail; '
                            'curl -fsS --max-time 30 -X POST '
                            '"${CRON_TRIGGER_BASE_URL}/v1/cronjobs/internal/${CRONJOB_ID}/trigger" '
                            '-H "X-Cron-Signature: ${CRON_INTERNAL_TOKEN}" '
                            '-H "Content-Type: application/json"'
                        ),
                    ],
                }
            ],
        }
        if service_account:
            pod_spec['serviceAccountName'] = service_account

        body: Dict[str, Any] = {
            'apiVersion': 'batch/v1',
            'kind': 'CronJob',
            'metadata': {
                'name': name,
                'namespace': namespace,
                'labels': {
                    'app.kubernetes.io/managed-by': 'a2a-server',
                    'codetether.run/component': 'cron',
                    'codetether.run/cronjob-id': job_id,
                    'codetether.run/tenant': tenant_label,
                },
            },
            'spec': {
                'schedule': cron_expression,
                'suspend': not bool(enabled),
                'concurrencyPolicy': 'Forbid',
                'startingDeadlineSeconds': int(
                    _env_str('CRON_STARTING_DEADLINE_SECONDS', '300')
                ),
                'successfulJobsHistoryLimit': int(
                    _env_str('CRON_SUCCESS_HISTORY_LIMIT', '1')
                ),
                'failedJobsHistoryLimit': int(
                    _env_str('CRON_FAILURE_HISTORY_LIMIT', '3')
                ),
                'jobTemplate': {
                    'spec': {
                        'ttlSecondsAfterFinished': int(
                            _env_str('CRON_JOB_TTL_SECONDS', '600')
                        ),
                        'template': {
                            'metadata': {
                                'labels': {
                                    'codetether.run/cronjob-id': job_id,
                                    'codetether.run/tenant': tenant_label,
                                }
                            },
                            'spec': pod_spec,
                        },
                    }
                },
            },
        }

        if timezone:
            # Supported on modern Kubernetes versions; ignored here if unset.
            body['spec']['timeZone'] = timezone

        return body

    async def reconcile_cronjob(
        self,
        *,
        job_id: str,
        cron_expression: str,
        timezone: Optional[str],
        enabled: bool,
        tenant_id: Optional[str],
    ) -> CronReconcileResult:
        if not is_knative_cron_available():
            raise KnativeCronError('Knative cron driver is not available')

        await self._init_client()
        if self._batch_api is None:
            raise KnativeCronError('Kubernetes batch client is not initialized')

        namespace = await self._resolve_namespace(tenant_id)
        await self._ensure_namespace_exists(namespace)
        name = self._cronjob_name(job_id)

        body = self._build_cronjob_body(
            job_id=job_id,
            cron_expression=cron_expression,
            timezone=timezone,
            enabled=enabled,
            tenant_id=tenant_id,
            namespace=namespace,
        )

        action = 'created'
        try:
            await self._batch_api.read_namespaced_cron_job(
                name=name,
                namespace=namespace,
            )
            await self._batch_api.patch_namespaced_cron_job(
                name=name,
                namespace=namespace,
                body=body,
            )
            action = 'updated'
        except ApiException as e:
            if getattr(e, 'status', None) == 404:
                await self._batch_api.create_namespaced_cron_job(
                    namespace=namespace,
                    body=body,
                )
            else:
                raise KnativeCronError(
                    f'Failed to reconcile cronjob {job_id} in namespace {namespace}: {e}'
                ) from e

        return CronReconcileResult(
            job_id=job_id,
            action=action,
            namespace=namespace,
            resource_name=name,
        )

    async def delete_cronjob(
        self,
        *,
        job_id: str,
        tenant_id: Optional[str],
        namespace: Optional[str] = None,
    ) -> bool:
        if not is_knative_cron_available():
            return False

        await self._init_client()
        if self._batch_api is None:
            raise KnativeCronError('Kubernetes batch client is not initialized')

        resolved_namespace = namespace or await self._resolve_namespace(tenant_id)
        name = self._cronjob_name(job_id)

        try:
            await self._batch_api.delete_namespaced_cron_job(
                name=name,
                namespace=resolved_namespace,
            )
            return True
        except ApiException as e:
            if getattr(e, 'status', None) == 404:
                return True
            raise KnativeCronError(
                f'Failed to delete cronjob resource {name} in {resolved_namespace}: {e}'
            ) from e

    async def reconcile_all(self) -> CronReconcileSummary:
        summary = CronReconcileSummary()
        if not is_knative_cron_available():
            summary.errors.append('Knative cron driver is not available')
            return summary

        pool = await get_pool()
        if not pool:
            summary.errors.append('Database not available')
            return summary

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tenant_id, cron_expression, timezone, enabled
                FROM cronjobs
                """
            )

        summary.checked = len(rows)
        for row in rows:
            row_dict = dict(row)
            try:
                await self.reconcile_cronjob(
                    job_id=str(row_dict['id']),
                    tenant_id=str(row_dict['tenant_id'])
                    if row_dict.get('tenant_id')
                    else None,
                    cron_expression=str(row_dict['cron_expression']),
                    timezone=str(row_dict['timezone'])
                    if row_dict.get('timezone')
                    else 'UTC',
                    enabled=bool(row_dict['enabled']),
                )
                summary.reconciled += 1
            except Exception as e:
                summary.failed += 1
                summary.errors.append(
                    f'cronjob={row_dict.get("id")} reconcile failed: {e}'
                )

        return summary

    async def close(self) -> None:
        if self._api_client is not None:
            try:
                await self._api_client.close()
            except Exception:
                pass
        self._initialized = False
        self._api_client = None
        self._batch_api = None
        self._core_api = None


knative_cron_manager = KnativeCronManager()


async def reconcile_cronjob_resource(
    *,
    job_id: str,
    tenant_id: Optional[str],
    cron_expression: str,
    timezone: Optional[str],
    enabled: bool,
) -> CronReconcileResult:
    return await knative_cron_manager.reconcile_cronjob(
        job_id=job_id,
        tenant_id=tenant_id,
        cron_expression=cron_expression,
        timezone=timezone,
        enabled=enabled,
    )


async def delete_cronjob_resource(
    *,
    job_id: str,
    tenant_id: Optional[str],
    namespace: Optional[str] = None,
) -> bool:
    return await knative_cron_manager.delete_cronjob(
        job_id=job_id,
        tenant_id=tenant_id,
        namespace=namespace,
    )


async def reconcile_all_cronjob_resources() -> CronReconcileSummary:
    return await knative_cron_manager.reconcile_all()
