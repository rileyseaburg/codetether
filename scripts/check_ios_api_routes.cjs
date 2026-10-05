#!/usr/bin/env node
// Check literal native-client routes against a downloaded OpenAPI document.
// This is a static contract check, not an authenticated end-to-end test.
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const schemaPath = process.argv[2];
if (!schemaPath) throw new Error('Usage: node scripts/check_ios_api_routes.cjs openapi.json');
const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
const normalize = path => '/' + path.replace(/^\//, '')
  .replace(/\\\([^)]*\)/g, '{}').replace(/\{[^}]*\}/g, '{}');
const known = new Set(Object.keys(schema.paths).map(normalize));
let checked = 0;
let missing = 0;
for (const name of ['A2AClient.swift', 'AuthService.swift']) {
  const path = resolve(__dirname, '../ui/swift/A2AMonitor/Sources/A2AMonitor/Services', name);
  const source = readFileSync(path, 'utf8');
  for (const match of source.matchAll(/appendingPathComponent\("([^"\n]+)"\)/g)) {
    const route = match[1];
    if (!route.startsWith('/v1/') && !route.startsWith('v1/')) continue;
    checked++;
    if (!known.has(normalize(route))) {
      console.error(`${name}: route absent from OpenAPI: ${route}`);
      missing++;
    }
  }
}
if (!checked) throw new Error('No routes checked');
console.log(JSON.stringify({ checked, missing, scope: 'static path existence only' }));
if (missing) process.exitCode = 1;