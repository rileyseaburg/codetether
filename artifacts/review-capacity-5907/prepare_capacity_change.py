"""Prepare an isolated, head-pinned CI configuration change from remote main."""
import base64
import json
import subprocess
from pathlib import Path

import httpx

out=Path(__file__).parent
record=json.loads(subprocess.run([
    'vault','kv','get','-format=json','kv/codetether/harvester/forgejo-review',
],capture_output=True,text=True,check=True).stdout)['data']['data']
root=record['api_base']+'/repos/'+record['repo']
path='.forgejo/workflows/codetether-pr-review.yml'
with httpx.Client(timeout=40,headers={
    'Authorization':'token '+record['token'],'User-Agent':'CodeTether-Review-Capacity/1.0',
}) as client:
    response=client.get(root+'/branches/main');response.raise_for_status()
    main=response.json()['commit']['id']
    response=client.get(root+'/contents/'+path,params={'ref':main})
    response.raise_for_status();file=response.json()
    text=base64.b64decode(file['content']).decode()
    assert text.count("CODETETHER_REVIEW_DIFF_MAX_BYTES: '10000000'")==1
    assert text.count('timeout-minutes: 60')==1
    text=text.replace("CODETETHER_REVIEW_DIFF_MAX_BYTES: '10000000'",
                      "CODETETHER_REVIEW_DIFF_MAX_BYTES: '20000000'")
    text=text.replace('timeout-minutes: 60','timeout-minutes: 180')
    anchor="      CODETETHER_REVIEW_CHUNK_MAX_BYTES: '200000'"
    assert text.count(anchor)==1
    text=text.replace(anchor,anchor+"\n      CODETETHER_REVIEW_CHUNK_CONCURRENCY: '2'\n      CODETETHER_REVIEW_CHUNK_MAX_COUNT: '128'")
    (out/'codetether-pr-review.yml').write_text(text)
    response=client.get(root+'/contents/scripts/codetether-review/chunk_pipeline.sh',params={'ref':main})
    response.raise_for_status();pipeline=response.json()
    assert base64.b64decode(pipeline['content']) == Path(
        '/home/riley/spotlessbinco/scripts/codetether-review/chunk_pipeline.sh'
    ).read_bytes(), 'Remote pipeline differs from the inspected implementation'
    (out/'original-chunk_pipeline.sh').write_bytes(base64.b64decode(pipeline['content']))
    metadata={'main':main,'files':{path:file['sha'],
               'scripts/codetether-review/chunk_pipeline.sh':pipeline['sha']}}
    (out/'source.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({'main':main,'config_prepared':str(out/'codetether-pr-review.yml'),
                      'total_bytes':20000000,'chunk_bytes':200000,'concurrency':2,
                      'max_chunks':128,'job_timeout_minutes':180}))