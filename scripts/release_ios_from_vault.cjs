#!/usr/bin/env node
// Test/build first, then pipe the documented Vault signing material over SSH.
const { spawnSync } = require('node:child_process');
function main() {
  const buildNumber = process.env.IOS_BUILD_NUMBER || '4';
  if (!/^\d{1,5}$/.test(buildNumber)) throw new Error('Invalid build number');
  const label = process.argv[2] || `workbench-release-v${buildNumber}-v1`;
  const build = spawnSync(process.execPath, ['scripts/build_workbench_release.cjs', label], {
    stdio: 'inherit', env: { ...process.env, IOS_BUILD_UNSIGNED: '1' },
  });
  if (build.status !== 0) throw new Error('Release build/tests failed; see retained Xcode evidence');
  const secret = spawnSync('vault', ['kv', 'get', '-format=json',
    'secret/codetether/ios-signing/distribution-6JF3S3B8MP'], { encoding: 'utf8', timeout: 30000 });
  if (secret.status !== 0) throw new Error('Vault signing read failed; output suppressed');
  const material = JSON.parse(secret.stdout).data.data;
  const sign = spawnSync('ssh', ['-o', 'BatchMode=yes', 'mac',
    '/opt/homebrew/bin/node ~/a2amonitor-login-20261005/sign_ios_vault_on_mac.cjs'], {
    input: JSON.stringify({ ...material, buildNumber: Number(buildNumber) }), encoding: 'utf8', timeout: 180000,
  });
  if (sign.status !== 0) throw new Error(`Isolated signing failed: ${sign.stderr.trim()}`);
  console.log(sign.stdout.trim());
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }