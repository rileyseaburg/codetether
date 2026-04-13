from pathlib import Path

import yaml


def _load_documents(relative_path: str):
    path = Path(__file__).resolve().parents[1] / relative_path
    with path.open(encoding='utf-8') as handle:
        return list(yaml.safe_load_all(handle))


def test_knative_worker_manifest_uses_persistent_workspace_claim():
    docs = _load_documents('knative-codetether-worker.yaml')

    pvc = next(doc for doc in docs if doc['kind'] == 'PersistentVolumeClaim')
    service = next(doc for doc in docs if doc['kind'] == 'Service')

    assert pvc['metadata']['name'] == 'codetether-worker-workspace'
    assert pvc['spec']['accessModes'] == ['ReadWriteMany']
    assert pvc['spec']['resources']['requests']['storage'] == '20Gi'

    workspace_volume = next(
        volume
        for volume in service['spec']['template']['spec']['volumes']
        if volume['name'] == 'workspace'
    )
    assert workspace_volume['persistentVolumeClaim']['claimName'] == (
        'codetether-worker-workspace'
    )
    assert 'emptyDir' not in workspace_volume


def test_polling_worker_manifest_uses_persistent_workspace_claim():
    docs = _load_documents('codetether-worker-deployment.yaml')

    pvc = next(doc for doc in docs if doc['kind'] == 'PersistentVolumeClaim')
    deployment = next(doc for doc in docs if doc['kind'] == 'Deployment')

    assert pvc['metadata']['name'] == 'codetether-worker-workspace'
    workspace_volume = next(
        volume
        for volume in deployment['spec']['template']['spec']['volumes']
        if volume['name'] == 'workspace'
    )
    assert workspace_volume['persistentVolumeClaim']['claimName'] == (
        'codetether-worker-workspace'
    )
    assert 'emptyDir' not in workspace_volume


def test_chart_worker_manifest_uses_persistent_workspace_claim():
    docs = _load_documents('chart/codetether-worker-deployment.yaml')

    pvc = next(doc for doc in docs if doc['kind'] == 'PersistentVolumeClaim')
    deployment = next(doc for doc in docs if doc['kind'] == 'Deployment')

    assert pvc['metadata']['name'] == 'codetether-worker-workspace'
    workspace_volume = next(
        volume
        for volume in deployment['spec']['template']['spec']['volumes']
        if volume['name'] == 'workspace'
    )
    assert workspace_volume['persistentVolumeClaim']['claimName'] == (
        'codetether-worker-workspace'
    )
    assert 'emptyDir' not in workspace_volume
