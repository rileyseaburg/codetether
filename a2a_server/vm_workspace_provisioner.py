"""
VM Workspace Provisioner (KubeVirt/Harvester-compatible).

This module provisions per-workspace virtual machines via Kubernetes CRDs.
It is feature-flagged and safe to import when kubernetes_asyncio is absent.
"""

import logging
import os
import re
import shlex
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name: str, default_csv: str) -> List[str]:
    raw = os.environ.get(name, default_csv)
    values = [part.strip() for part in raw.split(',') if part.strip()]
    return values or [v.strip() for v in default_csv.split(',') if v.strip()]


VM_WORKSPACES_ENABLED = _env_bool('VM_WORKSPACES_ENABLED', False)
VM_WORKSPACE_NAMESPACE = os.environ.get(
    'VM_WORKSPACE_NAMESPACE',
    os.environ.get('KUBERNETES_NAMESPACE', 'a2a-server'),
)
VM_WORKSPACE_API_GROUP = os.environ.get('VM_WORKSPACE_API_GROUP', 'kubevirt.io')
VM_WORKSPACE_API_VERSION = os.environ.get('VM_WORKSPACE_API_VERSION', 'v1')
VM_WORKSPACE_PLURAL = os.environ.get('VM_WORKSPACE_PLURAL', 'virtualmachines')
VM_WORKSPACE_IMAGE = os.environ.get(
    'VM_WORKSPACE_DEFAULT_IMAGE',
    'quay.io/containerdisks/ubuntu:22.04',
)
VM_WORKSPACE_DEFAULT_CPU_CORES = int(
    os.environ.get('VM_WORKSPACE_DEFAULT_CPU_CORES', '2')
)
VM_WORKSPACE_DEFAULT_MEMORY = os.environ.get('VM_WORKSPACE_DEFAULT_MEMORY', '2Gi')
VM_WORKSPACE_DEFAULT_DISK_SIZE = os.environ.get(
    'VM_WORKSPACE_DEFAULT_DISK_SIZE',
    '30Gi',
)
VM_WORKSPACE_STORAGE_CLASS = os.environ.get('VM_WORKSPACE_STORAGE_CLASS', '').strip()
VM_WORKSPACE_ACCESS_MODES = _env_list(
    'VM_WORKSPACE_ACCESS_MODES',
    'ReadWriteOnce',
)
VM_WORKSPACE_PVC_PREFIX = (
    os.environ.get('VM_WORKSPACE_PVC_PREFIX', 'codetether-vm-workspace').strip()
    or 'codetether-vm-workspace'
)
VM_WORKSPACE_CREATE_SSH_SERVICE = _env_bool(
    'VM_WORKSPACE_CREATE_SSH_SERVICE',
    True,
)
VM_WORKSPACE_SSH_SERVICE_TYPE = os.environ.get(
    'VM_WORKSPACE_SSH_SERVICE_TYPE',
    'ClusterIP',
)
VM_WORKSPACE_SSH_PUBLIC_KEY = os.environ.get('VM_WORKSPACE_SSH_PUBLIC_KEY', '').strip()
VM_WORKSPACE_SSH_USER = os.environ.get('VM_WORKSPACE_SSH_USER', 'coder').strip() or 'coder'
VM_WORKSPACE_CREATE_HTTP_SERVICE = _env_bool(
    'VM_WORKSPACE_CREATE_HTTP_SERVICE',
    True,
)
VM_WORKSPACE_HTTP_SERVICE_TYPE = os.environ.get(
    'VM_WORKSPACE_HTTP_SERVICE_TYPE',
    'ClusterIP',
)
VM_WORKSPACE_HTTP_PORT = int(os.environ.get('VM_WORKSPACE_HTTP_PORT', '8080'))
VM_WORKSPACE_NODE_SELECTOR_HOSTNAME = (
    os.environ.get('VM_WORKSPACE_NODE_SELECTOR_HOSTNAME', '').strip()
)


try:
    from kubernetes_asyncio import client, config
    from kubernetes_asyncio.client.rest import ApiException

    K8S_ASYNC_AVAILABLE = True
except ImportError:
    K8S_ASYNC_AVAILABLE = False
    logger.warning(
        'kubernetes_asyncio not installed. VM workspace provisioning disabled.'
    )


def is_enabled() -> bool:
    """Whether VM workspace provisioning is enabled."""
    return VM_WORKSPACES_ENABLED


class VMWorkspaceProvisionerError(Exception):
    """Base error for VM workspace provisioning."""


