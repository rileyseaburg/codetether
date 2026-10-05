"""Activate the tested sole owner while keeping merge execution held."""
import json
import subprocess

revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
tag='single-review-'+revision[:12]
image=json.loads(subprocess.check_output(['docker','inspect','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag]))[0]
assert image.get('RepoDigests'),'The exact source image has not been published'
app=json.loads(subprocess.check_output(['kubectl','-n','argocd','get','application','codetether-a2a-server','-o','json']))
values=app['spec']['source']['helm']['valuesObject']
assert values['env']['FORGEJO_AUTO_MERGE_REQUIRED_CHECKS']=='{}'
assert values['reviewHarvester']['allowChatGPTBackend'] is True
patch=[{'op':'test','path':'/metadata/resourceVersion','value':app['metadata']['resourceVersion']},
       {'op':'replace','path':'/spec/source/targetRevision','value':revision}]
for index,param in enumerate(app['spec']['source']['helm']['parameters']):
    if param['name'] in ('image.tag','blueGreen.rolloutId.green'):
        patch.append({'op':'replace','path':f'/spec/source/helm/parameters/{index}/value','value':tag})
for path,value in [('image/tag',tag),('blueGreen/rolloutId/green',tag),
                   ('blueGreen/images/green/image','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag)]:
    patch.append({'op':'replace','path':'/spec/source/helm/valuesObject/'+path,'value':value})
patch.append({'op':'add','path':'/spec/source/helm/valuesObject/env/FORGEJO_SINGLE_REVIEW_REPOS','value':'riley/spotlessbinco'})
subprocess.run(['kubectl','-n','argocd','patch','application','codetether-a2a-server','--type=json','-p',json.dumps(patch)],check=True)
print(json.dumps({'revision':revision,'image':tag,'merge_execution':'held'}))