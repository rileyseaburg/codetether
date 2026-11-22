// Extract literal SQL from the production helper; never execute Python.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { createHash } = require('node:crypto');
const { resolve } = require('node:path');
const root = resolve(__dirname, '../..');
const source = readFileSync(resolve(root, 'a2a_server/task_output.py'), 'utf8');
const migration = readFileSync(resolve(root, 'a2a_server/migrations/038_task_output_replay.sql'), 'utf8');
function query(prefix) {
    const matches = [...source.matchAll(/(?:'[^'\n]*'\s*)+/g)]
        .map(([block]) => [...block.matchAll(/'([^']*)'/g)].map(([, part]) => part).join(''))
        .filter((text) => text.startsWith(prefix));
    assert.equal(matches.length, 1, `Expected one production SQL literal: ${prefix}`);
    return matches[0];
}
function literal(value) {
    if (value === null) return 'NULL';
    if (typeof value === 'number') {
        assert(Number.isSafeInteger(value));
        return String(value);
    }
    return `'${String(value).replaceAll("'", "''")}'`;
}
function bind(sql, values) {
    return sql.replace(/\$(\d+)/g, (_, index) => {
        assert(Number(index) <= values.length, `Unbound parameter $${index}`);
        return literal(values[Number(index) - 1]);
    });
}
const task = query('SELECT id, tenant_id, worker_id, status FROM tasks');
const next = query('SELECT COALESCE(MAX(cursor), 0) + 1 FROM task_output_chunks');
const insert = query('INSERT INTO task_output_chunks');
const replay = query('SELECT cursor, output, timestamp, worker_id, event ');
const touch = query('UPDATE tasks SET updated_at = NOW()');
const worker = query('SELECT spiffe_id FROM workers WHERE worker_id = $1');
function append(id, output, commit = 'COMMIT') {
    const allocation = bind(next, [id]);
    const prefix = 'VALUES (' + literal(id) + ', 0,';
    const insertion = bind(insert, [id, 0, 'worker-a', output, '2026-01-01T00:00:00Z', '{"type":"progress"}']);
    assert(insertion.includes(prefix), 'Production insert parameter order changed');
    return `BEGIN; ${bind(task, [id])} FOR UPDATE; ${insertion.replace(prefix,
        'VALUES (' + literal(id) + ', (' + allocation + '),')}; ${bind(touch, [id])}; ${commit};`;
}
module.exports = { migration, bind, task, lock: task + ' FOR UPDATE', next, insert, replay, update: touch, worker, append,
    hashes: { helper: createHash('sha256').update(source).digest('hex'),
        migration: createHash('sha256').update(migration).digest('hex') } };