"""Inspect the current PR's complete diff, preserving an immutable artifact."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

import httpx

record = json.loads(subprocess.run(
    ['vault','kv','get','-format=json','kv/codetether/harvester/forgejo-review'],
    capture_output=True,text=True,check=True,
).stdout)['data']['data']
root = record['api_base'] + '/repos/' + record['repo']
destination = Path(__file__).parent
with httpx.Client(timeout=60, headers={
    'Authorization':'token '+record['token'],
    'User-Agent':'CodeTether-Review-Capacity/1.0',
}) as client:
    response = client.get(root+'/pulls/5907');response.raise_for_status()
    pr = response.json();head = pr['head']['sha']
    response = client.get(root+'/pulls/5907.diff');response.raise_for_status()
    patch = response.content
    response = client.get(root+'/pulls/5907');response.raise_for_status()
    assert response.json()['head']['sha'] == head, 'Head moved during capture'
    entries=[]
    offsets=list(re.finditer(rb'^diff --git (.+)$',patch,re.M))
    for index,match in enumerate(offsets):
        end=offsets[index+1].start() if index+1<len(offsets) else len(patch)
        entries.append({'header':match.group(1).decode(errors='replace'),
                        'bytes':end-match.start()})
    path=destination/(head+'.patch')
    path.write_bytes(patch)
    summary={'head':head,'base':pr['base']['sha'],'bytes':len(patch),
             'sha256':hashlib.sha256(patch).hexdigest(),'file_count':len(entries),
             'largest':sorted(entries,key=lambda e:e['bytes'],reverse=True)[:20],
             'artifact':str(path)}
    (destination/'composition.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))