@dataclass
class VMWorkspaceSpec:
    """Desired VM shape for a workspace."""

    cpu_cores: int = VM_WORKSPACE_DEFAULT_CPU_CORES
    memory: str = VM_WORKSPACE_DEFAULT_MEMORY
    disk_size: str = VM_WORKSPACE_DEFAULT_DISK_SIZE
    image: str = VM_WORKSPACE_IMAGE
    storage_class: str = VM_WORKSPACE_STORAGE_CLASS
    access_modes: List[str] = field(default_factory=lambda: list(VM_WORKSPACE_ACCESS_MODES))
    create_ssh_service: bool = VM_WORKSPACE_CREATE_SSH_SERVICE
    ssh_service_type: str = VM_WORKSPACE_SSH_SERVICE_TYPE
    ssh_user: str = VM_WORKSPACE_SSH_USER
    ssh_public_key: str = VM_WORKSPACE_SSH_PUBLIC_KEY
    create_http_service: bool = VM_WORKSPACE_CREATE_HTTP_SERVICE
    http_service_type: str = VM_WORKSPACE_HTTP_SERVICE_TYPE
    http_port: int = VM_WORKSPACE_HTTP_PORT


@dataclass
class VMWorkspaceResult:
    """Result of provisioning a workspace VM."""

    success: bool
    vm_name: Optional[str] = None
    namespace: Optional[str] = None
    pvc_name: Optional[str] = None
    ssh_service_name: Optional[str] = None
    ssh_host: Optional[str] = None
    ssh_port: int = 22
    http_service_name: Optional[str] = None
    public_url: Optional[str] = None
    status: Optional[str] = None
    already_exists: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'vm_name': self.vm_name,
            'namespace': self.namespace,
            'pvc_name': self.pvc_name,
            'ssh_service_name': self.ssh_service_name,
            'ssh_host': self.ssh_host,
            'ssh_port': self.ssh_port,
            'http_service_name': self.http_service_name,
            'public_url': self.public_url,
            'status': self.status,
            'already_exists': self.already_exists,
            'error_message': self.error_message,
        }


