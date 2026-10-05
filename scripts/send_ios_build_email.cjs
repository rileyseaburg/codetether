#!/usr/bin/env node
// Single-recipient release notification, fail-closed on proof or duplicate-send gaps.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const dir = 'artifacts/ios-simulator-delivery';
async function main() {
  const receiptPath = `${dir}/email-receipt.json`;
  if (fs.existsSync(receiptPath)) throw new Error('A send receipt already exists; refusing duplicate notification');
  const recipient = process.argv[2];
  if (!recipient || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)) throw new Error('Specify one valid recipient');
  const proof = JSON.parse(fs.readFileSync(`${dir}/delivery-proof.json`));
  const live = JSON.parse(fs.readFileSync(`${dir}/live-proof.json`));
  const xcode = JSON.parse(fs.readFileSync(`${dir}/xcode-summary.json`));
  if (!live.simulatorOrigin || live.httpStatus !== 200 || proof.simulatorTaskId !== live.taskId
    || proof.liveSimulatorTestsPassed !== 1 || xcode.result !== 'Passed' || xcode.failedTests || xcode.skippedTests
    || !proof.signatureVerified || proof.publicStatus !== 200) throw new Error('Delivery proof gate not satisfied');
  const download = await fetch(proof.ipaUrl, { signal: AbortSignal.timeout(60000) });
  if (download.status !== 200) throw new Error('IPA is not publicly downloadable');
  const hash = crypto.createHash('sha256').update(Buffer.from(await download.arrayBuffer())).digest('hex');
  if (hash !== proof.ipaSha256) throw new Error('Published IPA changed after verification');
  const secret = spawnSync('vault', ['kv', 'get', '-format=json', 'kv/spotlessbinco-api/sendgrid'],
    { encoding: 'utf8', timeout: 30000 });
  if (secret.status !== 0) throw new Error('SendGrid Vault read failed; output suppressed');
  const apiKey = JSON.parse(secret.stdout).data.data.SENDGRID_API_KEY;
  if (!apiKey) throw new Error('SendGrid credential absent');
  const subject = 'A2A Monitor iPhone build — signed IPA and live simulator proof';
  const text = `Riley,

The signed A2A Monitor iOS test build is ready on the NAS.

Download / installation page:
${proof.url}

Direct signed IPA:
${proof.ipaUrl}

Version: 1.0.0 (2), bundle com.a2a.monitor.
Signing: Apple Distribution / Ad Hoc profile including your registered iPhone.
Open the installation page in Safari on that iPhone and use Install, or download the IPA for Apple Configurator/Xcode installation.

Simulator proof (completed BEFORE this email):
- Xcode live integration: 1 passed, 0 failed, 0 skipped.
- Native Swift client in iOS Simulator created real task ${live.taskId}.
- The local worker created and hosted the HTML page; the simulator received its result and verified the actual file, HTTP 200, SHA-256 and running service.
- HTML SHA-256: ${live.sha256}

Important limits: this test used a temporary, restricted service-auth harness. It did NOT test user password entry, the Keycloak sign-in UI, or installation on the disconnected physical iPhone. The build does not contain those service credentials. This is an Ad Hoc test build, not an App Store release.

After signing in, use Command > Tasks & Responses. You can select github-copilot/gpt-5-mini in the optional Model field; the app tracks the real task ID and shows its returned response.

IPA SHA-256:
${proof.ipaSha256}

The dedicated test account is codetether-ios-e2e@example.invalid. Its password remains in Vault at secret/codetether/ios-e2e-user; no password is included in this message.
`;
  const payload = { personalizations: [{ to: [{ email: recipient }] }],
    from: { email: 'noreply@codetether.run', name: 'CodeTether' }, subject,
    content: [{ type: 'text/plain', value: text }] };
  fs.writeFileSync(`${dir}/email-draft.json`, JSON.stringify(payload, null, 2) + '\n');
  const response = await fetch('https://api.sendgrid.com/v3/mail/send', {
    method: 'POST', headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal: AbortSignal.timeout(30000),
  });
  const receipt = { recipient, from: payload.from.email, subject, status: response.status,
    accepted: response.status === 202, messageId: response.headers.get('x-message-id'),
    sentAt: new Date().toISOString(), simulatorTaskId: live.taskId, ipaSha256: proof.ipaSha256 };
  fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify(receipt, null, 2));
  if (response.status !== 202) throw new Error(`SendGrid rejected notification: HTTP ${response.status}; inspect before retry`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });



