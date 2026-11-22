#!/usr/bin/env node
// Verify CoreDevice receipts for this specific device/app; no account data is read.
const fs = require('node:fs');
const path = require('node:path');
const directory = process.argv[2];
const build = process.argv[3] || '4';
if (!/^\d{1,5}$/.test(build)) throw new Error('Invalid build number');
if (!/^artifacts\/agent-workflow-validation\/physical-install-\d{8}T\d{6}Z$/.test(directory || '')) {
  throw new Error('Expected a scoped physical-install evidence directory');
}
const expectedDevice = '4745B27B-2B68-5164-A053-B869B07EE2CA';
const bundle = 'com.a2a.monitor';
function receipt(name) {
  const data = JSON.parse(fs.readFileSync(path.join(directory, name + '.json')));
  if (data.info?.outcome !== 'success' || data.result?.deviceIdentifier !== expectedDevice) {
    throw new Error(`${name}: unsuccessful result or wrong device`);
  }
  return data.result;
}
const before = receipt('before');
const install = receipt('install');
const after = receipt('after');
const launch = receipt('launch');
const running = receipt('running');
const installed = after.apps.find(app => app.bundleIdentifier === bundle);
if (!installed || installed.bundleVersion !== build) throw new Error(`Build ${build} is not installed`);
if (!install.installedApplications.some(app => app.bundleID === bundle)) throw new Error('Install result missing app');
const pid = launch.process?.processIdentifier;
if (!pid || !launch.process.executable?.endsWith('/A2AMonitor.app/A2AMonitor')) throw new Error('Wrong launched process');
if (!running.runningProcesses?.some(process => process.processIdentifier === pid)) throw new Error('Launched app is no longer running');
const sha256 = fs.readFileSync(path.join(directory, 'sha256.txt'), 'utf8').split(/\s/)[0];
const publication = JSON.parse(fs.readFileSync(`artifacts/agent-workflow-validation/delivery-v${build}/delivery-proof.json`));
if (sha256 !== publication.ipaSha256) throw new Error('Installed IPA does not match published artifact');
const proof = { verificationLevel: 'real platform upload', verifiedAt: new Date().toISOString(),
  deviceName: 'riley', deviceIdentifier: expectedDevice, platform: 'physical iPhone',
  bundleId: bundle, version: installed.version, build: installed.bundleVersion,
  previousBuild: before.apps.find(app => app.bundleIdentifier === bundle)?.bundleVersion ?? null,
  ipaUrl: publication.ipaUrl, ipaSha256: sha256, installed: true, launched: true,
  processIdentifier: pid, running: true, uninstallPerformed: false,
  credentialsEntered: false, endToEndPhoneTaskTested: false };
fs.writeFileSync(path.join(directory, 'proof.json'), JSON.stringify(proof, null, 2) + '\n');
console.log(JSON.stringify(proof, null, 2));