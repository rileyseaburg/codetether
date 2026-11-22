#!/usr/bin/env node
// Secrets arrive over SSH stdin, never in arguments/logs. No login keychain access.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const root = path.join(process.env.HOME, 'a2amonitor-login-20261005');
function run(program, args, input, env) {
  const result = spawnSync(program, args, { input, env, encoding: 'utf8', timeout: 120000 });
  if (program === '/bin/bash') {
    fs.writeFileSync(path.join(root, `evidence/vault-package-${Date.now()}.log`), (result.stdout || '') + (result.stderr || ''));
  }
  if (result.status !== 0) throw new Error(`${path.basename(program)} ${args[0]} failed (output suppressed)`);
  return result.stdout;
}
function security(command) {
  // Command input avoids putting passwords in process arguments.
  try {
    run('/usr/bin/security', ['-i'], command + '\n');
  } catch {
    throw new Error(`Isolated keychain ${command.split(' ')[0]} failed (output suppressed)`);
  }
}
function main() {
  function keychainList() {
    return run('/usr/bin/security', ['list-keychains', '-d', 'user']).trim().split('\n').map(s => s.trim().replace(/^"|"$/g, '')).filter(Boolean);
  }
  if (process.platform !== 'darwin') throw new Error('Signing requires macOS');
  const material = JSON.parse(fs.readFileSync(0, 'utf8'));
  const build = material.buildNumber || 4;
  if (!Number.isInteger(build) || build < 1 || build > 99999) throw new Error('Invalid build number');
  if (material.team_id !== 'J9YRM3U37D' || !material.private_key_pem || !material.certificate_base64) {
    throw new Error('Unexpected signing material');
  }
  const cert = new crypto.X509Certificate(Buffer.from(material.certificate_base64, 'base64'));
  const identity = cert.fingerprint.replaceAll(':', '');
  if (identity !== '9113C278A8C8873BEBDB3BBFE807011FF1734C75' || new Date(cert.validTo) <= new Date()) {
    throw new Error('Distribution certificate mismatch or expiry');
  }
  if (!cert.checkPrivateKey(crypto.createPrivateKey(material.private_key_pem))) throw new Error('Key mismatch');
  fs.mkdirSync(path.join(root, '.signing'), { recursive: true, mode: 0o700 });
  const temp = fs.mkdtempSync(path.join(root, '.signing/vault-'));
  const keychain = path.join(temp, 'build.keychain-db');
  const password = crypto.randomBytes(32).toString('hex');
  let imported = false;
  try {
    fs.writeFileSync(path.join(temp, 'key.pem'), material.private_key_pem, { mode: 0o600 });
    fs.writeFileSync(path.join(temp, 'cert.pem'), cert.toString(), { mode: 0o600 });
    run('/usr/bin/openssl', ['pkcs12', '-export', '-inkey', path.join(temp, 'key.pem'),
      '-in', path.join(temp, 'cert.pem'), '-out', path.join(temp, 'signing.p12'), '-passout', 'stdin'], password + '\n');
    fs.chmodSync(path.join(temp, 'signing.p12'), 0o600);
    security(`create-keychain -p ${password} "${keychain}"`);
    security(`unlock-keychain -p ${password} "${keychain}"`);
    run('/usr/bin/security', ['set-keychain-settings', '-lut', '3600', keychain]);
    const searchList = keychainList();
    if (!searchList.includes(keychain)) run('/usr/bin/security', ['list-keychains', '-d', 'user', '-s', keychain, ...searchList]);
    // --keychain restricts chain discovery too: include only the matching public intermediate.
    const parents = run('/usr/bin/security', ['find-certificate', '-a', '-p', '-c', 'Apple Worldwide Developer Relations Certification Authority']);
    const parent = (parents.match(/-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----/g) || [])
      .map(pem => new crypto.X509Certificate(pem)).find(candidate => cert.issuer === candidate.subject && cert.verify(candidate.publicKey));
    if (!parent) throw new Error('Matching Apple signing intermediate is unavailable');
    const parentPath = path.join(temp, 'intermediate.pem');
    fs.writeFileSync(parentPath, parent.toString(), { mode: 0o600 });
    run('/usr/bin/security', ['import', parentPath, '-k', keychain]);
    security(`import "${temp}/signing.p12" -k "${keychain}" -P ${password} -T /usr/bin/codesign -T /usr/bin/security`);
    security(`set-key-partition-list -S apple-tool:,apple:,codesign: -s -k ${password} "${keychain}"`);
    const identities = run('/usr/bin/security', ['find-identity', '-v', '-p', 'codesigning', keychain]);
    if (!identities.includes(identity)) throw new Error('Isolated signing identity unavailable');
    imported = true;
    const output = run('/bin/bash', [path.join(root, 'package_ios_tested_app.sh'), String(build)], undefined, {
      ...process.env, IOS_VAULT_SIGNING: '1', IOS_SIGNING_IDENTITY: identity, IOS_SIGNING_KEYCHAIN: keychain,
    });
    fs.writeFileSync(path.join(root, `evidence/vault-signing-build-${build}-package.log`), output);
  } finally {
    try {
      run('/usr/bin/security', ['list-keychains', '-d', 'user', '-s', ...keychainList().filter(item => item !== keychain)]);
      if (fs.existsSync(keychain)) run('/usr/bin/security', ['delete-keychain', keychain]);
    } finally {
      fs.rmSync(temp, { recursive: true }); // Only this invocation's ephemeral key material.
    }
  }
  const report = { build, certificateId: material.certificate_id, identity,
    signing: 'Ad Hoc', isolatedKeychain: true, loginKeychainUsed: false,
    temporaryKeysRemoved: !fs.existsSync(temp), imported, timestamp: new Date().toISOString() };
  fs.writeFileSync(path.join(root, `evidence/vault-signing-build-${build}.json`), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }