"""Deploy the tested recovery controller without weakening the merge gate."""
import json
import subprocess

revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
tag='review-recovery-'+revision[:12]
image=json.loads(subprocess.check_output(['docker','inspect','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag]))[0]
assert image.get('RepoDigests')
app=json.loads(subprocess.check_output(['kubectl','-n','argocd','get','application','codetether-a2a-server','-o','json']))
env=app['spec']['source']['helm']['valuesObject']['env']
assert env['FORGEJO_SINGLE_REVIEW_REPOS']=='riley/spotlessbinco'
assert 'CodeTether / Harvester Review' in env['FORGEJO_AUTO_MERGE_REQUIRED_CHECKS']
patch=[{'op':'test','path':'/metadata/resourceVersion','value':app['metadata']['resourceVersion']},
       {'op':'replace','path':'/spec/source/targetRevision','value':revision}]
for i,param in enumerate(app['spec']['source']['helm']['parameters']):
    if param['name'] in ('image.tag','blueGreen.rolloutId.green'):
        patch.append({'op':'replace','path':f'/spec/source/helm/parameters/{i}/value','value':tag})
for path,value in [('image/tag',tag),('blueGreen/rolloutId/green',tag),
                   ('blueGreen/images/green/image','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag)]:
    patch.append({'op':'replace','path':'/spec/source/helm/valuesObject/'+path,'value':value})
patch.append({'op':'add','path':'/spec/source/helm/valuesObject/env/FORGEJO_REVIEW_RECOVERY_REPOS','value':'riley/spotlessbinco'})
subprocess.run(['kubectl','-n','argocd','patch','application','codetether-a2a-server','--type=json','-p',json.dumps(patch)],check=True)
print(json.dumps({'revision':revision,'image':tag,'recovery_enabled':True}))