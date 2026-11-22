#!/usr/bin/env node
// Publish build 4 only after Xcode, isolated signing, and live UI evidence gates.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const root = 'artifacts/agent-workflow-validation';
const download = '/mnt/nas/A2AMonitor/20261005/download';
const base = 'https://server.codetether.run/downloads/a2amonitor/20261005/';
const build = Number(process.env.IOS_BUILD_NUMBER || '4');
if (!Number.isInteger(build) || build < 1 || build > 99999) throw new Error('Invalid build number');
const proofDirectory = process.env.WORKBENCH_PROOF_DIR || `${root}/workbench-live-ui`;
if (!/^artifacts\/agent-workflow-validation\/[a-zA-Z0-9/_-]+$/.test(proofDirectory)) throw new Error('Invalid proof directory');
const name = `A2AMonitor-1.0.0-${build}.ipa`;
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
function run(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: 60000 });
  if (result.status !== 0) throw new Error(`${command} failed; output suppressed`);
  return result.stdout;
  }
const remote = command => run('ssh', ['-o', 'BatchMode=yes', 'mac', command]);
async function main() {
  if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0') throw new Error('TLS validation must be enabled');
  const label = process.argv[2];
  if (!new RegExp(`^workbench-release-v${build}-v\\d+$`).test(label || '')) throw new Error('Release test label required');
  const evidence = `${root}/delivery-v${build}`;
  fs.mkdirSync(evidence, { recursive: true });
  if (fs.existsSync(`${evidence}/delivery-proof.json`)) throw new Error('Existing delivery proof will not be overwritten');
  const live = JSON.parse(fs.readFileSync(`${proofDirectory}/proof.json`));
  if (!live.simulatorOrigin || !live.targets?.length || !live.targets.every(t => t.remembered && t.bothTurnsCompleted && t.workspaceVerified
    && Array.isArray(t.taskIds) && t.taskIds.length === 2 && t.taskIds.every(id => typeof id === 'string'))) {
    throw new Error('Strict live simulator gate failed');
  }
  if (build >= 5 && !live.targets.every(t => t.modelVerified)) throw new Error('Exact worker model identity was not verified');
  const summary = JSON.parse(remote(`xcrun xcresulttool get test-results summary --path ~/a2amonitor-login-20261005/evidence/${label}-tests.xcresult`));
  if (summary.result !== 'Passed' || summary.failedTests !== 0 || summary.skippedTests !== 0 || summary.passedTests < (build >= 5 ? 20 : 10)) {
    throw new Error('Release regression tests did not pass');
  }
  fs.writeFileSync(`${evidence}/test-summary.json`, JSON.stringify(summary, null, 2));
  const signingFile = build === 4 ? 'vault-signing.json' : `vault-signing-build-${build}.json`;
  const signing = JSON.parse(remote(`cat ~/a2amonitor-login-20261005/evidence/${signingFile}`));
  if (signing.build !== build || !signing.isolatedKeychain || !signing.temporaryKeysRemoved || signing.loginKeychainUsed) throw new Error('Signing gate failed');
  const app = `~/a2amonitor-login-20261005/adhoc-stage-${build}/Payload/A2AMonitor.app`;
  const version = remote(`set -e; codesign --verify --deep --strict ${app}; plutil -extract CFBundleVersion raw ${app}/Info.plist`).trim();
  if (version !== String(build)) throw new Error('Wrong signed build');
  const ipa = fs.readFileSync(path.join(download, name));
  const hash = digest(ipa);
  const remoteHash = remote(`shasum -a 256 ~/NAS/A2AMonitor/20261005/download/${name}`).split(/\s/)[0];
  if (hash !== remoteHash) throw new Error('NAS package differs from signing Mac');
  fs.writeFileSync(`${evidence}/signing.json`, JSON.stringify(signing, null, 2));
  const proof = { build, version: '1.0.0', bundleId: 'com.a2a.monitor', signing: 'Ad Hoc',
    ipaUrl: base + name, ipaSha256: hash, ipaBytes: ipa.length, signatureVerified: true,
    simulatorOrigin: true, testedTaskIds: live.targets.flatMap(t => t.taskIds),
    userLoginTested: false, physicalPhoneTested: false, testLabel: label, timestamp: new Date().toISOString() };
  const manifest = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>items</key><array><dict>
<key>assets</key><array><dict><key>kind</key><string>software-package</string><key>url</key><string>${base + name}</string></dict></array>
<key>metadata</key><dict><key>bundle-identifier</key><string>com.a2a.monitor</string><key>bundle-version</key><string>${build}</string>
<key>kind</key><string>software</string><key>title</key><string>A2A Monitor</string></dict>
</dict></array></dict></plist>\n`;
  const install = `itms-services://?action=download-manifest&url=${encodeURIComponent(base + 'manifest.plist')}`;
  const index = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A2A Monitor — Agents</title><style>body{max-width:44rem;margin:3rem auto;padding:0 1.3rem;font:18px/1.6 system-ui;background:#101826;color:#e7edf5}a{color:#92c8ff}.install{display:inline-block;padding:.7rem 1.3rem;border-radius:12px;background:#2470d7;color:white;text-decoration:none}code{overflow-wrap:anywhere;font-size:.75rem}</style>
<h1>A2A Monitor</h1><p>Version 1.0.0 · Build ${build} · Ad Hoc test build</p>
<p>Open this page in Safari on your registered iPhone. Tap Install to update the existing app.</p>
<p><a class="install" href="${install}">Install A2A Monitor</a></p>
<h2>Agents and conversations</h2><ol><li>Sign in with your own account.</li><li>Open Agents and choose an online session-capable agent.</li><li>Tap New Session, check the project folder, and enter your task.</li><li>Continue the same conversation from its chat screen.</li></ol>
<p>Build 5 adds a searchable provider/model picker, an explicit recommended model, corrected project discovery, and Change Model / Retry controls for failed turns. No provider/model ID needs to be typed.</p>
<p>Build mode can edit files and automatically commit or push changes. Check the selected folder before starting.</p>
<h2>Verification</h2><p>Live deployment/simulator: two real agent turns retained the same session ID and selected workspace. Mocked local: ${summary.passedTests} regression tests passed. Physical-iPhone installation and password entry were not automated.</p>
<p><a href="${name}">Download signed IPA</a> · <a href="proof.json">Build evidence</a></p><p>SHA-256: <code>${hash}</code></p></html>\n`;
  const files = { 'manifest.plist': manifest, 'index.html': index, 'proof.json': JSON.stringify(proof, null, 2) + '\n' };
  for (const [file, contents] of Object.entries(files)) {
    const old = path.join(download, file);
    const backup = `${evidence}/previous-${file}`;
    if (fs.existsSync(old) && !fs.existsSync(backup)) fs.copyFileSync(old, backup);
    fs.writeFileSync(`${evidence}/${file}`, contents);
  }
  const exec = run('systemctl', ['--user', 'show', 'codetether-a2amonitor-download', '-p', 'ExecStart', '--value']);
  if (!exec.includes(path.resolve('scripts/ios_download_server.cjs'))) throw new Error('Download service belongs to another process');
  for (const [file, contents] of Object.entries(files)) {
    const staged = path.join(download, `.build${build}-${file}`);
    fs.writeFileSync(staged, contents);
    fs.renameSync(staged, path.join(download, file));
  }
  // Reload only this dedicated allowlisted download server, not the shared tunnel.
  run('systemctl', ['--user', 'restart', 'codetether-a2amonitor-download']);
  async function get(file) {
    const response = await fetch(base + file, { signal: AbortSignal.timeout(90000), cache: 'no-store' });
    if (response.status !== 200) throw new Error(`${file} returned HTTP ${response.status}`);
    return Buffer.from(await response.arrayBuffer());
  }
  for (const [file, contents] of Object.entries(files)) {
    if (!(await get(file)).equals(Buffer.from(contents))) throw new Error(`Public ${file} mismatch`);
  }
  if (digest(await get(name)) !== hash) throw new Error('Public IPA digest mismatch');
  const range = await fetch(base + name, { headers: { Range: 'bytes=0-3' }, signal: AbortSignal.timeout(15000) });
  if (range.status !== 206 || !Buffer.from(await range.arrayBuffer()).equals(ipa.subarray(0, 4))) throw new Error('Range support failed');
  const blocked = await fetch(base + 'private-key.pem', { signal: AbortSignal.timeout(15000) });
  if (blocked.status !== 404) throw new Error('Download allowlist failed');
  const delivery = { ...proof, url: base, publicStatus: 200, rangeStatus: 206, blockedPathStatus: 404,
    tlsVerificationEnabled: true, verificationLevel: 'live deployment/Argo', installedOnPhone: false };
  fs.writeFileSync(`${evidence}/delivery-proof.json`, JSON.stringify(delivery, null, 2) + '\n');
  console.log(JSON.stringify(delivery, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });