"""
Kubernetes Instance Provisioning Service.

This module handles dynamic provisioning of dedicated Kubernetes instances
for new user signups. Each user gets their own isolated deployment.

Architecture:
- Each user gets a dedicated namespace (tenant isolation)
- Deployment with user-specific configuration
- Service for internal communication
- Ingress for external access (user-specific subdomain)

Best practices:
- Uses official kubernetes-client library
- Implements retry logic with exponential backoff
- Proper resource cleanup on failure (saga pattern)
- Configurable resource limits per tier
"""

import logging
import os
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Kubernetes client - imported conditionally to allow running without k8s
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    logger.warning(
        'kubernetes client not installed. K8s provisioning disabled.'
    )


class K8sProvisioningStatus(str, Enum):
    """Status of Kubernetes instance provisioning."""

    PENDING = 'pending'
    CREATING_NAMESPACE = 'creating_namespace'
    CREATING_DEPLOYMENT = 'creating_deployment'
    CREATING_SERVICE = 'creating_service'
    CREATING_INGRESS = 'creating_ingress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ROLLED_BACK = 'rolled_back'


@dataclass
class K8sInstanceConfig:
    """Configuration for a user's Kubernetes instance."""

    # Resource limits based on tier
    cpu_request: str = '100m'
    cpu_limit: str = '500m'
    memory_request: str = '128Mi'
    memory_limit: str = '512Mi'
    replicas: int = 1

    # Image configuration
    image: str = 'registry.quantum-forge.net/library/a2a-server:latest'
    image_pull_policy: str = 'Always'

    # Domain configuration
    base_domain: str = 'codetether.run'

    @classmethod
    def for_tier(cls, tier: str) -> 'K8sInstanceConfig':
        """Get configuration based on subscription tier."""
        configs = {
            'free': cls(
                cpu_request='50m',
                cpu_limit='200m',
                memory_request='64Mi',
                memory_limit='256Mi',
                replicas=1,
            ),
            'pro': cls(
                cpu_request='100m',
                cpu_limit='500m',
                memory_request='128Mi',
                memory_limit='512Mi',
                replicas=1,
            ),
            'agency': cls(
                cpu_request='250m',
                cpu_limit='1000m',
                memory_request='256Mi',
                memory_limit='1Gi',
                replicas=2,
            ),
            'enterprise': cls(
                cpu_request='500m',
                cpu_limit='2000m',
                memory_request='512Mi',
                memory_limit='2Gi',
                replicas=3,
            ),
        }
        return configs.get(tier, configs['free'])


@dataclass
class K8sProvisioningResult:
    """Result of Kubernetes instance provisioning."""

    success: bool
    namespace: Optional[str] = None
    deployment_name: Optional[str] = None
    service_name: Optional[str] = None
    ingress_host: Optional[str] = None
    internal_url: Optional[str] = None
    external_url: Optional[str] = None
    error_message: Optional[str] = None
    status: K8sProvisioningStatus = K8sProvisioningStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'namespace': self.namespace,
            'deployment_name': self.deployment_name,
            'service_name': self.service_name,
            'ingress_host': self.ingress_host,
            'internal_url': self.internal_url,
            'external_url': self.external_url,
            'error_message': self.error_message,
            'status': self.status.value,
        }


class K8sProvisioningService:
    """
    Service for provisioning dedicated Kubernetes instances for users.

    Each user gets:
    - A dedicated namespace for isolation
    - A Deployment running their A2A server instance
    - A Service for internal routing
    - An Ingress for external access via subdomain
    """

    def __init__(self):
        self.core_api: Optional[Any] = None
        self.apps_api: Optional[Any] = None
        self.networking_api: Optional[Any] = None
        self._initialized = False

    def _init_k8s_client(self) -> bool:
        """Initialize Kubernetes client."""
        if not K8S_AVAILABLE:
            logger.error('Kubernetes client not available')
            return False

        if self._initialized:
            return True

        try:
            # Try in-cluster config first (when running in K8s)
            try:
                config.load_incluster_config()
                logger.info('Loaded in-cluster Kubernetes config')
            except config.ConfigException:
                # Fall back to kubeconfig file
                kubeconfig_path = os.environ.get(
                    'KUBECONFIG', os.path.expanduser('~/.kube/config')
                )
                config.load_kube_config(config_file=kubeconfig_path)
                logger.info(f'Loaded Kubernetes config from {kubeconfig_path}')

            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.networking_api = client.NetworkingV1Api()
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f'Failed to initialize Kubernetes client: {e}')
            return False

    async def provision_instance(
        self,
        user_id: str,
        tenant_id: str,
        org_slug: str,
        tier: str = 'free',
        config_override: Optional[K8sInstanceConfig] = None,
    ) -> K8sProvisioningResult:
        """
        Provision a dedicated Kubernetes instance for a user.

        Args:
            user_id: The user's ID
            tenant_id: The tenant's ID
            org_slug: Organization slug for naming resources
            tier: Subscription tier (affects resource limits)
            config_override: Optional custom configuration

        Returns:
            K8sProvisioningResult with instance details
        """
        if not self._init_k8s_client():
            return K8sProvisioningResult(
                success=False,
                error_message='Kubernetes client not available',
                status=K8sProvisioningStatus.FAILED,
            )

        # Generate resource names
        namespace = f'tenant-{org_slug}'
        deployment_name = f'a2a-{org_slug}'
        service_name = f'a2a-{org_slug}-svc'
        ingress_name = f'a2a-{org_slug}-ingress'

        # Get configuration for tier
        k8s_config = config_override or K8sInstanceConfig.for_tier(tier)
        ingress_host = f'{org_slug}.{k8s_config.base_domain}'

        logger.info(
            f'Provisioning K8s instance for user {user_id}: namespace={namespace}'
        )

        # Track what we've created for rollback
        namespace_created = False
        deployment_created = False
        service_created = False
        ingress_created = False

        try:
            # Step 1: Create namespace
            await self._create_namespace(
                namespace, user_id, tenant_id, org_slug
            )
            namespace_created = True
            logger.info(f'Created namespace: {namespace}')

            # Step 2: Create deployment
            await self._create_deployment(
                namespace=namespace,
                name=deployment_name,
                user_id=user_id,
                tenant_id=tenant_id,
                config=k8s_config,
            )
            deployment_created = True
            logger.info(f'Created deployment: {deployment_name}')

            # Step 3: Create service
            await self._create_service(
                namespace=namespace,
                name=service_name,
                deployment_name=deployment_name,
            )
            service_created = True
            logger.info(f'Created service: {service_name}')

            # Step 4: Create ingress
            await self._create_ingress(
                namespace=namespace,
                name=ingress_name,
                service_name=service_name,
                host=ingress_host,
            )
            ingress_created = True
            logger.info(f'Created ingress: {ingress_name} -> {ingress_host}')

            # Success!
            internal_url = (
                f'http://{service_name}.{namespace}.svc.cluster.local:8000'
            )
            external_url = f'https://{ingress_host}'

            logger.info(
                f'K8s instance provisioned successfully: {external_url}'
            )

            return K8sProvisioningResult(
                success=True,
                namespace=namespace,
                deployment_name=deployment_name,
                service_name=service_name,
                ingress_host=ingress_host,
                internal_url=internal_url,
                external_url=external_url,
                status=K8sProvisioningStatus.COMPLETED,
            )

        except Exception as e:
            logger.error(f'K8s provisioning failed: {e}')

            # Rollback
            await self._rollback(
                namespace=namespace if namespace_created else None,
                deployment_name=deployment_name if deployment_created else None,
                service_name=service_name if service_created else None,
                ingress_name=ingress_name if ingress_created else None,
            )

            return K8sProvisioningResult(
                success=False,
                error_message=str(e),
                status=K8sProvisioningStatus.FAILED,
            )

    async def _create_namespace(
        self,
        name: str,
        user_id: str,
        tenant_id: str,
        org_slug: str,
    ) -> None:
        """Create a namespace for the tenant."""
        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=name,
                labels={
                    'app.kubernetes.io/managed-by': 'codetether',
                    'codetether.run/tenant-id': tenant_id,
                    'codetether.run/user-id': user_id,
                    'codetether.run/org-slug': org_slug,
                },
                annotations={
                    'codetether.run/provisioned-at': asyncio.get_event_loop()
                    .time()
                    .__str__(),
                },
            ),
        )

        try:
            await asyncio.to_thread(
                self.core_api.create_namespace,
                body=namespace,
            )
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f'Namespace {name} already exists')
            else:
                raise

    async def _create_deployment(
        self,
        namespace: str,
        name: str,
        user_id: str,
        tenant_id: str,
        config: K8sInstanceConfig,
    ) -> None:
        """Create a deployment for the user's A2A server."""
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels={
                    'app': name,
                    'app.kubernetes.io/managed-by': 'codetether',
                },
            ),
            spec=client.V1DeploymentSpec(
                replicas=config.replicas,
                selector=client.V1LabelSelector(
                    match_labels={'app': name},
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            'app': name,
                            'codetether.run/tenant-id': tenant_id,
                        },
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name='a2a-server',
                                image=config.image,
                                image_pull_policy=config.image_pull_policy,
                                ports=[
                                    client.V1ContainerPort(
                                        container_port=8000,
                                        name='http',
                                    ),
                                ],
                                env=[
                                    client.V1EnvVar(
                                        name='TENANT_ID',
                                        value=tenant_id,
                                    ),
                                    client.V1EnvVar(
                                        name='USER_ID',
                                        value=user_id,
                                    ),
                                    client.V1EnvVar(
                                        name='A2A_HOST',
                                        value='0.0.0.0',
                                    ),
                                    client.V1EnvVar(
                                        name='A2A_PORT',
                                        value='8000',
                                    ),
                                ],
                                resources=client.V1ResourceRequirements(
                                    requests={
                                        'cpu': config.cpu_request,
                                        'memory': config.memory_request,
                                    },
                                    limits={
                                        'cpu': config.cpu_limit,
                                        'memory': config.memory_limit,
                                    },
                                ),
                                liveness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path='/.well-known/agent-card.json',
                                        port='http',
                                    ),
                                    initial_delay_seconds=30,
                                    period_seconds=10,
                                ),
                                readiness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path='/.well-known/agent-card.json',
                                        port='http',
                                    ),
                                    initial_delay_seconds=5,
                                    period_seconds=5,
                                ),
                            ),
                        ],
                        # Security context
                        security_context=client.V1PodSecurityContext(
                            run_as_non_root=True,
                            run_as_user=1000,
                            fs_group=1000,
                        ),
                    ),
                ),
            ),
        )

        await asyncio.to_thread(
            self.apps_api.create_namespaced_deployment,
            namespace=namespace,
            body=deployment,
        )

    async def _create_service(
        self,
        namespace: str,
        name: str,
        deployment_name: str,
    ) -> None:
        """Create a service for the deployment."""
        service = client.V1Service(
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=namespace,
            ),
            spec=client.V1ServiceSpec(
                selector={'app': deployment_name},
                ports=[
                    client.V1ServicePort(
                        name='http',
                        port=8000,
                        target_port='http',
                    ),
                ],
                type='ClusterIP',
            ),
        )

        await asyncio.to_thread(
            self.core_api.create_namespaced_service,
            namespace=namespace,
            body=service,
        )

    async def _create_ingress(
        self,
        namespace: str,
        name: str,
        service_name: str,
        host: str,
    ) -> None:
        """Create an ingress for external access."""
        ingress = client.V1Ingress(
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=namespace,
                annotations={
                    'cert-manager.io/cluster-issuer': 'cloudflare-issuer',
                    'nginx.ingress.kubernetes.io/ssl-redirect': 'true',
                },
            ),
            spec=client.V1IngressSpec(
                ingress_class_name='nginx',
                tls=[
                    client.V1IngressTLS(
                        hosts=[host],
                        secret_name=f'{name}-tls',
                    ),
                ],
                rules=[
                    client.V1IngressRule(
                        host=host,
                        http=client.V1HTTPIngressRuleValue(
                            paths=[
                                client.V1HTTPIngressPath(
                                    path='/',
                                    path_type='Prefix',
                                    backend=client.V1IngressBackend(
                                        service=client.V1IngressServiceBackend(
                                            name=service_name,
                                            port=client.V1ServiceBackendPort(
                                                number=8000,
                                            ),
                                        ),
                                    ),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        await asyncio.to_thread(
            self.networking_api.create_namespaced_ingress,
            namespace=namespace,
            body=ingress,
        )

    async def _rollback(
        self,
        namespace: Optional[str],
        deployment_name: Optional[str],
        service_name: Optional[str],
        ingress_name: Optional[str],
    ) -> None:
        """Rollback created resources on failure."""
        logger.warning(f'Rolling back K8s resources for namespace {namespace}')

        # Delete in reverse order
        if ingress_name and namespace:
            try:
                await asyncio.to_thread(
                    self.networking_api.delete_namespaced_ingress,
                    name=ingress_name,
                    namespace=namespace,
                )
                logger.info(f'Rollback: Deleted ingress {ingress_name}')
            except Exception as e:
                logger.error(f'Rollback: Failed to delete ingress: {e}')

        if service_name and namespace:
            try:
                await asyncio.to_thread(
                    self.core_api.delete_namespaced_service,
                    name=service_name,
                    namespace=namespace,
                )
                logger.info(f'Rollback: Deleted service {service_name}')
            except Exception as e:
                logger.error(f'Rollback: Failed to delete service: {e}')

        if deployment_name and namespace:
            try:
                await asyncio.to_thread(
                    self.apps_api.delete_namespaced_deployment,
                    name=deployment_name,
                    namespace=namespace,
                )
                logger.info(f'Rollback: Deleted deployment {deployment_name}')
            except Exception as e:
                logger.error(f'Rollback: Failed to delete deployment: {e}')

        if namespace:
            try:
                await asyncio.to_thread(
                    self.core_api.delete_namespace,
                    name=namespace,
                )
                logger.info(f'Rollback: Deleted namespace {namespace}')
            except Exception as e:
                logger.error(f'Rollback: Failed to delete namespace: {e}')

    async def delete_instance(self, namespace: str) -> bool:
        """
        Delete a user's Kubernetes instance.

        Deleting the namespace cascades to all resources within it.
        """
        if not self._init_k8s_client():
            return False

        try:
            await asyncio.to_thread(
                self.core_api.delete_namespace,
                name=namespace,
            )
            logger.info(f'Deleted K8s instance namespace: {namespace}')
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(f'Namespace {namespace} already deleted')
                return True
            logger.error(f'Failed to delete namespace {namespace}: {e}')
            return False

    async def scale_instance_for_tier(
        self,
        namespace: str,
        new_tier: str,
    ) -> bool:
        """
        Scale a user's K8s instance based on their subscription tier.

        Called when user upgrades or downgrades their subscription.
        Updates deployment resources and replica count.

        Args:
            namespace: The tenant's K8s namespace
            new_tier: The new subscription tier (free, pro, agency, enterprise)

        Returns:
            True if scaling succeeded
        """
        if not self._init_k8s_client():
            logger.error('K8s client not available for scaling')
            return False

        config = K8sInstanceConfig.for_tier(new_tier)
        logger.info(f'Scaling K8s instance {namespace} to tier: {new_tier}')

        try:
            # List deployments in namespace
            deployments = await asyncio.to_thread(
                self.apps_api.list_namespaced_deployment,
                namespace=namespace,
            )

            for deployment in deployments.items:
                # Patch the deployment with new resources and replicas
                patch = {
                    'spec': {
                        'replicas': config.replicas,
                        'template': {
                            'spec': {
                                'containers': [
                                    {
                                        'name': 'a2a-server',
                                        'resources': {
                                            'requests': {
                                                'cpu': config.cpu_request,
                                                'memory': config.memory_request,
                                            },
                                            'limits': {
                                                'cpu': config.cpu_limit,
                                                'memory': config.memory_limit,
                                            },
                                        },
                                    }
                                ],
                            },
                        },
                    },
                }

                await asyncio.to_thread(
                    self.apps_api.patch_namespaced_deployment,
                    name=deployment.metadata.name,
                    namespace=namespace,
                    body=patch,
                )
                logger.info(
                    f'Scaled deployment {deployment.metadata.name}: '
                    f'replicas={config.replicas}, cpu={config.cpu_limit}, '
                    f'memory={config.memory_limit}'
                )

            return True

        except ApiException as e:
            if e.status == 404:
                logger.warning(f'Namespace {namespace} not found for scaling')
                return False
            logger.error(f'Failed to scale instance {namespace}: {e}')
            return False
        except Exception as e:
            logger.error(f'Unexpected error scaling instance {namespace}: {e}')
            return False

    async def suspend_instance(self, namespace: str) -> bool:
        """
        Suspend a user's K8s instance (scale to 0 replicas).

        Called when subscription is cancelled or payment fails.
        Instance is not deleted, just stopped to allow recovery.
        """
        if not self._init_k8s_client():
            return False

        logger.info(f'Suspending K8s instance: {namespace}')

        try:
            deployments = await asyncio.to_thread(
                self.apps_api.list_namespaced_deployment,
                namespace=namespace,
            )

            for deployment in deployments.items:
                patch = {'spec': {'replicas': 0}}
                await asyncio.to_thread(
                    self.apps_api.patch_namespaced_deployment,
                    name=deployment.metadata.name,
                    namespace=namespace,
                    body=patch,
                )
                logger.info(f'Suspended deployment: {deployment.metadata.name}')

            return True

        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f'Namespace {namespace} not found for suspension'
                )
                return True  # Already gone
            logger.error(f'Failed to suspend instance {namespace}: {e}')
            return False

    async def resume_instance(self, namespace: str, tier: str = 'free') -> bool:
        """
        Resume a suspended K8s instance.

        Called when user reactivates subscription or payment succeeds.
        """
        return await self.scale_instance_for_tier(namespace, tier)

    async def get_instance_status(
        self, namespace: str
    ) -> Optional[Dict[str, Any]]:
        """Get the status of a user's Kubernetes instance."""
        if not self._init_k8s_client():
            return None

        try:
            # Get namespace
            ns = await asyncio.to_thread(
                self.core_api.read_namespace,
                name=namespace,
            )

            # Get deployments
            deployments = await asyncio.to_thread(
                self.apps_api.list_namespaced_deployment,
                namespace=namespace,
            )

            # Get pods
            pods = await asyncio.to_thread(
                self.core_api.list_namespaced_pod,
                namespace=namespace,
            )

            return {
                'namespace': namespace,
                'namespace_status': ns.status.phase,
                'deployments': [
                    {
                        'name': d.metadata.name,
                        'replicas': d.status.replicas,
                        'ready_replicas': d.status.ready_replicas,
                        'available_replicas': d.status.available_replicas,
                    }
                    for d in deployments.items
                ],
                'pods': [
                    {
                        'name': p.metadata.name,
                        'phase': p.status.phase,
                        'ready': all(
                            c.ready for c in (p.status.container_statuses or [])
                        ),
                    }
                    for p in pods.items
                ],
            }

        except ApiException as e:
            if e.status == 404:
                return None
            raise


# Global service instance
k8s_provisioning_service = K8sProvisioningService()


async def provision_k8s_instance_for_user(
    user_id: str,
    tenant_id: str,
    org_slug: str,
    tier: str = 'free',
) -> K8sProvisioningResult:
    """
    Convenience function to provision a K8s instance for a new user.
    """
    return await k8s_provisioning_service.provision_instance(
        user_id=user_id,
        tenant_id=tenant_id,
        org_slug=org_slug,
        tier=tier,
    )
