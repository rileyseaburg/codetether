"""Renew trusted runner tokens and retain only non-secret verification evidence."""
import datetime
import json
from pathlib import Path
import subprocess

NAMESPACE = "forgejo-actions"
SELECTOR = "app=forgejo-act-runner-dind"
OUT = Path(__file__).parent / "renewal-evidence.json"


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError(f"Command failed with exit {result.returncode}; output suppressed")
    return result.stdout


def vault(pod, args):
    script = ('export VAULT_ADDR=http://vault.vault.svc.cluster.local:8200; '
              'export VAULT_TOKEN="$(cat /vault/runtime/token)"; exec vault "$@"')
    return json.loads(command(["kubectl", "exec", "-n", NAMESPACE, pod,
                               "-c", "vault-agent", "--", "sh", "-c", script,
                               "vault", *args]))


def metadata(data):
    keys = ("display_name", "policies", "ttl", "period", "renewable",
            "path", "explicit_max_ttl")
    return {key: data.get(key) for key in keys}


pods = json.loads(command(["kubectl", "get", "pods", "-n", NAMESPACE,
                          "-l", SELECTOR, "--field-selector=status.phase=Running",
                          "-o", "json"]))["items"]
evidence = {"level": "live deployment/Argo", "namespace": NAMESPACE,
            "deployment": "forgejo-act-runner-dind",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "runners": []}
for item in pods:
    pod = item["metadata"]["name"]
    record = {"pod": pod, "before": metadata(vault(pod, ["token", "lookup", "-format=json"])["data"])}
    renewed = vault(pod, ["token", "renew", "-format=json"])["auth"]
    record["renewal"] = {key: renewed.get(key) for key in ("renewable", "lease_duration", "policies")}
    record["after"] = metadata(vault(pod, ["token", "lookup", "-format=json"])["data"])
    record["credential_reads"] = {}
    for identity in ("spotlessbinco-agent", "codetether-bot"):
        secret = vault(pod, ["kv", "get", "-format=json", "kv/forgejo/" + identity])
        record["credential_reads"][identity] = bool(secret["data"]["data"].get("token"))
    capabilities = vault(pod, ["token", "capabilities", "-format=json", "auth/token/create"])
    record["token_creation_capabilities"] = capabilities
    check = ('test -n "$(cat /vault/runtime/token)" && '
             'test "$(sed -n \'s/^VAULT_TOKEN=//p\' /data/job-env)" = "$(cat /vault/runtime/token)"')
    command(["kubectl", "exec", "-n", NAMESPACE, pod, "-c", "runner", "--", "sh", "-c", check])
    record["job_env_matches_token_sink"] = True
    evidence["runners"].append(record)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(record, indent=2))
if not evidence["runners"]:
    raise RuntimeError("No running trusted runner pods found")