class VMWorkspaceProvisioner:
    """Kubernetes-backed VM workspace provisioner."""

    def __init__(self, namespace: str = VM_WORKSPACE_NAMESPACE):
        self.namespace = namespace
        self._initialized = False
        self._api_client: Optional[client.ApiClient] = None
        self._core_api: Optional[client.CoreV1Api] = None
        self._custom_api: Optional[client.CustomObjectsApi] = None

    @staticmethod
    def _sanitize_k8s_name(value: str) -> str:
        normalized = re.sub(r'[^a-z0-9-]+', '-', value.lower())
        normalized = re.sub(r'-{2,}', '-', normalized).strip('-')
        if not normalized:
            return 'workspace'
        return normalized[:63]

    def _vm_name(self, workspace_id: str) -> str:
        prefix = self._sanitize_k8s_name('codetether-vm')
        suffix = self._sanitize_k8s_name(workspace_id)
        max_suffix = max(1, 63 - len(prefix) - 1)
        return f'{prefix}-{suffix[:max_suffix]}'

    def _pvc_name(self, workspace_id: str) -> str:
        prefix = self._sanitize_k8s_name(VM_WORKSPACE_PVC_PREFIX)
        suffix = self._sanitize_k8s_name(workspace_id)
        max_suffix = max(1, 63 - len(prefix) - 1)
        return f'{prefix}-{suffix[:max_suffix]}'

    def _ssh_service_name(self, vm_name: str) -> str:
        suffix = '-ssh'
        return f'{vm_name[: 63 - len(suffix)]}{suffix}'

    def _http_service_name(self, vm_name: str) -> str:
        suffix = '-http'
        return f'{vm_name[: 63 - len(suffix)]}{suffix}'

    def _cloud_init_secret_name(self, workspace_id: str) -> str:
        suffix = '-cloudinit'
        base = self._sanitize_k8s_name(f'codetether-vm-{workspace_id}')
        return f'{base[: 63 - len(suffix)]}{suffix}'

    @staticmethod
    def _shell_quote(value: str) -> str:
        return shlex.quote(value)

    async def _init_client(self) -> bool:
        if not K8S_ASYNC_AVAILABLE:
            return False
        if self._initialized:
            return True

        try:
            try:
                config.load_incluster_config()
                logger.info('Loaded in-cluster Kubernetes config for VM provisioner')
            except config.ConfigException:
                kubeconfig_path = os.environ.get(
                    'KUBECONFIG',
                    os.path.expanduser('~/.kube/config'),
                )
                await config.load_kube_config(config_file=kubeconfig_path)
                logger.info(
                    'Loaded kubeconfig for VM provisioner from %s',
                    kubeconfig_path,
                )

            self._api_client = client.ApiClient()
            self._core_api = client.CoreV1Api(self._api_client)
            self._custom_api = client.CustomObjectsApi(self._api_client)
            self._initialized = True
            return True
        except Exception as e:
            logger.error('Failed to initialize VM provisioner client: %s', e)
            return False

    def _cloud_init_user_data(
        self,
        spec: VMWorkspaceSpec,
        bootstrap: Optional[Dict[str, str]] = None,
    ) -> str:
        ssh_section = ''
        if spec.ssh_public_key:
            ssh_section = (
                '\n    ssh_authorized_keys:\n'
                f'      - {spec.ssh_public_key}\n'
            )
        packages: List[str] = []
        write_files = ''
        bootstrap_runcmd = ''
        if bootstrap:
            packages = [
                'ca-certificates',
                'curl',
                'git',
                'openssh-server',
                'python3',
            ]
            env_body = '\n'.join(
                f"{key}={self._shell_quote(str(value))}"
                for key, value in bootstrap.items()
                if value is not None and str(value).strip()
            )
            bootstrap_script = textwrap.dedent(
                """\
                #!/bin/bash
                set -euo pipefail
                set -a
                . /etc/codetether-worker/env
                set +a
                export HOME="${HOME:-/root}"
                export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
                WORKDIR="${A2A_CODEBASES:-/workspace}"
                RUNTIME_ROOT="$WORKDIR/.codetether"
                BIN_DIR="$RUNTIME_ROOT/bin"
                TMP_DIR="$RUNTIME_ROOT/tmp"
                BIN_PATH="$BIN_DIR/codetether"
                DOWNLOAD_PATH="$TMP_DIR/codetether-download"
                ASKPASS_PATH="$BIN_DIR/codetether-vm-askpass"
                GIT_USER_NAME="${CODETETHER_GIT_USER_NAME:-${CODETETHER_WORKER_NAME:-CodeTether Agent}}"
                GIT_USER_EMAIL="${CODETETHER_GIT_USER_EMAIL:-agent@codetether.run}"
                STATUS_URL="${CODETETHER_BOOTSTRAP_STATUS_URL:-}"
                AUTH_HEADER=()
                if [ -n "${CODETETHER_WORKER_AUTH_TOKEN:-}" ]; then
                  AUTH_HEADER=(-H "Authorization: Bearer $CODETETHER_WORKER_AUTH_TOKEN")
                fi
                FAILED_STAGE=bootstrap
                trap 'rc=$?; post_status "$FAILED_STAGE" failed "Bootstrap failed during $FAILED_STAGE (exit $rc)"; exit $rc' ERR
                post_status() {
                  if [ -z "$STATUS_URL" ] || [ -z "${CODETETHER_WORKSPACE_ID:-}" ]; then
                    return 0
                  fi
                  local stage="$1"
                  local status="$2"
                  local message="$3"
                  local payload
                  payload="$(python3 - "$stage" "$status" "$message" "${CODETETHER_WORKER_NAME:-}" <<'PY'
                import json
                import sys
                stage, status, message, worker_name = sys.argv[1:5]
                print(json.dumps({
                    "stage": stage,
                    "status": status,
                    "message": message,
                    "worker_name": worker_name,
                }))
                PY
                )"
                  curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' --data "$payload" "$STATUS_URL" >/dev/null || true
                }
                if [ "${1:-}" = "--start-service" ]; then
                  FAILED_STAGE=service
                  post_status service starting "Starting CodeTether worker service"
                  systemctl daemon-reload
                  systemctl enable codetether-worker.service
                  systemctl start codetether-worker.service
                  post_status service ready "CodeTether worker service started"
                  exit 0
                fi
                post_status bootstrap starting "Bootstrap started"
                mkdir -p /etc/codetether-worker /workspace "$WORKDIR" "$BIN_DIR" "$TMP_DIR"
                if [ ! -x "$BIN_PATH" ]; then
                  FAILED_STAGE=download
                  post_status download starting "Downloading CodeTether runtime"
                  if [ -n "${CODETETHER_WORKER_AUTH_TOKEN:-}" ]; then
                    curl -fsSL -H "Authorization: Bearer $CODETETHER_WORKER_AUTH_TOKEN" -o "$DOWNLOAD_PATH" "$CODETETHER_DOWNLOAD_URL"
                  else
                    curl -fsSL -o "$DOWNLOAD_PATH" "$CODETETHER_DOWNLOAD_URL"
                  fi
                  MAGIC="$(od -An -t x1 -N 4 "$DOWNLOAD_PATH" | tr -d ' \\n')"
                  if [ "${MAGIC#1f8b08}" != "$MAGIC" ]; then
                    tar -xzf "$DOWNLOAD_PATH" -C "$TMP_DIR"
                    EXTRACTED_PATH="$(find "$TMP_DIR" -maxdepth 2 -type f -name 'codetether*' ! -name 'codetether-download' | head -n 1)"
                    test -n "$EXTRACTED_PATH"
                    install -m 0755 "$EXTRACTED_PATH" "$BIN_PATH"
                  elif [ "$MAGIC" = "7f454c46" ]; then
                    install -m 0755 "$DOWNLOAD_PATH" "$BIN_PATH"
                  else
                    echo "Unsupported CodeTether artifact format: $MAGIC" >&2
                    exit 1
                  fi
                  post_status download ready "CodeTether runtime ready"
                fi
                cat >"$ASKPASS_PATH" <<'EOF'
                #!/bin/sh
                case "$1" in
                  *Username*) printf '%s\\n' "$CODETETHER_BOOTSTRAP_GIT_USERNAME" ;;
                  *) printf '%s\\n' "$CODETETHER_BOOTSTRAP_GIT_PASSWORD" ;;
                esac
                EOF
                chmod 700 "$ASKPASS_PATH"
                if [ ! -d "$WORKDIR/.git" ] && [ -n "${CODETETHER_BOOTSTRAP_GIT_URL:-}" ]; then
                  FAILED_STAGE=clone
                  post_status clone starting "Cloning workspace repository"
                  mkdir -p "$(dirname "$WORKDIR")"
                  CLONE_TARGET="$WORKDIR"
                  if [ -d "$WORKDIR/lost+found" ] && ! find "$WORKDIR" -mindepth 1 -maxdepth 1 ! -name lost+found | grep -q .; then
                    CLONE_TARGET="$(mktemp -d "$(dirname "$WORKDIR")/.codetether-clone.XXXXXX")"
                  fi
                  GIT_ASKPASS="$ASKPASS_PATH" \\
                  GIT_TERMINAL_PROMPT=0 \\
                  git clone --branch "$CODETETHER_BOOTSTRAP_GIT_BRANCH" "$CODETETHER_BOOTSTRAP_GIT_URL" "$CLONE_TARGET"
                  if [ "$CLONE_TARGET" != "$WORKDIR" ]; then
                    shopt -s dotglob nullglob
                    mv "$CLONE_TARGET"/* "$WORKDIR"/
                    shopt -u dotglob nullglob
                    rmdir "$CLONE_TARGET"
                  fi
                fi
                if [ -d "$WORKDIR/.git" ]; then
                  FAILED_STAGE=configure
                  post_status configure starting "Configuring workspace repository"
                  git config --global --add safe.directory "$WORKDIR"
                  git -C "$WORKDIR" config user.name "$GIT_USER_NAME"
                  git -C "$WORKDIR" config user.email "$GIT_USER_EMAIL"
                  post_status configure ready "Workspace repository ready"
                fi
                FAILED_STAGE=service
                post_status service prepared "Bootstrap finished; worker service ready to start"
                systemctl daemon-reload
                systemctl enable codetether-worker.service
                """
            ).rstrip()
            service_unit = textwrap.dedent(
                """\
                [Unit]
                Description=CodeTether Harvester Worker
                After=network-online.target
                Wants=network-online.target

                [Service]
                Type=simple
                TimeoutStartSec=0
                EnvironmentFile=/etc/codetether-worker/env
                Environment=HOME=/root
                Environment=XDG_CONFIG_HOME=/root/.config
                WorkingDirectory=/
                ExecStartPre=/usr/local/bin/codetether-vm-bootstrap
                ExecStart=/bin/bash -lc 'cd "${A2A_CODEBASES:-/workspace}" && ARGS=(worker --server "$A2A_SERVER_URL" --name "$CODETETHER_WORKER_NAME" --codebases "$A2A_CODEBASES" --auto-approve all); if [ -n "${CODETETHER_WORKER_AUTH_TOKEN:-}" ]; then ARGS+=(--token "$CODETETHER_WORKER_AUTH_TOKEN"); fi; if [ -n "${CODETETHER_WORKER_PUBLIC_URL:-}" ]; then ARGS+=(--public-url "$CODETETHER_WORKER_PUBLIC_URL"); fi; if [ -n "${CODETETHER_WORKER_HOST:-}" ]; then ARGS+=(--hostname "$CODETETHER_WORKER_HOST"); fi; if [ -n "${CODETETHER_WORKER_PORT:-}" ]; then ARGS+=(--port "$CODETETHER_WORKER_PORT"); fi; exec "${A2A_CODEBASES:-/workspace}/.codetether/bin/codetether" "${ARGS[@]}"'
                Restart=always
                RestartSec=5

                [Install]
                WantedBy=multi-user.target
                """
            ).rstrip()
            write_files = f"""
write_files:
  - path: /etc/codetether-worker/env
    permissions: '0600'
    content: |
{textwrap.indent(env_body, '      ')}
  - path: /usr/local/bin/codetether-vm-bootstrap
    permissions: '0755'
    content: |
{textwrap.indent(bootstrap_script, '      ')}
  - path: /etc/systemd/system/codetether-worker.service
    permissions: '0644'
    content: |
{textwrap.indent(service_unit, '      ')}
"""
            bootstrap_runcmd = (
                "\n  - [bash, -lc, '/usr/local/bin/codetether-vm-bootstrap --start-service']"
            )

        package_lines = '\n'.join(f'  - {pkg}' for pkg in packages)
        packages_block = f"packages:\n{package_lines}\n" if package_lines else ''
        return f"""#cloud-config
package_update: false
package_upgrade: false
{packages_block}users:
  - default
  - name: {spec.ssh_user}
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: [sudo]
    shell: /bin/bash{ssh_section}{write_files}
runcmd:
  - [mkdir, -p, /var/run/sshd]
  - [bash, -c, 'systemctl enable --now ssh || systemctl enable --now sshd || true']
  - [mkdir, -p, /workspace]
  - [bash, -c, 'while [ ! -b /dev/vdb ]; do sleep 1; done']
  - [bash, -c, 'if ! blkid /dev/vdb; then mkfs.ext4 -F /dev/vdb; fi']
  - [bash, -c, 'mountpoint -q /workspace || mount /dev/vdb /workspace']
  - [bash, -c, 'grep -q \"^/dev/vdb /workspace\" /etc/fstab || echo \"/dev/vdb /workspace ext4 defaults,nofail 0 2\" >> /etc/fstab']
{bootstrap_runcmd}
"""

    def _build_vm_manifest(
        self,
        workspace_id: str,
        workspace_name: str,
        vm_name: str,
        pvc_name: str,
        cloud_init_secret_name: str,
        spec: VMWorkspaceSpec,
        tenant_id: str,
    ) -> Dict[str, Any]:
        template_spec: Dict[str, Any] = {
            'terminationGracePeriodSeconds': 0,
            'domain': {
                'cpu': {'cores': max(1, int(spec.cpu_cores))},
                'resources': {'requests': {'memory': spec.memory}},
                'devices': {
                    'disks': [
                        {'name': 'boot', 'disk': {'bus': 'virtio'}},
                        {'name': 'workspace', 'disk': {'bus': 'virtio'}},
                        {'name': 'cloudinit', 'disk': {'bus': 'virtio'}},
                    ],
                    'interfaces': [{'name': 'default', 'masquerade': {}}],
                },
            },
            'networks': [{'name': 'default', 'pod': {}}],
            'volumes': [
                {'name': 'boot', 'containerDisk': {'image': spec.image}},
                {
                    'name': 'workspace',
                    'persistentVolumeClaim': {'claimName': pvc_name},
                },
                {
                    'name': 'cloudinit',
                    'cloudInitNoCloud': {
                        'secretRef': {'name': cloud_init_secret_name}
                    },
                },
            ],
        }
        if VM_WORKSPACE_NODE_SELECTOR_HOSTNAME:
            template_spec['nodeSelector'] = {
                'kubernetes.io/hostname': VM_WORKSPACE_NODE_SELECTOR_HOSTNAME
            }
        return {
            'apiVersion': f'{VM_WORKSPACE_API_GROUP}/{VM_WORKSPACE_API_VERSION}',
            'kind': 'VirtualMachine',
            'metadata': {
                'name': vm_name,
                'namespace': self.namespace,
                'labels': {
                    'codetether.run/workspace': workspace_id,
                    'codetether.run/tenant': tenant_id,
                    'app.kubernetes.io/managed-by': 'codetether',
                },
                'annotations': {
                    'codetether.run/workspace-name': workspace_name,
                },
            },
            'spec': {
                'running': True,
                'template': {
                    'metadata': {
                        'labels': {
                            'vm.kubevirt.io/name': vm_name,
                            'kubevirt.io/domain': vm_name,
                            'codetether.run/workspace': workspace_id,
                            'codetether.run/tenant': tenant_id,
                        }
                    },
                    'spec': template_spec,
                },
            },
        }

    async def _ensure_workspace_pvc(
        self,
        workspace_id: str,
        tenant_id: str,
        spec: VMWorkspaceSpec,
    ) -> str:
        if not self._core_api:
            raise VMWorkspaceProvisionerError('Core API client not initialized')

        pvc_name = self._pvc_name(workspace_id)
        try:
            await self._core_api.read_namespaced_persistent_volume_claim(
                name=pvc_name,
                namespace=self.namespace,
            )
            return pvc_name
        except ApiException as e:
            if e.status != 404:
                raise VMWorkspaceProvisionerError(
                    f'Failed to read workspace PVC {pvc_name}: {e}'
                )

        pvc: Dict[str, Any] = {
            'apiVersion': 'v1',
            'kind': 'PersistentVolumeClaim',
            'metadata': {
                'name': pvc_name,
                'namespace': self.namespace,
                'labels': {
                    'codetether.run/workspace': workspace_id,
                    'codetether.run/tenant': tenant_id,
                },
            },
            'spec': {
                'accessModes': list(spec.access_modes),
                'resources': {'requests': {'storage': spec.disk_size}},
            },
        }
        if spec.storage_class:
            pvc['spec']['storageClassName'] = spec.storage_class

        try:
            await self._core_api.create_namespaced_persistent_volume_claim(
                namespace=self.namespace,
                body=pvc,
            )
            logger.info(
                'Created workspace PVC %s for workspace %s',
                pvc_name,
                workspace_id,
            )
            return pvc_name
        except ApiException as e:
            raise VMWorkspaceProvisionerError(
                f'Failed to create workspace PVC {pvc_name}: {e}'
            )

    async def _ensure_ssh_service(
        self,
        vm_name: str,
        workspace_id: str,
        tenant_id: str,
        service_type: str,
    ) -> str:
        if not self._core_api:
            raise VMWorkspaceProvisionerError('Core API client not initialized')

        service_name = self._ssh_service_name(vm_name)
        service_body = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': service_name,
                'namespace': self.namespace,
                'labels': {
                    'codetether.run/workspace': workspace_id,
                    'codetether.run/tenant': tenant_id,
                },
            },
            'spec': {
                'type': service_type,
                'selector': {'vm.kubevirt.io/name': vm_name},
                'ports': [
                    {
                        'name': 'ssh',
                        'port': 22,
                        'targetPort': 22,
                    }
                ],
            },
        }

        try:
            await self._core_api.read_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )
            return service_name
        except ApiException as e:
            if e.status != 404:
                raise VMWorkspaceProvisionerError(
                    f'Failed to read SSH service {service_name}: {e}'
                )

        try:
            await self._core_api.create_namespaced_service(
                namespace=self.namespace,
                body=service_body,
            )
            logger.info('Created VM SSH service %s for %s', service_name, vm_name)
            return service_name
        except ApiException as e:
            raise VMWorkspaceProvisionerError(
                f'Failed to create SSH service {service_name}: {e}'
            )

    async def _ensure_http_service(
        self,
        vm_name: str,
        workspace_id: str,
        tenant_id: str,
        service_type: str,
        port: int,
    ) -> str:
        if not self._core_api:
            raise VMWorkspaceProvisionerError('Core API client not initialized')

        service_name = self._http_service_name(vm_name)
        service_body = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': service_name,
                'namespace': self.namespace,
                'labels': {
                    'codetether.run/workspace': workspace_id,
                    'codetether.run/tenant': tenant_id,
                },
            },
            'spec': {
                'type': service_type,
                'selector': {'vm.kubevirt.io/name': vm_name},
                'ports': [
                    {
                        'name': 'http',
                        'port': port,
                        'targetPort': port,
                    }
                ],
            },
        }

        try:
            await self._core_api.read_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )
            return service_name
        except ApiException as e:
            if e.status != 404:
                raise VMWorkspaceProvisionerError(
                    f'Failed to read HTTP service {service_name}: {e}'
                )

        try:
            await self._core_api.create_namespaced_service(
                namespace=self.namespace,
                body=service_body,
            )
            logger.info('Created VM HTTP service %s for %s', service_name, vm_name)
            return service_name
        except ApiException as e:
            raise VMWorkspaceProvisionerError(
                f'Failed to create HTTP service {service_name}: {e}'
            )

    async def _ensure_cloud_init_secret(
        self,
        workspace_id: str,
        tenant_id: str,
        spec: VMWorkspaceSpec,
        bootstrap: Optional[Dict[str, str]] = None,
    ) -> str:
        if not self._core_api:
            raise VMWorkspaceProvisionerError('Core API client not initialized')

        secret_name = self._cloud_init_secret_name(workspace_id)
        secret_body = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': secret_name,
                'namespace': self.namespace,
                'labels': {
                    'codetether.run/workspace': workspace_id,
                    'codetether.run/tenant': tenant_id,
                },
            },
            'type': 'Opaque',
            'stringData': {
                'userdata': self._cloud_init_user_data(
                    spec,
                    bootstrap=bootstrap,
                )
            },
        }

        try:
            await self._core_api.read_namespaced_secret(
                name=secret_name,
                namespace=self.namespace,
            )
            await self._core_api.replace_namespaced_secret(
                name=secret_name,
                namespace=self.namespace,
                body=secret_body,
            )
            return secret_name
        except ApiException as e:
            if e.status != 404:
                raise VMWorkspaceProvisionerError(
                    f'Failed to read cloud-init secret {secret_name}: {e}'
                )

        try:
            await self._core_api.create_namespaced_secret(
                namespace=self.namespace,
                body=secret_body,
            )
            return secret_name
        except ApiException as e:
            raise VMWorkspaceProvisionerError(
                f'Failed to create cloud-init secret {secret_name}: {e}'
            )

    async def get_vm_status(self, vm_name: str) -> Optional[str]:
        if not await self._init_client():
            return None
        if not self._custom_api:
            return None

        try:
            vm = await self._custom_api.get_namespaced_custom_object(
                group=VM_WORKSPACE_API_GROUP,
                version=VM_WORKSPACE_API_VERSION,
                namespace=self.namespace,
                plural=VM_WORKSPACE_PLURAL,
                name=vm_name,
            )
            status = vm.get('status') or {}
            return status.get('printableStatus') or status.get('phase') or 'Unknown'
        except ApiException as e:
            if e.status == 404:
                return 'NotFound'
            logger.warning('Failed to get VM status for %s: %s', vm_name, e)
            return None

    async def provision_workspace_vm(
        self,
        workspace_id: str,
        workspace_name: str,
        tenant_id: str = 'default',
        spec: Optional[VMWorkspaceSpec] = None,
        bootstrap: Optional[Dict[str, str]] = None,
    ) -> VMWorkspaceResult:
        if not VM_WORKSPACES_ENABLED:
            return VMWorkspaceResult(
                success=False,
                error_message='VM workspace provisioning is disabled',
            )

        if not await self._init_client():
            return VMWorkspaceResult(
                success=False,
                error_message='Kubernetes VM client unavailable',
            )
        if not self._custom_api:
            return VMWorkspaceResult(
                success=False,
                error_message='Kubernetes custom API unavailable',
            )

        vm_spec = spec or VMWorkspaceSpec()
        vm_name = self._vm_name(workspace_id)
        pvc_name = self._pvc_name(workspace_id)
        cloud_init_secret_name = self._cloud_init_secret_name(workspace_id)
        ssh_service_name = self._ssh_service_name(vm_name) if vm_spec.create_ssh_service else None
        http_service_name = self._http_service_name(vm_name) if vm_spec.create_http_service else None

        try:
            bootstrap_env = dict(bootstrap or {})
            if bootstrap_env:
                bootstrap_env.setdefault(
                    'CODETETHER_WORKER_ID',
                    f'harvester-{workspace_id}',
                )
                bootstrap_env.setdefault('CODETETHER_WORKER_HOST', '0.0.0.0')
                bootstrap_env.setdefault(
                    'CODETETHER_WORKER_PORT',
                    str(vm_spec.http_port),
                )
                if http_service_name:
                    bootstrap_env.setdefault(
                        'CODETETHER_WORKER_PUBLIC_URL',
                        (
                            f'http://{http_service_name}.{self.namespace}.svc.cluster.local:'
                            f'{vm_spec.http_port}'
                        ),
                    )
            pvc_name = await self._ensure_workspace_pvc(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                spec=vm_spec,
            )
            cloud_init_secret_name = await self._ensure_cloud_init_secret(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                spec=vm_spec,
                bootstrap=bootstrap_env or None,
            )

            existing = None
            try:
                existing = await self._custom_api.get_namespaced_custom_object(
                    group=VM_WORKSPACE_API_GROUP,
                    version=VM_WORKSPACE_API_VERSION,
                    namespace=self.namespace,
                    plural=VM_WORKSPACE_PLURAL,
                    name=vm_name,
                )
            except ApiException as e:
                if e.status != 404:
                    raise VMWorkspaceProvisionerError(
                        f'Failed reading existing VM {vm_name}: {e}'
                    )

            if existing is None:
                vm_manifest = self._build_vm_manifest(
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    vm_name=vm_name,
                    pvc_name=pvc_name,
                    cloud_init_secret_name=cloud_init_secret_name,
                    spec=vm_spec,
                    tenant_id=tenant_id,
                )
                await self._custom_api.create_namespaced_custom_object(
                    group=VM_WORKSPACE_API_GROUP,
                    version=VM_WORKSPACE_API_VERSION,
                    namespace=self.namespace,
                    plural=VM_WORKSPACE_PLURAL,
                    body=vm_manifest,
                )
                already_exists = False
            else:
                already_exists = True

            if vm_spec.create_ssh_service:
                ssh_service_name = await self._ensure_ssh_service(
                    vm_name=vm_name,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    service_type=vm_spec.ssh_service_type,
                )

            if vm_spec.create_http_service:
                http_service_name = await self._ensure_http_service(
                    vm_name=vm_name,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    service_type=vm_spec.http_service_type,
                    port=vm_spec.http_port,
                )

            vm_status = await self.get_vm_status(vm_name)
            ssh_host = (
                f'{ssh_service_name}.{self.namespace}.svc.cluster.local'
                if ssh_service_name
                else None
            )
            public_url = (
                f'http://{http_service_name}.{self.namespace}.svc.cluster.local:{vm_spec.http_port}'
                if http_service_name
                else None
            )

            return VMWorkspaceResult(
                success=True,
                vm_name=vm_name,
                namespace=self.namespace,
                pvc_name=pvc_name,
                ssh_service_name=ssh_service_name,
                ssh_host=ssh_host,
                http_service_name=http_service_name,
                public_url=public_url,
                status=vm_status,
                already_exists=already_exists,
            )
        except VMWorkspaceProvisionerError as e:
            logger.error('VM workspace provisioning failed: %s', e)
            return VMWorkspaceResult(success=False, error_message=str(e))
        except ApiException as e:
            detail = (
                f'Kubernetes API error while provisioning VM workspace '
                f'(group={VM_WORKSPACE_API_GROUP}, version={VM_WORKSPACE_API_VERSION}, '
                f'plural={VM_WORKSPACE_PLURAL}): {e}'
            )
            logger.error(detail)
            return VMWorkspaceResult(success=False, error_message=detail)
        except Exception as e:
            logger.error('Unexpected VM provisioning error: %s', e)
            return VMWorkspaceResult(success=False, error_message=str(e))

    async def delete_workspace_vm(
        self,
        workspace_id: str,
        vm_name: Optional[str] = None,
        delete_pvc: bool = True,
    ) -> bool:
        if not await self._init_client():
            return False
        if not self._custom_api or not self._core_api:
            return False

        target_vm_name = vm_name or self._vm_name(workspace_id)
        pvc_name = self._pvc_name(workspace_id)
        cloud_init_secret_name = self._cloud_init_secret_name(workspace_id)
        ssh_service_name = self._ssh_service_name(target_vm_name)
        http_service_name = self._http_service_name(target_vm_name)
        ok = True

        try:
            await self._custom_api.delete_namespaced_custom_object(
                group=VM_WORKSPACE_API_GROUP,
                version=VM_WORKSPACE_API_VERSION,
                namespace=self.namespace,
                plural=VM_WORKSPACE_PLURAL,
                name=target_vm_name,
                body=client.V1DeleteOptions(),
            )
        except ApiException as e:
            if e.status != 404:
                logger.warning('Failed deleting VM %s: %s', target_vm_name, e)
                ok = False

        try:
            await self._core_api.delete_namespaced_service(
                name=ssh_service_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(),
            )
        except ApiException as e:
            if e.status != 404:
                logger.warning(
                    'Failed deleting SSH service %s: %s',
                    ssh_service_name,
                    e,
                )
                ok = False

        try:
            await self._core_api.delete_namespaced_service(
                name=http_service_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(),
            )
        except ApiException as e:
            if e.status != 404:
                logger.warning(
                    'Failed deleting HTTP service %s: %s',
                    http_service_name,
                    e,
                )
                ok = False

        if delete_pvc:
            try:
                await self._core_api.delete_namespaced_persistent_volume_claim(
                    name=pvc_name,
                    namespace=self.namespace,
                    body=client.V1DeleteOptions(),
                )
            except ApiException as e:
                if e.status != 404:
                    logger.warning('Failed deleting PVC %s: %s', pvc_name, e)
                    ok = False

        try:
            await self._core_api.delete_namespaced_secret(
                name=cloud_init_secret_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(),
            )
        except ApiException as e:
            if e.status != 404:
                logger.warning(
                    'Failed deleting cloud-init secret %s: %s',
                    cloud_init_secret_name,
                    e,
                )
                ok = False

        return ok


vm_workspace_provisioner = VMWorkspaceProvisioner()
