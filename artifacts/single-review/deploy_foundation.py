"""Promote tested code and a safe-only reviewer without enabling review cutover."""
import json
import subprocess

app=json.loads(subprocess.check_output([
    'kubectl','-n','argocd','get','application','codetether-a2a-server','-o','json']))
helm=app['spec']['source']['helm'];values=helm['valuesObject']
assert values['image']['tag']=='automerge-580ff64bd07d'
assert not values['env'].get('FORGEJO_SINGLE_REVIEW_REPOS')
tag='single-review-5c689568e086'
patch=[{'op':'test','path':'/metadata/resourceVersion','value':app['metadata']['resourceVersion']},
       {'op':'replace','path':'/spec/source/targetRevision','value':'5c689568e086fe424b0da398f7c74fb570c2e6db'}]
for i,p in enumerate(helm['parameters']):
    if p['name'] in ('image.tag','blueGreen.rolloutId.green'):
        patch.append({'op':'replace','path':f'/spec/source/helm/parameters/{i}/value','value':tag})
for path,value in (
    ('image/tag',tag),
    ('blueGreen/images/green/image','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag),
    ('blueGreen/rolloutId/green',tag),
):
    patch.append({'op':'replace','path':'/spec/source/helm/valuesObject/'+path,'value':value})
patch.append({'op':'add','path':'/spec/source/helm/valuesObject/reviewHarvester','value':{'enabled':True}})
patch.append({'op':'add','path':'/spec/source/helm/valuesObject/env/FORGEJO_REVIEW_SAFE_WORKER','value':'harvester-pr-review'})
subprocess.run(['kubectl','-n','argocd','patch','application','codetether-a2a-server','--type=json','-p',json.dumps(patch)],check=True)