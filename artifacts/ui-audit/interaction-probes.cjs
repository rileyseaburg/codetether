const fs = require('node:fs');
const assert = require('node:assert/strict');
const ts = require('../../marketing-site/node_modules/typescript');
const root = 'marketing-site/src/app/(dashboard)/dashboard/';
const js = text => ts.transpile(text, {target:ts.ScriptTarget.ES2020});
(async () => {
 const settings = fs.readFileSync(root+'settings/page.tsx','utf8');
 const handler = settings.slice(settings.indexOf('const handleTestKey ='),settings.indexOf('const handleDeleteKey ='));
 const calls = [];
 const testKey = new Function('apiKeys','setTesting','setError','setSuccess','getAuthToken','testApiKeyEndpointV1AgentApiKeysTestPost','apiKey',
  js(handler)+'; return handleTestKey;')([],x=>calls.push(x),x=>calls.push(x),x=>calls.push(x),()=> 'fixture',x=>calls.push(x),'fixture-key');
 await testKey('new-provider');
 assert.equal(calls.length,0);
 const chat = fs.readFileSync(root+'sessions/components/ChatInput.tsx','utf8');
 const keyHandler = chat.slice(chat.indexOf('const handleKeyDown ='),chat.indexOf('const canSend ='));
 let sends=0, prevents=0;
 const onKeyDown = new Function('onSend',js(keyHandler)+'; return handleKeyDown;')(()=>sends++);
 onKeyDown({key:'Enter',shiftKey:false,nativeEvent:{isComposing:true},preventDefault:()=>prevents++});
 assert.equal(sends,1);
 assert.equal(prevents,1);
 const results = {level:'mocked local',checks:[
  {name:'testing unsaved provider produces no API request or feedback',observedCalls:calls.length},
  {name:'IME composition Enter submits message',sends,prevents}
 ]};
 fs.writeFileSync('artifacts/ui-audit/interaction-results.json',JSON.stringify(results,null,2));
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exit(1)});