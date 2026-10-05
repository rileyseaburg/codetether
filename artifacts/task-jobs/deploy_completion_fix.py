"""Deploy the completion controller without changing admission settings."""

import json
import subprocess
import sys

from pathlib import Path


def main():
    """Pin commit/image together and retain the operator's other Argo values."""
    revision = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True
    ).strip()
    tag = sys.argv[1] if len(sys.argv) > 1 else 'completion-800d10d4'
    image = 'registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:' + tag
    info = json.loads(subprocess.check_output(['docker', 'inspect', image]))[0]
    assert info.get('RepoDigests'), 'Image must be pushed first'
    app = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'argocd',
                'get',
                'application',
                'codetether-a2a-server',
                '-o',
                'json',
            ]
        )
    )
    source = app['spec']['source']
    assert source['path'] == 'chart/a2a-server'
    prefix = '/spec/source/helm/valuesObject/'
    patches = [
        {
            'op': 'test',
            'path': '/metadata/resourceVersion',
            'value': app['metadata']['resourceVersion'],
        },
        {
            'op': 'replace',
            'path': '/spec/source/targetRevision',
            'value': revision,
        },
    ]
    for path, value in (
        ('image/tag', tag),
        ('blueGreen/rolloutId/green', tag),
        ('blueGreen/images/green/image', image),
    ):
        patches.append({'op': 'replace', 'path': prefix + path, 'value': value})
    for index, param in enumerate(source['helm'].get('parameters', [])):
        if param['name'] in {'image.tag', 'blueGreen.rolloutId.green'}:
            patches.append(
                {
                    'op': 'replace',
                    'path': f'/spec/source/helm/parameters/{index}/value',
                    'value': tag,
                }
            )
    subprocess.run(
        [
            'kubectl',
            '-n',
            'argocd',
            'patch',
            'application',
            'codetether-a2a-server',
            '--type=json',
            '-p',
            json.dumps(patches),
        ],
        check=True,
    )
    for deployment in (
        'a2a-server-deployment-green',
        'a2a-server-temporal-worker',
    ):
        subprocess.run(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'wait',
                f'deployment/{deployment}',
                '--for=jsonpath={.spec.template.spec.containers[0].image}='
                + image,
                '--timeout=240s',
            ],
            check=True,
        )
        subprocess.run(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'rollout',
                'status',
                f'deployment/{deployment}',
                '--timeout=240s',
            ],
            check=True,
        )
    result = {
        'namespace': 'a2a-system',
        'app': 'codetether-a2a-server',
        'revision': revision,
        'image': image,
        'digests': info['RepoDigests'],
        'admission_config_unchanged': True,
    }
    Path(f'artifacts/task-jobs/{tag}-deploy.json').write_text(
        json.dumps(result, indent=2) + '\n'
    )
    print(json.dumps(result))


if __name__ == '__main__':
    main()
