#!/usr/bin/env node
// Repeatable live UI run: resolve the actual booted simulator; fail closed on harness startup.
const { spawn, spawnSync } = require('node:child_process');
const runName = process.argv[2];
if (!/^workbench-ui-live-v\d+$/.test(runName || '')) throw new Error('Provide a unique result-bundle name');
const list = spawnSync('ssh', ['-o', 'BatchMode=yes', 'mac', 'xcrun simctl list devices booted --json'], { encoding: 'utf8', timeout: 30000 });
if (list.status !== 0) throw new Error('Simulator discovery failed');
const device = Object.values(JSON.parse(list.stdout).devices).flat().find(d => d.name === 'iPhone 16 Pro Max' && d.state === 'Booted');
if (!device || !/^[A-Fa-f0-9-]{36}$/.test(device.udid)) throw new Error('Expected simulator is not booted');
console.log(JSON.stringify({ device: device.name, udid: device.udid, result: `evidence/${runName}.xcresult` }));
const bridge = spawn(process.execPath, ['scripts/workbench_live_bridge.cjs'], { env: { ...process.env, WORKBENCH_UI_TEST: '1' }, stdio: 'inherit' });
const tunnel = spawn('ssh', ['-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes', '-N', '-R', '127.0.0.1:19872:127.0.0.1:19871', 'mac'], { stdio: 'inherit' });
const cleanup = () => { bridge.kill('SIGTERM'); tunnel.kill('SIGTERM'); };
process.on('exit', cleanup);
process.on('SIGTERM', () => process.exit(1));
setTimeout(() => {
  if (bridge.exitCode !== null || tunnel.exitCode !== null) { console.error('Harness startup failed'); process.exit(1); }
  const command = `cd ~/a2amonitor-login-20261005 && xcodebuild -project A2AMonitor.xcodeproj -scheme A2AMonitor -configuration Debug ` +
    `-destination "platform=iOS Simulator,id=${device.udid},arch=arm64" -derivedDataPath build ` +
    `-clonedSourcePackagesDirPath "$HOME/a2amonitor-login-20261005/SourcePackages" -disableAutomaticPackageResolution -skipPackageUpdates ` +
    `-parallel-testing-enabled NO -jobs 2 CODE_SIGNING_ALLOWED=NO PROVISIONING_PROFILE_SPECIFIER= COMPILER_INDEX_STORE_ENABLE=NO ` +
    `A2A_LIVE_SIMULATOR_TEST=1 -test-timeouts-enabled YES -maximum-test-execution-time-allowance 300 ` +
    `-only-testing:A2AMonitorUITests/WorkSessionUITests -resultBundlePath evidence/${runName}.xcresult test`;
  const test = spawn('ssh', ['-o', 'BatchMode=yes', 'mac', command]);
  let pending = '';
  function output(chunk) {
    pending += chunk.toString();
    const lines = pending.split('\n'); pending = lines.pop();
    for (const line of lines) if (/WORKFLOW_STAGE|Test Case|error:|\*\* TEST/.test(line)) console.log(line);
  }
  test.stdout.on('data', output); test.stderr.on('data', output);
  test.on('exit', code => { console.log(JSON.stringify({ xcodeExit: code, runName })); process.exit(code === 0 ? 0 : 1); });
}, 1500);


















