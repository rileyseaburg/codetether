#!/usr/bin/env node
// Publish an allowlisted NAS download path through the existing public tunnel.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const evidence = path.resolve(__dirname, '../artifacts/ios-simulator-delivery');
const download = '/mnt/nas/A2AMonitor/20261005/download';
function run(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: 30000 });
  if (result.status !== 0) throw new Error(`${command} failed; output suppressed`);
  return result.stdout;
}
async function main() {
  const live = JSON.parse(fs.readFileSync(path.join(evidence, 'live-proof.json')));
  if (!live.simulatorOrigin || live.httpStatus !== 200) throw new Error('Simulator proof gate not satisfied');
  const ipa = path.join(download, 'A2AMonitor-1.0.0-2.ipa');
  const hash = crypto.createHash('sha256').update(fs.readFileSync(ipa)).digest('hex');
  if (hash !== '4679f356dde97dbbfd82c5b64c68cd3911ad4431e497d7e2253767d449319109') throw new Error('IPA hash mismatch');
  fs.copyFileSync(path.join(evidence, 'index.html'), path.join(download, 'index.html'));
  fs.copyFileSync(path.join(evidence, 'manifest.plist'), path.join(download, 'manifest.plist'));
  const proof = { app: 'A2A Monitor', version: '1.0.0', build: '2', signing: 'Ad Hoc, registered iPhone only',
    ipaSha256: hash, simulatorTaskId: live.taskId, simulatorOrigin: true,
    simulatorTaskHttpStatus: live.httpStatus, simulatorHtmlSha256: live.sha256,
    userLoginTested: false, physicalPhoneTested: false };
  fs.writeFileSync(path.join(download, 'proof.json'), JSON.stringify(proof, null, 2) + '\n');
  const service = 'codetether-a2amonitor-download';
  const loaded = run('systemctl', ['--user', 'show', service, '-p', 'LoadState', '--value']).trim();
  if (loaded === 'not-found') {
    run('systemd-run', ['--user', `--unit=${service}`, '--collect', '--property=Restart=on-failure',
      process.execPath, path.resolve(__dirname, 'ios_download_server.cjs')]);
  } else {
    const exec = run('systemctl', ['--user', 'show', service, '-p', 'ExecStart', '--value']);
    if (!exec.includes(path.resolve(__dirname, 'ios_download_server.cjs'))) throw new Error('Download service name belongs to another process');
  }
  const cf = JSON.parse(run('vault', ['kv', 'get', '-format=json', 'kv/cloudflare/api-token'])).data.data;
  const unit = fs.readFileSync(path.join(process.env.HOME, '.config/systemd/user/codetether-public-tunnel.service'), 'utf8');
  const tokenPath = /--token-file\s+(\S+)/.exec(unit)?.[1]?.replace('%h', process.env.HOME);
  if (!tokenPath) throw new Error('Existing tunnel token-file path not found');
  const tunnel = JSON.parse(Buffer.from(fs.readFileSync(tokenPath, 'utf8').trim(), 'base64').toString());
  if (tunnel.a !== cf.account_id || !tunnel.t) throw new Error('Unexpected Cloudflare account');
  const api = `https://api.cloudflare.com/client/v4/accounts/${cf.account_id}/cfd_tunnel/${tunnel.t}/configurations`;
  const headers = { Authorization: `Bearer ${cf.token}`, 'Content-Type': 'application/json' };
  const response = await fetch(api, { headers, signal: AbortSignal.timeout(30000) });
  const body = await response.json();
  if (!response.ok || !body.success) throw new Error(`Cloudflare config read HTTP ${response.status}`);
  const config = body.result.config;
  const rule = { hostname: 'server.codetether.run', path: '^/downloads/a2amonitor/20261005(?:/.*)?$', service: 'http://127.0.0.1:18772' };
  const old = config.ingress.find(item => item.hostname === rule.hostname && item.path === rule.path);
  if (old && old.service !== rule.service) throw new Error('An unrelated download route already exists');
  if (!old) {
    const updated = { ...config, ingress: [rule, ...config.ingress] };
    const saved = await fetch(api, { method: 'PUT', headers, body: JSON.stringify({ config: updated }), signal: AbortSignal.timeout(30000) });
    const result = await saved.json();
    if (!saved.ok || !result.success) throw new Error(`Cloudflare config write HTTP ${saved.status}`);
  }
  const record = { tunnelId: tunnel.t, rule, nasDirectory: download, ipaSha256: hash,
    url: 'https://server.codetether.run/downloads/a2amonitor/20261005/',
    publishedAt: new Date().toISOString(), simulatorTaskId: live.taskId };
  fs.writeFileSync(path.join(evidence, 'publication.json'), JSON.stringify(record, null, 2) + '\n');
  console.log(JSON.stringify(record));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });



















