"""Create a frontend-only release commit without touching the user's index/branch."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
def git(*args, env=None, input=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env, input=input, text=True).strip()

base = git('rev-parse', 'origin/main')
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
branch = 'release/ui-usability-' + stamp
with tempfile.TemporaryDirectory(prefix='ui-release-index-') as temporary:
    env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
    git('read-tree', base, env=env)
    git('add', '-A', '--', 'marketing-site', env=env)
    paths = git('diff', '--cached', '--name-only', base, env=env).splitlines()
    if not paths or any(not name.startswith('marketing-site/') for name in paths):
        raise RuntimeError('Release scope is not frontend-only')
    if any('/node_modules/' in name or '/.env' in name or name.endswith(('.pem', '.key')) for name in paths):
        raise RuntimeError('Unexpected sensitive/generated content in release')
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, '-p', base, input='fix(ui): simplify dashboard workflows and harden production authentication\n')
git('update-ref', 'refs/heads/' + branch, commit, '0' * 40)
record = {'branch': branch, 'commit': commit, 'base': base, 'paths': paths,
          'image': 'registry.quantum-forge.net/cluster-ci-cache/codetether-marketing:ui-' + commit[:12]}
(OUT / 'release.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({key: record[key] for key in ('branch', 'commit', 'image')}, indent=2))