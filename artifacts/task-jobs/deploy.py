"""Enable finite task Jobs while legacy worker replicas drain without restarts."""
import json
import subprocess

rev=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
code=rev
tag='task-jobs-'+code[:12]
image=json.loads(subprocess.check_output(['docker','inspect','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag]))[0]
assert image.get('RepoDigests')
app=json.loads(subprocess.check_output(['kubectl','-n','argocd','get','application','codetether-a2a-server','-o','json']))
patch=[{'op':'test','path':'/metadata/resourceVersion','value':app['metadata']['resourceVersion']},
       {'op':'replace','path':'/spec/source/targetRevision','value':rev}]
for i,param in enumerate(app['spec']['source']['helm']['parameters']):
    if param['name'] in ('image.tag','blueGreen.rolloutId.green'):
        patch.append({'op':'replace','path':f'/spec/source/helm/parameters/{i}/value','value':tag})
for path,value in [('image/tag',tag),('blueGreen/rolloutId/green',tag),
                   ('blueGreen/images/green/image','registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:'+tag)]:
    patch.append({'op':'replace','path':'/spec/source/helm/valuesObject/'+path,'value':value})
patch.append({'op':'add','path':'/spec/source/helm/valuesObject/taskJobs','value':{'enabled':True}})
for key,value in {'HARVESTER_JOB_REPOS':'riley/spotlessbinco','HARVESTER_JOB_NAMESPACE':'a2a-system',
    'HARVESTER_JOB_TEMPLATE':'a2a-server-task-job-template','HARVESTER_JOB_MAX_ACTIVE':'8','HARVESTER_JOB_MAX_ACTIVE_READONLY':'4',
    'HARVESTER_JOB_MAX_RETAINED':'40','HARVESTER_JOB_TTL':'60',
    'HARVESTER_JOB_EXCLUDED_NODES':'kube-worker-08,node7,storage-node,spotless-tv-gpu',
    'HARVESTER_JOB_ALLOWED_NODES':'k8s-worker-1,k8s-worker-2,k8s-worker-3,k8s-worker-4',
    'CODETETHER_DASHBOARD_URL':'https://codetether.run'}.items():
    patch.append({'op':'add','path':'/spec/source/helm/valuesObject/env/'+key,'value':value})
subprocess.run(['kubectl','-n','argocd','patch','application','codetether-a2a-server','--type=json','-p',json.dumps(patch)],check=True)
print(json.dumps({'image':tag,'revision':rev,'legacy_replica_count_unchanged':True}))