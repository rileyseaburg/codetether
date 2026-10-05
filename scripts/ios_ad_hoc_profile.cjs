#!/usr/bin/env node
// Create/reuse a device-scoped profile; private keys never leave process memory.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
require('node:dns').setDefaultResultOrder('ipv4first');
const output = path.resolve(__dirname, '../artifacts/ios-simulator-delivery');
function secret(location) {
  const r = spawnSync('vault', ['kv', 'get', '-format=json', location], { encoding: 'utf8', timeout: 30000 });
  if (r.status !== 0) throw new Error('Vault read failed; output suppressed');
  return JSON.parse(r.stdout).data.data;
}
async function main() {
  const proof = JSON.parse(fs.readFileSync(path.join(output, 'live-proof.json')));
  if (!proof.simulatorOrigin || proof.httpStatus !== 200) throw new Error('Live simulator gate not satisfied');
  const key = secret('secret/codetether/ios-api-key');
  const signing = secret('secret/codetether/ios-signing/distribution-6JF3S3B8MP');
  const filename = Object.keys(key).find(k => /^AuthKey_[A-Z0-9]+\.p8$/.test(k));
  if (!filename || !key.issuer_id) throw new Error('App Store Connect key metadata missing');
  const now = Math.floor(Date.now() / 1000);
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');
  const input = encode({ alg: 'ES256', kid: filename.slice(8, -3), typ: 'JWT' }) + '.' +
    encode({ iss: key.issuer_id, iat: now, exp: now + 1200, aud: 'appstoreconnect-v1' });
  const signature = crypto.sign('sha256', Buffer.from(input), { key: key[filename], dsaEncoding: 'ieee-p1363' }).toString('base64url');
  async function api(route, method = 'GET', body) {
    const response = await fetch(`https://api.appstoreconnect.apple.com/v1/${route}`, { method,
      headers: { Authorization: `Bearer ${input}.${signature}`, 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(`App Store Connect HTTP ${response.status}: ${(error.errors || []).map(e => e.code).join(',')}`);
    }
    return response.json();
  }
  let bundles = await api('bundleIds?filter%5Bidentifier%5D=com.a2a.monitor');
  if (!bundles.data.length) bundles = { data: [(await api('bundleIds', 'POST', { data: {
    type: 'bundleIds', attributes: { identifier: 'com.a2a.monitor', name: 'A2A Monitor', platform: 'IOS' },
  } })).data] };
  if (bundles.data.length !== 1) throw new Error('Ambiguous bundle ID');
  const device = await api('devices?filter%5Budid%5D=00008110-001879C23E0A401E');
  if (device.data.length !== 1 || device.data[0].attributes.status !== 'ENABLED') throw new Error('Riley iPhone is not enabled for signing');
  const certificateId = signing.certificate_id;
  const cert = (await api(`certificates/${certificateId}`)).data;
  if (new Date(cert.attributes.expirationDate) <= new Date()) throw new Error('Distribution certificate expired');
  const name = 'A2A Monitor Ad Hoc 20261005';
  const existing = await api(`profiles?filter%5Bname%5D=${encodeURIComponent(name)}`);
  let profile = existing.data.find(p => p.attributes.name === name && p.attributes.profileState === 'ACTIVE');
  if (profile) {
    const bundle = await api(`profiles/${profile.id}/bundleId`);
    if (bundle.data.id !== bundles.data[0].id) throw new Error('Existing profile belongs to another app');
  } else {
    profile = (await api('profiles', 'POST', { data: { type: 'profiles',
      attributes: { name, profileType: 'IOS_APP_ADHOC' }, relationships: {
        bundleId: { data: { type: 'bundleIds', id: bundles.data[0].id } },
        certificates: { data: [{ type: 'certificates', id: certificateId }] },
        devices: { data: [{ type: 'devices', id: device.data[0].id }] },
      } } })).data;
  }
  fs.writeFileSync(path.join(output, 'A2AMonitor.mobileprovision'), Buffer.from(profile.attributes.profileContent, 'base64'));
  const record = { profileId: profile.id, uuid: profile.attributes.uuid, name, bundleId: 'com.a2a.monitor',
    certificateId, deviceId: device.data[0].id, deviceUDID: device.data[0].attributes.udid,
    expiresAt: profile.attributes.expirationDate, type: profile.attributes.profileType };
  fs.writeFileSync(path.join(output, 'signing-profile.json'), JSON.stringify(record, null, 2) + '\n');
  console.log(JSON.stringify(record));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });


