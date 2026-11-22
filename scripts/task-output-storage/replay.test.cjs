const { test } = require('node:test');
const assert = require('node:assert/strict');
const { fixture } = require('./fixture.cjs');
const sql = require('./source.cjs');
test('exclusive replay persists across new connections with 1000 rows plus lookahead', async (t) => {
    const db = await fixture(t);
    await db.run(`INSERT INTO task_output_chunks (task_id, cursor, worker_id, output, timestamp)
        SELECT 'abc', n, 'worker-a', 'chunk-' || n, 'fixture' FROM generate_series(1, 1004) n;`);
    const first = await db.json(sql.bind(sql.replay, ['abc', 0, 1001]));
    assert.equal(first.length, 1001);
    assert.equal(first[999].cursor, 1000);
    assert.equal(first[1000].cursor, 1001);
    // Every db.json invocation starts a new psql connection.
    const second = await db.json(sql.bind(sql.replay, ['abc', first[999].cursor, 1001]));
    assert.deepEqual(second.map((row) => row.cursor), [1001, 1002, 1003, 1004]);
    assert.deepEqual(await db.json(sql.bind(sql.replay, ['abc-2', 0, 1001])), []);
    const terminal = await db.json(sql.bind(sql.replay, ['abc', 1004, 1001]));
    assert.deepEqual(terminal, []);
    await db.run("UPDATE tasks SET status = 'completed' WHERE id = 'abc';");
    const task = await db.json(sql.bind(sql.task, ['abc']));
    assert.equal(task[0].status, 'completed');
    assert.equal((await db.json(sql.bind(sql.replay, ['abc', 1003, 1001])))[0].cursor, 1004);
});