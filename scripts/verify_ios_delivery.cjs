#!/usr/bin/env node
const fs = require('node:fs');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const dir = 'artifacts/ios-simulator-delivery';
async function main() {
  const live = JSON.parse(fs.readFileSync(`${dir}/live-proof.json`));
  const publication = JSON.parse(fs.readFileSync(`${dir}/publication.json`));
  const summary = spawnSync('ssh', ['-o', 'BatchMode=yes', 'mac',
    'xcrun xcresulttool get test-results summary --path ~/a2amonitor-login-20261005/evidence/live-simulator-task-20261005.xcresult'],
    { encoding: 'utf8', timeout: 30000 });
  if (summary.status !== 0) throw new Error('Cannot read authoritative Xcode result');
  const xcode = JSON.parse(summary.stdout);
  if (xcode.result !== 'Passed' || xcode.passedTests !== 1 || xcode.failedTests || xcode.skippedTests) throw new Error('Live simulator test did not pass');
  fs.writeFileSync(`${dir}/xcode-summary.json`, JSON.stringify(xcode, null, 2) + '\n');
  const signature = spawnSync('ssh', ['-o', 'BatchMode=yes', 'mac',
    'codesign --verify --deep --strict ~/a2amonitor-login-20261005/adhoc-stage/Payload/A2AMonitor.app'],
    { encoding: 'utf8', timeout: 30000 });
  if (signature.status !== 0) throw new Error('Staged app signature validation failed');
  async function get(name) {
    const response = await fetch(publication.url + name, { signal: AbortSignal.timeout(60000) });
    if (response.status !== 200) throw new Error(`Public download ${name}: HTTP ${response.status}`);
    return Buffer.from(await response.arrayBuffer());
  }
  const index = (await get('')).toString();
  const manifest = (await get('manifest.plist')).toString();
  const publicProof = JSON.parse((await get('proof.json')).toString());
  const ipa = await get('A2AMonitor-1.0.0-2.ipa');
  const hash = crypto.createHash('sha256').update(ipa).digest('hex');
  if (hash !== publication.ipaSha256 || hash !== publicProof.ipaSha256) throw new Error('Downloaded IPA hash mismatch');
  if (!manifest.includes(publication.url + 'A2AMonitor-1.0.0-2.ipa') || !manifest.includes('com.a2a.monitor')) throw new Error('Install manifest mismatch');
  if (!index.includes('itms-services:') || publicProof.simulatorTaskId !== live.taskId) throw new Error('Landing page or proof mismatch');
  const range = await fetch(publication.url + 'A2AMonitor-1.0.0-2.ipa', { headers: { Range: 'bytes=0-3' }, signal: AbortSignal.timeout(10000) });
  if (range.status !== 206 || !(Buffer.from(await range.arrayBuffer())).equals(ipa.subarray(0, 4))) throw new Error('IPA range request failed');
  const forbidden = await fetch(publication.url + 'private-key.pem', { signal: AbortSignal.timeout(10000) });
  if (forbidden.status !== 404) throw new Error('Download route is not allowlisted');
  const proof = { url: publication.url, ipaUrl: publication.url + 'A2AMonitor-1.0.0-2.ipa',
    ipaSha256: hash, ipaBytes: ipa.length, publicStatus: 200, rangeStatus: range.status,
    blockedPathStatus: forbidden.status, signatureVerified: true, simulatorTaskId: live.taskId,
    liveSimulatorTestsPassed: xcode.passedTests, userLoginTested: false, physicalPhoneTested: false,
    verifiedAt: new Date().toISOString() };
  fs.writeFileSync(`${dir}/delivery-proof.json`, JSON.stringify(proof, null, 2) + '\n');
  console.log(JSON.stringify(proof, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });





