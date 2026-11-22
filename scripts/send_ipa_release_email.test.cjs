const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { parse, secureURL } = require('./send_ipa_release_email.cjs');
const source = fs.readFileSync(require.resolve('./send_ipa_release_email.cjs'), 'utf8');

function fixture({ send = false, status = 202, ambiguous = false, badHash = false, duplicate = false, failedTests = 0 } = {}) {
  const root = '/evidence';
  const page = 'https://release.example.test/app/';
  const ipa = Buffer.from('synthetic IPA fixture, never a real signed package');
  const proof = { signatureVerified: true, tlsVerificationEnabled: true, publicStatus: 200,
    build: 7, url: page, ipaUrl: `${page}App-7.ipa`,
    ipaSha256: crypto.createHash('sha256').update(ipa).digest('hex') };
  const files = new Map([
    [`${root}/delivery-proof.json`, JSON.stringify(proof)],
    [`${root}/test-summary.json`, JSON.stringify({ result: 'Passed', passedTests: 3, failedTests, skippedTests: 0 })],
    [`${root}/notes.txt`, `Fixture only: ${page} ${proof.ipaUrl}`],
    ['/runbook.md', '# Test runbook\nNo credentials.'],
  ]);
  if (duplicate) files.set(`${root}/email-attempt.json`, '{}');
  const counters = { vault: 0, sends: 0 };
  const fakeFS = {
    readFileSync: (name, encoding) => {
      assert.ok(files.has(name), `Unexpected file read: ${name}`);
      return encoding ? String(files.get(name)) : Buffer.from(files.get(name));
    },
    existsSync: name => files.has(name),
    writeFileSync: (name, value, options) => {
      if (options?.flag === 'wx' && files.has(name)) throw new Error('EEXIST');
      files.set(name, value);
    },
  };
  const requestBodies = [];
  const fakeRequire = name => {
    if (name === 'node:fs') return fakeFS;
    if (name === 'node:dns') return { setDefaultResultOrder() {} };
    if (name === 'node:child_process') return { spawnSync(command, args) {
      assert.equal(command, 'vault');
      assert.equal(args.at(-1), 'kv/approved/test');
      counters.vault++;
      return { status: 0, stdout: JSON.stringify({ data: { data: { SENDGRID_API_KEY: 'synthetic-not-a-real-key' } } }) };
    } };
    return require(name);
  };
  const args = ['node', 'mailer', '--proof', `${root}/delivery-proof.json`, '--tests', `${root}/test-summary.json`,
    '--notes', `${root}/notes.txt`, '--recipient', 'authorized@example.test', '--app', 'Fixture App',
    '--attachment', '/runbook.md', '--vault-path', 'kv/approved/test'];
  if (send) args.push('--send');
  const context = vm.createContext({ require: fakeRequire, module: { exports: {} }, Buffer, URL, AbortSignal,
    console: { log() {}, error() {} }, process: { argv: args, env: {} },
    fetch: async (url, options) => {
      url = String(url);
      if (url === 'https://api.sendgrid.com/v3/mail/send') {
        counters.sends++;
        requestBodies.push(JSON.parse(options.body));
        if (ambiguous) throw new Error('Synthetic timeout');
        return { status, headers: { get: name => name === 'x-message-id' ? 'fixture-message-id' : null } };
      }
      const responses = new Map([
        [`${page}proof.json`, JSON.stringify(proof)],
        [`${page}manifest.plist`, `<string>${proof.ipaUrl}</string>`],
        [page, '<a href="itms-services://?action=download-manifest">Install</a>'],
        [proof.ipaUrl, badHash ? Buffer.from('wrong package') : ipa],
      ]);
      assert.ok(responses.has(url), `Unexpected network destination: ${url}`);
      return { status: 200, url, arrayBuffer: async () => Buffer.from(responses.get(url)) };
    },
  });
  vm.runInContext(source, context);
  return { main: context.module.exports.main, counters, files, requestBodies };
}

test('rejects unknown/incomplete flags and credential-bearing or non-HTTPS URLs', () => {
  assert.throws(() => parse(['--unknown', 'x']));
  assert.throws(() => parse(['--proof']));
  assert.throws(() => secureURL('http://example.test/'));
  assert.throws(() => secureURL('https://name:secret@example.test/'));
});
test('preview checks artifacts without reading Vault or sending', async () => {
  const f = fixture(); await f.main();
  assert.deepEqual(f.counters, { vault: 0, sends: 0 });
  assert.ok(f.files.has('/evidence/email-draft.json'));
});
test('accepted send records message ID, exact recipient, attachment and no inbox claim', async () => {
  const f = fixture({ send: true }); await f.main();
  assert.deepEqual(f.counters, { vault: 1, sends: 1 });
  const receipt = JSON.parse(f.files.get('/evidence/email-receipt.json'));
  assert.equal(receipt.accepted, true);
  assert.equal(receipt.messageId, 'fixture-message-id');
  assert.equal(receipt.mailboxDeliveryVerified, false);
  assert.equal(f.requestBodies[0].personalizations[0].to[0].email, 'authorized@example.test');
  assert.equal(f.requestBodies[0].attachments[0].filename, 'runbook.md');
  assert.ok(!JSON.stringify([...f.files.values()]).includes('synthetic-not-a-real-key'));
});
test('prior attempt blocks duplicate email before reading Vault', async () => {
  const f = fixture({ send: true, duplicate: true });
  await assert.rejects(f.main(), /Prior send attempt/);
  assert.deepEqual(f.counters, { vault: 0, sends: 0 });
});
test('hash mismatch or failing tests stop notification', async () => {
  for (const options of [{ badHash: true }, { failedTests: 1 }]) {
    const f = fixture({ send: true, ...options });
    await assert.rejects(f.main(), /hash changed|evidence gate/);
    assert.deepEqual(f.counters, { vault: 0, sends: 0 });
  }
});
test('rejection and ambiguous timeout retain receipts and prevent retry', async () => {
  for (const options of [{ status: 403 }, { ambiguous: true }]) {
    const f = fixture({ send: true, ...options });
    await assert.rejects(f.main(), /HTTP 403|Synthetic timeout/);
    const receipt = JSON.parse(f.files.get('/evidence/email-receipt.json'));
    assert.equal(receipt.accepted, options.ambiguous ? null : false);
    await assert.rejects(f.main(), /Prior send attempt/);
    assert.equal(f.counters.sends, 1);
  }
});