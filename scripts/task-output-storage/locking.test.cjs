const { test } = require('node:test');
const assert = require('node:assert/strict');
const { fixture } = require('./fixture.cjs');
const { session, waitForLock } = require('./session.cjs');
const sql = require('./source.cjs');
test('completion waits for an append holding the production task-row lock', async (t) => {
    const db = await fixture(t), writer = session(t, db), terminal = session(t, db);
    await writer.send(`BEGIN; ${sql.bind(sql.lock, ['abc'])};`);
    const completing = terminal.send("UPDATE tasks SET status = 'completed' WHERE id = 'abc';");
    await waitForLock(db, terminal.name);
    await writer.send(`${sql.bind(sql.next, ['abc'])};
        ${sql.bind(sql.insert, ['abc', 1, 'worker-a', 'before completion', 'fixture', null])};
        ${sql.bind(sql.update, ['abc'])}; COMMIT;`);
    await completing;
    assert.equal((await db.json(sql.bind(sql.task, ['abc'])))[0].status, 'completed');
    assert.equal((await db.json(sql.bind(sql.replay, ['abc', 0, 1001])))[0].output, 'before completion');
});
test('waiting writer observes committed terminal status before deciding to append', async (t) => {
    const db = await fixture(t), terminal = session(t, db), writer = session(t, db);
    await terminal.send("BEGIN; UPDATE tasks SET status = 'completed' WHERE id = 'abc';");
    const locking = writer.send(`BEGIN; ${sql.bind(sql.lock, ['abc'])};`);
    await waitForLock(db, writer.name);
    await terminal.send('COMMIT;');
    await locking;
    assert.equal(await writer.send("SELECT status FROM tasks WHERE id = 'abc';"), 'completed');
    await writer.send('ROLLBACK;');
    assert.deepEqual(await db.json(sql.bind(sql.replay, ['abc', 0, 1001])), []);
});
test('repeatable-read replay retains a consistent output/status snapshot', async (t) => {
    const db = await fixture(t), reader = session(t, db);
    await reader.send(`BEGIN ISOLATION LEVEL REPEATABLE READ; ${sql.bind(sql.task, ['abc'])};`);
    await db.run(sql.append('abc', 'new output'));
    await db.run("UPDATE tasks SET status = 'completed' WHERE id = 'abc';");
    assert.equal(await reader.send("SELECT status FROM tasks WHERE id = 'abc';"), 'running');
    assert.equal(await reader.send("SELECT count(*) FROM task_output_chunks WHERE task_id = 'abc';"), '0');
    await reader.send('COMMIT;');
    assert.equal((await db.json(sql.bind(sql.task, ['abc'])))[0].status, 'completed');
    assert.equal((await db.json(sql.bind(sql.replay, ['abc', 0, 1001]))).length, 1);
});