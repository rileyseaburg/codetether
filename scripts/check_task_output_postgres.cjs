// Run only against an explicitly acknowledged, isolated PostgreSQL database.
const { spawn } = require('node:child_process');
const { createWriteStream, mkdirSync } = require('node:fs');
const { resolve } = require('node:path');
const { database } = require('./task-output-storage/database.cjs');

database('output_contract_preflight'); // Validate acknowledgement and libpq settings.
const root = resolve(__dirname, '..');
const directory = resolve(root, process.env.TASK_OUTPUT_REPORT_DIR ||
    'artifacts/task-output/postgres-contract');
mkdirSync(directory, { recursive: true });
const report = resolve(directory, `${new Date().toISOString().replaceAll(':', '-')}-${process.pid}.tap`);
const evidence = createWriteStream(report, { flags: 'wx' });
const child = spawn(process.execPath, ['--test', '--test-concurrency=1', '--test-reporter=tap',
    'scripts/task-output-storage/concurrency.test.cjs',
    'scripts/task-output-storage/locking.test.cjs',
    'scripts/task-output-storage/replay.test.cjs'], { cwd: root });
evidence.on('error', (error) => {
    console.error(`Evidence write failed: ${error.message}`);
    child.kill();
    process.exitCode = 1;
});
child.stdout.on('data', (data) => { evidence.write(data); process.stdout.write(data); });
child.stderr.on('data', (data) => { evidence.write(data); process.stderr.write(data); });
child.on('error', (error) => {
    evidence.write(`# Runner startup error: ${error.message}\n`);
    process.exitCode = 1;
});
child.on('close', (code, signal) => {
    evidence.end(`# Runner exit: ${code}; signal: ${signal || 'none'}\n`, () => {
        console.log(`Storage-contract evidence: ${report}`);
        process.exitCode = process.exitCode || (code === 0 ? 0 : 1);
    });
});