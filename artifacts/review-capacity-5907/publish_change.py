"""Publish only the reviewed CI changes on a new branch; preserve PR 5907."""
import base64
import json
import subprocess
from pathlib import Path

import httpx

directory=Path(__file__).parent
source=json.loads((directory/'source.json').read_text())
credential=json.loads(subprocess.run([
    'vault','kv','get','-format=json','kv/forgejo/codetether-bot',
],capture_output=True,text=True,check=True).stdout)['data']['data']
root='https://forgejo.quantum-forge.io/api/v1/repos/riley/spotlessbinco'
branch='fix/codetether-review-capacity-5907'
mapping={'.forgejo/workflows/codetether-pr-review.yml':'codetether-pr-review.yml',
         'scripts/codetether-review/chunk_pipeline.sh':'chunk_pipeline.sh',
         'scripts/codetether-review/chunk_worker.sh':'chunk_worker.sh'}
with httpx.Client(timeout=60,headers={
    'Authorization':'token '+credential['token'],'User-Agent':'CodeTether-Review-Capacity/1.0',
}) as client:
    r=client.get(root+'/branches/main');r.raise_for_status()
    assert r.json()['commit']['id']==source['main'], 'Main advanced; refresh the proposed patch'
    files=[]
    for path,local in mapping.items():
        text=(directory/local).read_bytes()
        if path.endswith('.sh'):assert len(text.splitlines())<=80
        item={'operation':'update' if path in source['files'] else 'create',
              'path':path,'content':base64.b64encode(text).decode()}
        if path in source['files']:item['sha']=source['files'][path]
        files.append(item)
    r=client.post(root+'/contents',json={'branch':'main','new_branch':branch,
        'message':'ci: bound full-diff review capacity and parallelize exact chunks',
        'files':files})
    r.raise_for_status();change=r.json()
    print('COMMIT',json.dumps({'sha':change.get('commit',{}).get('sha')}),flush=True)
    r=client.post(root+'/pulls',json={'base':'main','head':branch,
        'title':'Bound complete review capacity and process exact chunks concurrently',
        'body':'## Changes\n- Raise total complete-diff ceiling from 10 MB to 20 MB.\n- Retain 200 KB chunk, 240 KB prompt and 900 KB task bounds.\n- Run two chunks at a time, with a 128-chunk hard cap and 180-minute job timeout.\n- Keep per-chunk artifacts isolated and aggregate in manifest order only after every exact-hash acknowledgement succeeds.\n- Preserve verified-author routing, trusted-base execution, credentials, and approval gates.\n\n## Evidence\nStatic/local: current PR #5907 diff is 2,920,978 bytes across 84 files, dominated by generated RustyRoad code. Canonical chunk generation reconstructed that exact real diff (SHA-256 d85c6791c87f648f1c6959ed2f79ae81e36a46425afc26fcd3550d128af9269a); 16 chunks at a 190 KB preflight bound. New handwritten shell files remain below 80 lines.\n\nNot-run locally: tests, compilers, and live model review. Existing CI validation is retained. No generated files or PR #5907 branch contents were changed.\n\nThis changes the trusted review workflow and must land on main before it governs later PR review runs. No truncation or partial approval is allowed.'})
    r.raise_for_status();pr=r.json()
    result={'number':pr['number'],'url':pr['html_url'],'head':pr['head']['sha'],'branch':branch}
    (directory/'publication.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PR',json.dumps(result))