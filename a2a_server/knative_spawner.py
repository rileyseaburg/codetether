"""
Knative Spawner for per-session agent workers.

This module manages the lifecycle of Knative Services and Triggers for
on-demand agent worker instances. Each session gets its own isolated
Knative Service that scales to zero when idle.

Architecture:
- Templates stored in ConfigMap (created by Helm chart)
- Service + Trigger created dynamically per session
- Scale-to-zero for cost efficiency
- Garbage collection for abandoned sessions

Configuration:
    KNATIVE_ENABLED: Enable Knative spawning (default: false)
    KUBERNETES_NAMESPACE: Namespace for Knative resources (default: a2a-server)

Usage:
    from a2a_server.knative_spawner import knative_spawner

    # Create a worker for a new session
    result = await knative_spawner.create_session_worker(
        session_id="abc123",
        tenant_id="tenant-xyz",
        codebase_id="codebase-456"
    )

    # Check worker status
    status = await knative_spawner.get_worker_status("abc123")

    # Cleanup old workers
    await knative_spawner.cleanup_idle_workers(max_age_hours=24)
"""

import asyncio
import logging
import os
import re
import yaml
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configuration from environment
KNATIVE_ENABLED = os.environ.get('KNATIVE_ENABLED', 'false').lower() == 'true'
KUBERNETES_NAMESPACE = os.environ.get('KUBERNETES_NAMESPACE', 'a2a-server')
CONFIGMAP_NAME = os.environ.get(
    'KNATIVE_TEMPLATE_CONFIGMAP',
    'codetether-a2a-server-knative-worker-template',
)

# Kubernetes client - imported conditionally
try:
    from kubernetes_asyncio import client, config
    from kubernetes_asyncio.client.rest import ApiException

    K8S_ASYNC_AVAILABLE = True
except ImportError:
    K8S_ASYNC_AVAILABLE = False
    logger.warning(
        'kubernetes_asyncio not installed. Knative spawning disabled. '
        'Install with: pip install kubernetes_asyncio'
    )


class WorkerStatus(str, Enum):
    """Status of a Knative session worker."""

    PENDING = 'pending'
    CREATING = 'creating'
    READY = 'ready'
    RUNNING = 'running'
    SCALED_TO_ZERO = 'scaled_to_zero'
    FAILED = 'failed'
    NOT_FOUND = 'not_found'


@dataclass
class WorkerInfo:
    """Information about a session worker."""

    session_id: str
    tenant_id: str
    codebase_id: str
    status: WorkerStatus
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'tenant_id': self.tenant_id,
            'codebase_id': self.codebase_id,
            'status': self.status.value,
            'url': self.url,
            'created_at': self.created_at.isoformat()
            if self.created_at
            else None,
            'last_active': self.last_active.isoformat()
            if self.last_active
            else None,
            'error_message': self.error_message,
        }


@dataclass
class SpawnResult:
    """Result of spawning a session worker."""

    success: bool
    session_id: str
    service_name: Optional[str] = None
    trigger_name: Optional[str] = None
    url: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'session_id': self.session_id,
            'service_name': self.service_name,
            'trigger_name': self.trigger_name,
            'url': self.url,
            'error_message': self.error_message,
        }


class KnativeSpawnerError(Exception):
    """Base exception for Knative spawner errors."""

    pass


class ConfigMapNotFoundError(KnativeSpawnerError):
    """Raised when the template ConfigMap is not found."""

    pass


class TemplateError(KnativeSpawnerError):
    """Raised when template processing fails."""

    pass


