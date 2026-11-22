#!/usr/bin/env node
// Proof-gated, single-recipient release notification. Preview unless --send is explicit.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
function parse(argv) {
  const options = { send: false };
  const keys = new Set(['proof', 'tests', 'notes', 'recipient', 'app', 'attachment', 'vault-path', 'sender']);
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--send') { options.send = true; continue; }
    const key = argv[i].replace(/^--/, '');
    if (!keys.has(key) || !argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error('Unknown or incomplete option');
    options[key] = argv[++i];
  }
  for (const key of ['proof', 'tests', 'notes', 'recipient', 'app']) if (!options[key]) throw new Error(`--${key} is required`);
  return options;
}
function secureURL(value) {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Credential-free HTTPS URL required');
  return url;
}
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
async function main() {
  const options = parse(process.argv.slice(2));
  if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0') throw new Error('TLS verification must remain enabled');
  const sender = options.sender || 'noreply@codetether.run';
  for (const email of [sender, options.recipient]) {
    if (!/^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/.test(email)) throw new Error('Exactly one valid recipient and sender required');
  }
  const proof = JSON.parse(fs.readFileSync(options.proof));
  const tests = JSON.parse(fs.readFileSync(options.tests));
  if (proof.signatureVerified !== true || proof.publicStatus !== 200 || proof.tlsVerificationEnabled !== true
      || !/^[a-f0-9]{64}$/.test(proof.ipaSha256 || '') || !proof.build
      || tests.result !== 'Passed' || !Number.isSafeInteger(tests.passedTests) || tests.passedTests < 1
      || tests.failedTests !== 0 || tests.skippedTests !== 0) {
    throw new Error('Release evidence gate not satisfied');
  }
  const page = secureURL(proof.url), ipa = secureURL(proof.ipaUrl);
  if (page.origin !== ipa.origin) throw new Error('Unexpected cross-origin package URL');
  const get = async url => {
    const response = await fetch(url, { signal: AbortSignal.timeout(90000), cache: 'no-store' });
    if (response.status !== 200 || new URL(response.url).origin !== page.origin) throw new Error('Public release URL not available at its expected origin');
    return Buffer.from(await response.arrayBuffer());
  };
  const publicProof = JSON.parse((await get(new URL('proof.json', page))).toString());
  const manifest = (await get(new URL('manifest.plist', page))).toString();
  const index = (await get(page)).toString();
  if (String(publicProof.build) !== String(proof.build) || publicProof.ipaSha256 !== proof.ipaSha256
      || !manifest.includes(ipa.href) || !index.includes('itms-services:')) throw new Error('Published manifest/page/proof does not match this release');
  if (hash(await get(ipa)) !== proof.ipaSha256) throw new Error('Public IPA hash changed');
  const directory = path.dirname(options.proof);
  const subject = `${options.app} build ${proof.build} — install link and fixes`;
  const text = fs.readFileSync(options.notes, 'utf8');
  if (!text.includes(proof.url) || !text.includes(proof.ipaUrl)) throw new Error('Notes must include both verified URLs');
  const payload = { personalizations: [{ to: [{ email: options.recipient }] }],
    from: { email: sender, name: 'CodeTether' }, subject,
    content: [{ type: 'text/plain', value: text }] };
  let attachmentHash;
  if (options.attachment) {
    if (path.extname(options.attachment).toLowerCase() !== '.md') throw new Error('Only a reviewed Markdown runbook may be attached');
    const bytes = fs.readFileSync(options.attachment);
    if (bytes.length > 200000 || /-----BEGIN (?:RSA |EC )?PRIVATE KEY-----/.test(bytes.toString())) throw new Error('Unsafe or oversized attachment');
    attachmentHash = hash(bytes);
    payload.attachments = [{ content: bytes.toString('base64'), type: 'text/markdown',
      filename: path.basename(options.attachment), disposition: 'attachment' }];
  }
  fs.writeFileSync(path.join(directory, 'email-draft.json'), JSON.stringify(payload, null, 2) + '\n');
  if (!options.send) {
    console.log(JSON.stringify({ preview: true, recipient: options.recipient, subject, publicHashVerified: true, attachmentHash }));
    return;
  }
  const attemptPath = path.join(directory, 'email-attempt.json');
  const receiptPath = path.join(directory, 'email-receipt.json');
  if (fs.existsSync(attemptPath) || fs.existsSync(receiptPath)) throw new Error('Prior send attempt exists; inspect it before any retry');
  const secret = spawnSync('vault', ['kv', 'get', '-format=json', options['vault-path'] || 'kv/spotlessbinco-api/sendgrid'], {
    encoding: 'utf8', timeout: 30000 });
  if (secret.status !== 0) throw new Error('Vault SendGrid read failed; output suppressed');
  let key;
  try { key = JSON.parse(secret.stdout).data.data.SENDGRID_API_KEY; }
  catch { throw new Error('Vault response could not be read; output suppressed'); }
  if (!key) throw new Error('SendGrid credential missing');
  const attempt = { recipient: options.recipient, sender, subject, ipaSha256: proof.ipaSha256,
    attachmentHash, attemptedAt: new Date().toISOString(), acceptance: 'unknown' };
  fs.writeFileSync(attemptPath, JSON.stringify(attempt, null, 2), { flag: 'wx' });
  try {
    const response = await fetch('https://api.sendgrid.com/v3/mail/send', {
      method: 'POST', headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(30000),
    });
    const receipt = { ...attempt, httpStatus: response.status, accepted: response.status === 202,
      messageId: response.headers.get('x-message-id'), respondedAt: new Date().toISOString(),
      acceptance: response.status === 202 ? 'accepted' : 'rejected', mailboxDeliveryVerified: false };
    fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(receipt, null, 2));
    if (response.status !== 202) throw new Error(`SendGrid HTTP ${response.status}; inspect before retrying`);
  } catch (error) {
    if (!fs.existsSync(receiptPath)) fs.writeFileSync(receiptPath,
      JSON.stringify({ ...attempt, accepted: null, mailboxDeliveryVerified: false, diagnostic: 'No definitive response; do not automatically retry' }, null, 2), { flag: 'wx' });
    throw error;
  }
}
module.exports = { main, parse, secureURL };
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });