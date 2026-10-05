// Recheck approved Vault usage and the installed device without logging secrets.
// Run with: node artifacts/a2amonitor-ios-install-20261005/capture-audit.cjs
const { spawnSync } = require('node:child_process');
const { writeFileSync } = require('node:fs');
const { join } = require('node:path');

const secretPath = 'secret/codetether/mac-mini';
const read = spawnSync('vault', ['kv', 'get', '-format=json', secretPath], {
  encoding: 'utf8', timeout: 30000, maxBuffer: 1024 * 1024,
});
if (read.status !== 0) throw new Error('Vault read failed; output suppressed');
const response = JSON.parse(read.stdout);
const password = response.data?.data?.password;
if (typeof password !== 'string' || !password || /[\r\n]/.test(password)) {
  throw new Error('Vault credential format is unsupported; value suppressed');
}
const device = '4745B27B-2B68-5164-A053-B869B07EE2CA';
const remote = [
  'IFS= read -r keychain_password',
  'security unlock-keychain -p "$keychain_password" "$HOME/Library/Keychains/login.keychain-db" || exit',
  'unset keychain_password',
  'hostname',
  'cd ~/a2amonitor-install-20261005-336f5fd || exit',
  `xcrun devicectl device info details --device ${device} --timeout 30 --json-output evidence/final-device.json || exit`,
  `xcrun devicectl device info apps --device ${device} --bundle-id com.a2a.monitor --timeout 30 --json-output evidence/final-app.json`,
].join('; ');
const ssh = spawnSync('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', 'mac', remote], {
  input: password + '\n', encoding: 'utf8', timeout: 90000, maxBuffer: 1024 * 1024,
});
const audit = {
  recordedAt: new Date().toISOString(),
  secretPath,
  vaultRequestId: response.request_id,
  vaultSecretVersion: response.data?.metadata?.version,
  secretDelivery: 'SSH stdin, shell read; not placed in SSH arguments or written to disk',
  operation: 'Unlock signing keychain, then query paired device and installed app in same SSH session',
  sshTarget: 'mac',
  sshExitCode: ssh.status,
  sshHost: ssh.status === 0 ? ssh.stdout.split('\n')[0].trim() : null,
  deviceIdentifier: device,
};
writeFileSync(join(__dirname, 'credential-use-audit.json'), JSON.stringify(audit, null, 2) + '\n', { mode: 0o600 });
// Do not forward unfiltered child output or the Vault response to logs.
console.log(JSON.stringify(audit, null, 2));
if (ssh.status !== 0) process.exitCode = 1;