class KnativeSpawner:
    """
    Manages Knative Services and Triggers for per-session agent workers.

    Each session gets:
    - A Knative Service that runs the codetether-agent worker container
    - A Knative Trigger that routes tasks to the service

    Services scale to zero when idle and are garbage collected after max_age.
    """

    def __init__(
        self,
        namespace: str = KUBERNETES_NAMESPACE,
        configmap_name: str = CONFIGMAP_NAME,
    ):
        self.namespace = namespace
        self.configmap_name = configmap_name
        self._api_client: Optional[client.ApiClient] = None
        self._core_api: Optional[client.CoreV1Api] = None
        self._custom_api: Optional[client.CustomObjectsApi] = None
        self._initialized = False
        self._templates: Dict[str, str] = {}
        self._init_lock = asyncio.Lock()

    async def _init_client(self) -> bool:
        """Initialize the Kubernetes async client."""
        if not K8S_ASYNC_AVAILABLE:
            logger.error('kubernetes_asyncio not available')
            return False

        if self._initialized:
            return True

        async with self._init_lock:
            if self._initialized:
                return True

            try:
                # Try in-cluster config first
                try:
                    config.load_incluster_config()
                    logger.info('Loaded in-cluster Kubernetes config')
                except config.ConfigException:
                    # Fall back to kubeconfig
                    kubeconfig_path = os.environ.get(
                        'KUBECONFIG', os.path.expanduser('~/.kube/config')
                    )
                    await config.load_kube_config(config_file=kubeconfig_path)
                    logger.info(f'Loaded kubeconfig from {kubeconfig_path}')

                self._api_client = client.ApiClient()
                self._core_api = client.CoreV1Api(self._api_client)
                self._custom_api = client.CustomObjectsApi(self._api_client)
                self._initialized = True

                # Load templates from ConfigMap
                await self._load_templates()

                return True

            except Exception as e:
                logger.error(f'Failed to initialize Kubernetes client: {e}')
                return False

    async def _load_templates(self) -> None:
        """Load service and trigger templates from ConfigMap."""
        if not self._core_api:
            raise KnativeSpawnerError('Kubernetes client not initialized')

        try:
            configmap = await self._core_api.read_namespaced_config_map(
                name=self.configmap_name,
                namespace=self.namespace,
            )

            if not configmap.data:
                raise ConfigMapNotFoundError(
                    f'ConfigMap {self.configmap_name} has no data'
                )

            self._templates = configmap.data
            logger.info(
                f'Loaded {len(self._templates)} templates from ConfigMap '
                f'{self.configmap_name}'
            )

        except ApiException as e:
            if e.status == 404:
                raise ConfigMapNotFoundError(
                    f'ConfigMap {self.configmap_name} not found in namespace '
                    f'{self.namespace}. Ensure Helm chart is deployed with '
                    f'knative.enabled=true'
                )
            raise KnativeSpawnerError(f'Failed to load templates: {e}')

    def _render_template(
        self,
        template_key: str,
        session_id: str,
        tenant_id: str,
        codebase_id: str,
    ) -> Dict[str, Any]:
        """Render a template with placeholder substitution."""
        if template_key not in self._templates:
            raise TemplateError(f'Template {template_key} not found')

        template = self._templates[template_key]

        # Replace placeholders
        rendered = template.replace('SESSION_ID', session_id)
        rendered = rendered.replace('TENANT_ID', tenant_id)
        rendered = rendered.replace('CODEBASE_ID', codebase_id)

        try:
            return yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            raise TemplateError(f'Failed to parse rendered template: {e}')

    async def create_session_worker(
        self,
        session_id: str,
        tenant_id: str,
        codebase_id: str,
    ) -> SpawnResult:
        """
        Create a Knative Service and Trigger for a session.

        Args:
            session_id: Unique session identifier
            tenant_id: Tenant ID for isolation
            codebase_id: Associated codebase ID

        Returns:
            SpawnResult with service details or error
        """
        if not KNATIVE_ENABLED:
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message='Knative spawning is disabled (KNATIVE_ENABLED=false)',
            )

        if not await self._init_client():
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message='Kubernetes client initialization failed',
            )

        # Validate session_id format (alphanumeric + hyphens only)
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', session_id):
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message=f'Invalid session_id format: {session_id}. '
                'Must be lowercase alphanumeric with hyphens.',
            )

        service_name = f'codetether-session-{session_id}'
        trigger_name = f'trigger-session-{session_id}'

        logger.info(
            f'Creating Knative worker for session {session_id}, '
            f'tenant {tenant_id}, codebase {codebase_id}'
        )

        try:
            # Reload templates if not loaded
            if not self._templates:
                await self._load_templates()

            # Create Knative Service
            service_body = self._render_template(
                'service-template.yaml',
                session_id=session_id,
                tenant_id=tenant_id,
                codebase_id=codebase_id,
            )

            try:
                await self._custom_api.create_namespaced_custom_object(
                    group='serving.knative.dev',
                    version='v1',
                    namespace=self.namespace,
                    plural='services',
                    body=service_body,
                )
                logger.info(f'Created Knative Service: {service_name}')
            except ApiException as e:
                if e.status == 409:  # Already exists
                    logger.info(
                        f'Knative Service {service_name} already exists'
                    )
                else:
                    raise

            # Create Knative Trigger
            trigger_body = self._render_template(
                'trigger-template.yaml',
                session_id=session_id,
                tenant_id=tenant_id,
                codebase_id=codebase_id,
            )

            try:
                await self._custom_api.create_namespaced_custom_object(
                    group='eventing.knative.dev',
                    version='v1',
                    namespace=self.namespace,
                    plural='triggers',
                    body=trigger_body,
                )
                logger.info(f'Created Knative Trigger: {trigger_name}')
            except ApiException as e:
                if e.status == 409:  # Already exists
                    logger.info(
                        f'Knative Trigger {trigger_name} already exists'
                    )
                else:
                    # Rollback service if trigger fails
                    await self._delete_service(service_name)
                    raise

            # Get the service URL
            url = await self._get_service_url(service_name)

            return SpawnResult(
                success=True,
                session_id=session_id,
                service_name=service_name,
                trigger_name=trigger_name,
                url=url,
            )

        except ConfigMapNotFoundError as e:
            logger.error(f'ConfigMap not found: {e}')
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message=str(e),
            )
        except TemplateError as e:
            logger.error(f'Template error: {e}')
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message=str(e),
            )
        except ApiException as e:
            logger.error(f'Kubernetes API error: {e}')
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message=f'Kubernetes API error: {e.reason}',
            )
        except Exception as e:
            logger.error(f'Unexpected error creating session worker: {e}')
            return SpawnResult(
                success=False,
                session_id=session_id,
                error_message=str(e),
            )

    async def delete_session_worker(self, session_id: str) -> bool:
        """
        Delete a session's Knative Service and Trigger.

        Args:
            session_id: Session identifier

        Returns:
            True if deletion succeeded (or resources didn't exist)
        """
        if not KNATIVE_ENABLED:
            logger.warning('Knative spawning is disabled')
            return False

        if not await self._init_client():
            logger.error('Kubernetes client initialization failed')
            return False

        service_name = f'codetether-session-{session_id}'
        trigger_name = f'trigger-session-{session_id}'

        logger.info(f'Deleting Knative worker for session {session_id}')

        trigger_deleted = await self._delete_trigger(trigger_name)
        service_deleted = await self._delete_service(service_name)

        return trigger_deleted and service_deleted

    async def _delete_service(self, service_name: str) -> bool:
        """Delete a Knative Service."""
        try:
            await self._custom_api.delete_namespaced_custom_object(
                group='serving.knative.dev',
                version='v1',
                namespace=self.namespace,
                plural='services',
                name=service_name,
            )
            logger.info(f'Deleted Knative Service: {service_name}')
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(
                    f'Knative Service {service_name} not found (already deleted)'
                )
                return True
            logger.error(
                f'Failed to delete Knative Service {service_name}: {e}'
            )
            return False

    async def _delete_trigger(self, trigger_name: str) -> bool:
        """Delete a Knative Trigger."""
        try:
            await self._custom_api.delete_namespaced_custom_object(
                group='eventing.knative.dev',
                version='v1',
                namespace=self.namespace,
                plural='triggers',
                name=trigger_name,
            )
            logger.info(f'Deleted Knative Trigger: {trigger_name}')
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(
                    f'Knative Trigger {trigger_name} not found (already deleted)'
                )
                return True
            logger.error(
                f'Failed to delete Knative Trigger {trigger_name}: {e}'
            )
            return False

    async def _get_service_url(self, service_name: str) -> Optional[str]:
        """Get the URL for a Knative Service."""
        try:
            service = await self._custom_api.get_namespaced_custom_object(
                group='serving.knative.dev',
                version='v1',
                namespace=self.namespace,
                plural='services',
                name=service_name,
            )

            # URL is in status.url
            return service.get('status', {}).get('url')
        except ApiException:
            return None

    async def get_worker_status(self, session_id: str) -> WorkerInfo:
        """
        Get the status of a session worker.

        Args:
            session_id: Session identifier

        Returns:
            WorkerInfo with current status
        """
        if not KNATIVE_ENABLED:
            return WorkerInfo(
                session_id=session_id,
                tenant_id='',
                codebase_id='',
                status=WorkerStatus.NOT_FOUND,
                error_message='Knative spawning is disabled',
            )

        if not await self._init_client():
            return WorkerInfo(
                session_id=session_id,
                tenant_id='',
                codebase_id='',
                status=WorkerStatus.FAILED,
                error_message='Kubernetes client initialization failed',
            )

        service_name = f'codetether-session-{session_id}'

        try:
            service = await self._custom_api.get_namespaced_custom_object(
                group='serving.knative.dev',
                version='v1',
                namespace=self.namespace,
                plural='services',
                name=service_name,
            )

            # Extract labels
            metadata = service.get('metadata', {})
            labels = metadata.get('labels', {})
            tenant_id = labels.get('codetether.run/tenant', '')
            codebase_id = labels.get('codetether.run/codebase', '')

            # Parse timestamps
            created_at = None
            if 'creationTimestamp' in metadata:
                created_at = datetime.fromisoformat(
                    metadata['creationTimestamp'].replace('Z', '+00:00')
                )

            # Determine status from conditions
            status_obj = service.get('status', {})
            conditions = status_obj.get('conditions', [])
            url = status_obj.get('url')

            # Check for ready condition
            ready_condition = next(
                (c for c in conditions if c.get('type') == 'Ready'), None
            )

            if ready_condition:
                if ready_condition.get('status') == 'True':
                    # Check if actually running or scaled to zero
                    # Knative services with 0 pods are still "Ready"
                    status = WorkerStatus.READY
                elif ready_condition.get('status') == 'False':
                    status = WorkerStatus.FAILED
                else:
                    status = WorkerStatus.PENDING
            else:
                status = WorkerStatus.CREATING

            return WorkerInfo(
                session_id=session_id,
                tenant_id=tenant_id,
                codebase_id=codebase_id,
                status=status,
                url=url,
                created_at=created_at,
            )

        except ApiException as e:
            if e.status == 404:
                return WorkerInfo(
                    session_id=session_id,
                    tenant_id='',
                    codebase_id='',
                    status=WorkerStatus.NOT_FOUND,
                )
            logger.error(f'Failed to get worker status: {e}')
            return WorkerInfo(
                session_id=session_id,
                tenant_id='',
                codebase_id='',
                status=WorkerStatus.FAILED,
                error_message=f'API error: {e.reason}',
            )

    async def list_session_workers(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[WorkerInfo]:
        """
        List all session workers.

        Args:
            tenant_id: Filter by tenant (optional)

        Returns:
            List of WorkerInfo objects
        """
        if not KNATIVE_ENABLED:
            return []

        if not await self._init_client():
            return []

        try:
            # Build label selector
            label_selector = 'codetether.run/session'
            if tenant_id:
                label_selector = f'codetether.run/tenant={tenant_id}'

            services = await self._custom_api.list_namespaced_custom_object(
                group='serving.knative.dev',
                version='v1',
                namespace=self.namespace,
                plural='services',
                label_selector=label_selector,
            )

            workers = []
            for service in services.get('items', []):
                metadata = service.get('metadata', {})
                labels = metadata.get('labels', {})
                status_obj = service.get('status', {})

                # Extract session_id from name
                name = metadata.get('name', '')
                session_id = name.replace('codetether-session-', '')

                # Parse creation timestamp
                created_at = None
                if 'creationTimestamp' in metadata:
                    created_at = datetime.fromisoformat(
                        metadata['creationTimestamp'].replace('Z', '+00:00')
                    )

                # Determine status
                conditions = status_obj.get('conditions', [])
                ready_condition = next(
                    (c for c in conditions if c.get('type') == 'Ready'), None
                )

                if ready_condition and ready_condition.get('status') == 'True':
                    status = WorkerStatus.READY
                elif (
                    ready_condition and ready_condition.get('status') == 'False'
                ):
                    status = WorkerStatus.FAILED
                else:
                    status = WorkerStatus.PENDING

                workers.append(
                    WorkerInfo(
                        session_id=session_id,
                        tenant_id=labels.get('codetether.run/tenant', ''),
                        codebase_id=labels.get('codetether.run/codebase', ''),
                        status=status,
                        url=status_obj.get('url'),
                        created_at=created_at,
                    )
                )

            return workers

        except ApiException as e:
            logger.error(f'Failed to list session workers: {e}')
            return []

    async def cleanup_idle_workers(
        self,
        max_age_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Clean up workers that have been idle for too long.

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Dict with cleanup statistics
        """
        if not KNATIVE_ENABLED:
            return {'cleaned': 0, 'errors': 0, 'message': 'Knative disabled'}

        if not await self._init_client():
            return {'cleaned': 0, 'errors': 0, 'message': 'Client init failed'}

        logger.info(
            f'Starting cleanup of workers older than {max_age_hours} hours'
        )

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cleaned = 0
        errors = 0

        workers = await self.list_session_workers()

        for worker in workers:
            if worker.created_at and worker.created_at < cutoff:
                logger.info(
                    f'Cleaning up idle worker {worker.session_id} '
                    f'(created: {worker.created_at})'
                )
                if await self.delete_session_worker(worker.session_id):
                    cleaned += 1
                else:
                    errors += 1

        logger.info(f'Cleanup complete: {cleaned} cleaned, {errors} errors')
        return {
            'cleaned': cleaned,
            'errors': errors,
            'cutoff': cutoff.isoformat(),
        }

    async def close(self) -> None:
        """Close the Kubernetes client connection."""
        if self._api_client:
            await self._api_client.close()
            self._api_client = None
            self._core_api = None
            self._custom_api = None
            self._initialized = False
            logger.info('Knative spawner client closed')


# Global spawner instance
knative_spawner = KnativeSpawner()


# Convenience functions
async def create_session_worker(
    session_id: str,
    tenant_id: str,
    codebase_id: str,
) -> SpawnResult:
    """Create a Knative worker for a session."""
    return await knative_spawner.create_session_worker(
        session_id=session_id,
        tenant_id=tenant_id,
        codebase_id=codebase_id,
    )


async def delete_session_worker(session_id: str) -> bool:
    """Delete a session's Knative worker."""
    return await knative_spawner.delete_session_worker(session_id)


async def get_worker_status(session_id: str) -> WorkerInfo:
    """Get the status of a session worker."""
    return await knative_spawner.get_worker_status(session_id)


async def list_session_workers(
    tenant_id: Optional[str] = None,
) -> List[WorkerInfo]:
    """List all session workers."""
    return await knative_spawner.list_session_workers(tenant_id=tenant_id)


async def cleanup_idle_workers(max_age_hours: int = 24) -> Dict[str, Any]:
    """Clean up idle workers."""
    return await knative_spawner.cleanup_idle_workers(
        max_age_hours=max_age_hours
    )


# Public API
__all__ = [
    # Classes
    'KnativeSpawner',
    'WorkerStatus',
    'WorkerInfo',
    'SpawnResult',
    # Exceptions
    'KnativeSpawnerError',
    'ConfigMapNotFoundError',
    'TemplateError',
    # Global instance
    'knative_spawner',
    # Convenience functions
    'create_session_worker',
    'delete_session_worker',
    'get_worker_status',
    'list_session_workers',
    'cleanup_idle_workers',
    # Configuration
    'KNATIVE_ENABLED',
    'KUBERNETES_NAMESPACE',
]
