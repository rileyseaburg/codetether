from a2a_server.knative_spawner import KnativeSpawner, WorkspacePersistenceConfig


def test_workspace_pvc_name_is_sanitized_and_bounded():
    spawner = KnativeSpawner(namespace='test', configmap_name='test-cm')
    spawner.workspace_persistence = WorkspacePersistenceConfig(
        enabled=True,
        pvc_prefix='CodeTether_WORKSPACE',
    )

    pvc_name = spawner._workspace_pvc_name(
        'ABCDEF1234__workspace.with.invalid+++chars_and_a_very_long_tail'
    )

    assert len(pvc_name) <= 63
    assert pvc_name.startswith('codetether-workspace-')
    assert pvc_name == pvc_name.lower()
    assert '_' not in pvc_name


def test_render_template_replaces_workspace_placeholders():
    spawner = KnativeSpawner(namespace='test', configmap_name='test-cm')
    spawner.workspace_persistence = WorkspacePersistenceConfig(
        enabled=True,
        mount_path='/workspace',
        base_path='/workspace/repos',
    )
    spawner._templates = {
        'service-template.yaml': """
apiVersion: v1
kind: Pod
metadata:
  name: test-SESSION_ID
spec:
  containers:
    - name: c
      env:
        - name: BASE
          value: "WORKSPACE_BASE_PATH"
      volumeMounts:
        - name: ws
          mountPath: "WORKSPACE_MOUNT_PATH"
  volumes:
    - name: ws
      persistentVolumeClaim:
        claimName: "WORKSPACE_PVC_NAME"
"""
    }

    rendered = spawner._render_template(
        template_key='service-template.yaml',
        session_id='session-1',
        tenant_id='tenant-1',
        codebase_id='workspace-1',
        workspace_pvc_name='codetether-workspace-workspace-1',
    )

    assert rendered['metadata']['name'] == 'test-session-1'
    assert rendered['spec']['containers'][0]['env'][0]['value'] == '/workspace/repos'
    assert (
        rendered['spec']['containers'][0]['volumeMounts'][0]['mountPath']
        == '/workspace'
    )
    assert (
        rendered['spec']['volumes'][0]['persistentVolumeClaim']['claimName']
        == 'codetether-workspace-workspace-1'
    )
