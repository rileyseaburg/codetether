import yaml

from a2a_server import vm_workspace_provisioner
from a2a_server.vm_workspace_provisioner import VMWorkspaceProvisioner, VMWorkspaceSpec


def test_vm_workspace_names_are_sanitized_and_bounded():
    provisioner = VMWorkspaceProvisioner(namespace='test')
    workspace_id = 'ABCDEF1234__workspace.with.invalid+++chars_and_a_very_long_tail'
    vm_name = provisioner._vm_name(workspace_id)
    pvc_name = provisioner._pvc_name(workspace_id)
    assert len(vm_name) <= 63 and len(pvc_name) <= 63
    assert vm_name == vm_name.lower() and pvc_name == pvc_name.lower()
    assert '_' not in vm_name and '_' not in pvc_name
    assert vm_name.startswith('codetether-vm-')


def test_vm_manifest_uses_cloudinit_secret_ref():
    provisioner = VMWorkspaceProvisioner(namespace='a2a-server')
    manifest = provisioner._build_vm_manifest(
        workspace_id='ec77c942',
        workspace_name='A2A-Server-MCP',
        vm_name='codetether-vm-ec77c942',
        pvc_name='codetether-vm-workspace-ec77c942',
        cloud_init_secret_name='codetether-vm-ec77c942-cloudinit',
        spec=VMWorkspaceSpec(),
        tenant_id='default',
    )
    cloudinit = next(v for v in manifest['spec']['template']['spec']['volumes'] if v['name'] == 'cloudinit')
    assert cloudinit['cloudInitNoCloud']['secretRef']['name'] == 'codetether-vm-ec77c942-cloudinit'


def test_vm_manifest_honors_hostname_node_selector():
    provisioner = VMWorkspaceProvisioner(namespace='a2a-server')
    original = vm_workspace_provisioner.VM_WORKSPACE_NODE_SELECTOR_HOSTNAME
    vm_workspace_provisioner.VM_WORKSPACE_NODE_SELECTOR_HOSTNAME = 'k8s-worker-2'
    try:
        manifest = provisioner._build_vm_manifest(
            workspace_id='ec77c942',
            workspace_name='A2A-Server-MCP',
            vm_name='codetether-vm-ec77c942',
            pvc_name='codetether-vm-workspace-ec77c942',
            cloud_init_secret_name='codetether-vm-ec77c942-cloudinit',
            spec=VMWorkspaceSpec(),
            tenant_id='default',
        )
    finally:
        vm_workspace_provisioner.VM_WORKSPACE_NODE_SELECTOR_HOSTNAME = original

    assert manifest['spec']['template']['spec']['nodeSelector'] == {
        'kubernetes.io/hostname': 'k8s-worker-2'
    }


def test_cloud_init_bootstrap_reports_status_to_control_plane():
    provisioner = VMWorkspaceProvisioner(namespace='a2a-server')
    user_data = provisioner._cloud_init_user_data(
        VMWorkspaceSpec(ssh_user='coder'),
        bootstrap={
            'CODETETHER_BOOTSTRAP_STATUS_URL': 'https://api.codetether.run/v1/agent/workspaces/ws-1/bootstrap/status',
            'CODETETHER_WORKSPACE_ID': 'ws-1',
            'CODETETHER_WORKER_AUTH_TOKEN': 'token',
            'CODETETHER_WORKER_PUBLIC_URL': 'http://codetether-vm-ws-1-http.a2a-server.svc.cluster.local:8080',
        },
    )
    assert 'post_status()' in user_data
    assert 'Bootstrap failed during $FAILED_STAGE' in user_data
    assert '/v1/agent/workspaces/ws-1/bootstrap/status' in user_data
    assert 'Authorization: Bearer $CODETETHER_WORKER_AUTH_TOKEN' in user_data
    assert 'curl -fsSL -H "Authorization: Bearer $CODETETHER_WORKER_AUTH_TOKEN" -o "$DOWNLOAD_PATH" "$CODETETHER_DOWNLOAD_URL"' in user_data
    assert '--token "$CODETETHER_WORKER_AUTH_TOKEN"' in user_data
    assert '--public-url "$CODETETHER_WORKER_PUBLIC_URL"' in user_data
    assert 'codetether-vm-bootstrap --start-service' in user_data
    assert 'systemctl daemon-reload' in user_data
    assert 'systemctl enable codetether-worker.service' in user_data
    assert 'systemctl start codetether-worker.service' in user_data


def test_cloud_init_bootstrap_embeds_valid_yaml_and_indented_heredoc():
    provisioner = VMWorkspaceProvisioner(namespace='a2a-server')
    user_data = provisioner._cloud_init_user_data(
        VMWorkspaceSpec(ssh_user='coder'),
        bootstrap={
            'CODETETHER_BOOTSTRAP_STATUS_URL': 'https://api.codetether.run/v1/agent/workspaces/ws-1/bootstrap/status',
            'CODETETHER_WORKSPACE_ID': 'ws-1',
            'CODETETHER_WORKER_AUTH_TOKEN': 'token',
            'CODETETHER_WORKER_PUBLIC_URL': 'http://codetether-vm-ws-1-http.a2a-server.svc.cluster.local:8080',
        },
    )

    assert '\n      import json\n' in user_data
    assert '\n      import sys\n' in user_data
    assert '\nimport json\n' not in user_data
    assert '\nimport sys\n' not in user_data

    parsed = yaml.safe_load(user_data)
    bootstrap_file = next(
        item
        for item in parsed['write_files']
        if item['path'] == '/usr/local/bin/codetether-vm-bootstrap'
    )
    assert "payload=\"$(python3 -" in bootstrap_file['content']
    assert 'import json' in bootstrap_file['content']
    assert 'import sys' in bootstrap_file['content']
    assert 'CLONE_TARGET="$WORKDIR"' in bootstrap_file['content']
    assert 'lost+found' in bootstrap_file['content']
    assert 'git clone --branch "$CODETETHER_BOOTSTRAP_GIT_BRANCH" "$CODETETHER_BOOTSTRAP_GIT_URL" "$CLONE_TARGET"' in bootstrap_file['content']
    assert 'mv "$CLONE_TARGET"/* "$WORKDIR"/' in bootstrap_file['content']


def test_vm_http_service_name_is_bounded():
    provisioner = VMWorkspaceProvisioner(namespace='test')
    service_name = provisioner._http_service_name('codetether-vm-ec77c942')
    assert service_name == 'codetether-vm-ec77c942-http'
    assert len(service_name) <= 63
