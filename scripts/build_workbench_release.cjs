#!/usr/bin/env node
// Use the same restored package artifacts as the successful live UI run.
const fs = require('node:fs');
const { spawn, spawnSync } = require('node:child_process');
const dir = 'artifacts/agent-workflow-validation';
const buildNumber = process.env.IOS_BUILD_NUMBER || '4';
if (!/^\d{1,5}$/.test(buildNumber)) throw new Error('Invalid build number');
const proofDirectory = process.env.WORKBENCH_PROOF_DIR || `${dir}/workbench-live-ui`;
if (!/^artifacts\/agent-workflow-validation\/[a-zA-Z0-9/_-]+$/.test(proofDirectory)) throw new Error('Invalid proof directory');
const proof = JSON.parse(fs.readFileSync(`${proofDirectory}/proof.json`));
const label = process.argv[2] || `workbench-release-v${buildNumber}-v1`;
const unsigned = process.env.IOS_BUILD_UNSIGNED === '1';
if (!new RegExp(`^workbench-release-v${buildNumber}-v\\d+$`).test(label)) throw new Error('Invalid release run label');
if (!proof.simulatorOrigin || !proof.targets?.every(t => t.remembered && t.bothTurnsCompleted && t.workspaceVerified)) {
  throw new Error('Strict live UI evidence is required before release');
}
const devices = JSON.parse(spawnSync('ssh', ['mac', 'xcrun simctl list devices booted -j'], { encoding: 'utf8' }).stdout);
const device = Object.values(devices.devices).flat().find(d => d.name === 'iPhone 16 Pro Max' && d.state === 'Booted');
if (!device) throw new Error('No booted test device');
const common = '-project A2AMonitor.xcodeproj -scheme A2AMonitor -configuration Debug -derivedDataPath build ' +
  '-clonedSourcePackagesDirPath "$HOME/a2amonitor-login-20261005/SourcePackages" -disableAutomaticPackageResolution -skipPackageUpdates -jobs 2 COMPILER_INDEX_STORE_ENABLE=NO';
const command = 'set -e; export PATH=/opt/homebrew/bin:$PATH; cd ~/a2amonitor-login-20261005; ' +
  `xcodebuild ${common} -destination "platform=iOS Simulator,id=${device.udid},arch=arm64" ` +
  '-parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO PROVISIONING_PROFILE_SPECIFIER= ' +
  '-only-testing:A2AMonitorTests/WorkSessionTests -only-testing:A2AMonitorTests/TaskHTTPContractTests ' +
  '-only-testing:A2AMonitorTests/WorkerModelOptionTests -only-testing:A2AMonitorTests/ProjectDiscoveryTests ' +
  '-only-testing:A2AMonitorUITests/LoginUITests/testLoginFailureMessages ' +
  `-resultBundlePath evidence/${label}-tests.xcresult test > evidence/${label}-tests.log 2>&1; ` +
  `xcodebuild ${common} -destination "generic/platform=iOS" ` +
  (unsigned ? 'CODE_SIGNING_ALLOWED=NO PROVISIONING_PROFILE_SPECIFIER= ' :
    'CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM=J9YRM3U37D PROVISIONING_PROFILE_SPECIFIER= CODE_SIGN_IDENTITY="Apple Development" ') +
  `-resultBundlePath evidence/${label}-device.xcresult build > evidence/${label}-device.log 2>&1; ` +
  (unsigned ? 'echo "Unsigned device build ready for isolated Vault signing"' : `bash package_ios_tested_app.sh ${buildNumber}`);
const child = spawn('ssh', ['mac', command], { stdio: 'inherit' });
child.on('exit', code => {
  console.log(JSON.stringify({ exitCode: code, build: Number(buildNumber) }));
  process.exitCode = code === 0 ? 0 : 1;
});