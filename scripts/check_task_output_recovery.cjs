#!/usr/bin/env node
// Explicitly opted-in local/CI storage proof, never live deployment proof.
const { spawnSync } = require('node:child_process');
const { mkdirSync, writeFileSync } = require('node:fs');
const { resolve, join } = require('node:path');
if (process.env.TASK_OUTPUT_RECOVERY_DOCKER !== '1') {
    console.error('Set TASK_OUTPUT_RECOVERY_DOCKER=1 to crash a fresh test-owned container (never an existing database).');
    process.exit(2);
}
const root = resolve(__dirname, '..');
const base = resolve(process.env.TASK_OUTPUT_REPORT_DIR || join(root, 'artifacts/task-output/postgres-recovery'));
const directory = join(base, new Date().toISOString().replaceAll(':', '-'));
mkdirSync(directory, { recursive: true });
const result = spawnSync(process.execPath, ['--test', '--test-reporter=tap',
    join(__dirname, 'task-output-storage/recovery-safety.test.cjs'),
    join(__dirname, 'task-output-storage/recovery.test.cjs')], {
    cwd: root, env: { ...process.env, TASK_OUTPUT_RECOVERY_REPORT_DIR: directory },
    encoding: 'utf8', timeout: 180000, maxBuffer: 8 * 1024 * 1024,
});
const output = (result.stdout || '') + (result.stderr || '');
writeFileSync(join(directory, 'recovery.tap'), output);
writeFileSync(join(directory, 'result.json'), JSON.stringify({
    evidenceLevel: 'static/local', command: 'TASK_OUTPUT_RECOVERY_DOCKER=1 node scripts/check_task_output_recovery.cjs',
    exitCode: result.status, signal: result.signal,
    error: result.error?.message, reportDirectory: directory,
}, null, 2));
process.stdout.write(output);
console.log(`Preserved recovery evidence: ${directory}`);
process.exit(result.status === 0 && !result.error ? 0 : 1);