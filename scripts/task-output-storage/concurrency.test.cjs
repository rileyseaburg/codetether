const { test } = require('node:test');
const assert = require('node:assert/strict');
const { fixture } = require('./fixture.cjs');
const sql = require('./source.cjs');
test('24 concurrent writers allocate ordered unique cursors under the production lock', async (t) => {
    const db = await fixture(t);
    assert(sql.task.endsWith('WHERE id = $1'));
    await Promise.all(Array.from({ length: 24 }, (_, n) => db.run(sql.append('abc', `chunk-${n}`))));
    const rows = await db.json(sql.bind(sql.replay, ['abc', 0, 1001]));
    assert.deepEqual(rows.map((row) => row.cursor), Array.from({ length: 24 }, (_, n) => n + 1));
    assert.equal(new Set(rows.map((row) => row.output)).size, 24);
    assert(rows.every((row) => row.worker_id === 'worker-a' && row.event.type === 'progress'));
    assert.deepEqual(await db.json(sql.bind(sql.replay, ['abc-2', 0, 1001])), []);
});
test('rollback consumes neither a cursor nor a task update', async (t) => {
    const db = await fixture(t);
    await db.run(sql.append('abc', 'first'));
    const before = await db.run("SELECT updated_at FROM tasks WHERE id = 'abc';");
    await db.run(sql.append('abc', 'rolled-back', 'ROLLBACK'));
    assert.equal(await db.run("SELECT updated_at FROM tasks WHERE id = 'abc';"), before);
    await db.run(sql.append('abc', 'second'));
    const rows = await db.json(sql.bind(sql.replay, ['abc', 0, 1001]));
    assert.deepEqual(rows.map(({ cursor, output }) => [cursor, output]), [[1, 'first'], [2, 'second']]);
});
test('migration enforces positive unique task-owned cursors and cascade deletion', async (t) => {
    const db = await fixture(t);
    await db.run(sql.append('abc', 'first'));
    for (const [id, cursor] of [['abc', 0], ['abc', 1], ['missing', 2]]) {
        await assert.rejects(db.run(sql.bind(sql.insert,
            [id, cursor, 'worker-a', 'invalid', 'fixture', null])));
    }
    assert.equal(await db.run("SELECT spiffe_id FROM workers WHERE worker_id = 'worker-a';"), 'spiffe://fixture/worker-a');
    await db.run("DELETE FROM tasks WHERE id = 'abc';");
    assert.deepEqual(await db.json(sql.bind(sql.replay, ['abc', 0, 1001])), []);
});