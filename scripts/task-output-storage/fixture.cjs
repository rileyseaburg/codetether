// Deliberately preserve each isolated schema for inspection, including failures.
const { randomBytes } = require('node:crypto');
const { database } = require('./database.cjs');
const sql = require('./source.cjs');
async function fixture(t) {
    const db = database(`output_contract_${randomBytes(8).toString('hex')}`);
    t.diagnostic(`Preserved schema: ${db.schema}; sources: ${JSON.stringify(sql.hashes)}`);
    await db.run(`CREATE SCHEMA ${db.schema};
        CREATE TABLE tasks (id TEXT PRIMARY KEY, tenant_id TEXT, worker_id TEXT,
            status TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT '2026-01-01Z');
        CREATE TABLE workers (worker_id TEXT PRIMARY KEY);`);
    await db.run(sql.migration);
    await db.run(sql.migration);
    t.diagnostic(await db.run('SELECT version();'));
    await db.run(`INSERT INTO tasks (id, tenant_id, worker_id, status)
        VALUES ('abc', 'tenant-a', 'worker-a', 'running'),
            ('abc-2', 'tenant-b', 'worker-b', 'running');
        INSERT INTO workers (worker_id, spiffe_id)
        VALUES ('worker-a', 'spiffe://fixture/worker-a');`);
    return db;
}
module.exports = { fixture };
