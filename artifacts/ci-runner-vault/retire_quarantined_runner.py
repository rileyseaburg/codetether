"""Disable only the idle legacy runner service; never stop/restart CT 300."""
import json
import shlex
import subprocess

HOST = 'root@192.168.50.134'
PROBE = r'''
import pathlib,subprocess,json
config=pathlib.Path('/etc/forgejo-runner/config.yml').read_text()
assert 'shutdown_timeout: 3h' in config, 'Graceful shutdown contract changed'
jobs=subprocess.check_output(['docker','-H','tcp://127.0.0.1:2375','ps','-q'],text=True)
assert not jobs.strip(), 'Runner still has active Docker jobs; do not interrupt'
active=subprocess.run(['lxc-ls','--active'],capture_output=True,text=True)
# The persistent CodeTether worker is separate from Forgejo and is left running.
assert active.returncode==0 and set(active.stdout.split()) <= {'codetether-worker-01'}, 'Unknown nested job containers are active'
subprocess.run(['systemctl','disable','--now','forgejo-runner.service'],check=True)
state=subprocess.run(['systemctl','is-active','forgejo-runner.service'],capture_output=True,text=True)
enabled=subprocess.run(['systemctl','is-enabled','forgejo-runner.service'],capture_output=True,text=True)
print(json.dumps({'service':'forgejo-runner.service','active':state.stdout.strip(),'enabled':enabled.stdout.strip()}))
assert state.stdout.strip()=='inactive'
assert enabled.stdout.strip()=='disabled'
'''

subprocess.run(
    ['ssh','-o','BatchMode=yes',HOST,
     shlex.join(['pct','exec','300','--','python3','-c',PROBE])],
    check=True,
)