const test = require('node:test');
const assert = require('node:assert/strict');
const { writeFile, readFile } = require('node:fs/promises');
const { join } = require('node:path');
const { createContainer } = require('./recovery-container.cjs');
const { database } = require('./database.cjs');
const { fixture } = require('./fixture.cjs');
const { session } = require('./session.cjs');
const sql = require('./source.cjs');
test('SIGKILL recovery retains committed output and rolls back the open append', { timeout: 120000 }, async (t) => {
    const directory = process.env.TASK_OUTPUT_RECOVERY_REPORT_DIR;
    assert(directory, 'Use scripts/check_task_output_recovery.cjs for retained evidence');
    const container = await createContainer(directory);
    t.diagnostic(`Preserved container: ${container.id}`);
    t.after(() => container.retain());
    Object.assign(process.env, await container.ready());
    let db = await fixture(t);
    await db.run(sql.append('abc', 'committed-before-crash'));
    await db.run(sql.append('abc-2', 'other-task-committed'));
    const committed = await db.json(sql.bind(sql.replay, ['abc', 0]));
    const interrupted = session(t, db);
    await interrupted.send(sql.append('abc', 'must-rollback', '') + '\nSELECT count(*) FROM task_output_chunks;');
    assert.equal(await db.run(`SELECT count(*) FROM pg_stat_activity WHERE application_name = '${interrupted.name}' AND state = 'idle in transaction';`), '1');
    await writeFile(join(directory, 'before-crash.json'), JSON.stringify({
        containerId: container.id, schema: db.schema, sources: sql.hashes,
        committed, interruptedSession: interrupted.name,
    }, null, 2));
    await container.capture('before-crash');
    await container.crash();
    Object.assign(process.env, await container.restart());
    db = database(db.schema);
    assert.deepEqual(await db.json(sql.bind(sql.replay, ['abc', 0])), committed);
    assert.deepEqual(await db.json(sql.bind(sql.replay, ['abc', 1])), []);
    assert.equal(await db.run("SELECT count(*) FROM task_output_chunks WHERE output = 'must-rollback';"), '0');
    assert.equal((await db.json(sql.bind(sql.replay, ['abc-2', 0])))[0].output, 'other-task-committed');
    await db.run(sql.append('abc', 'committed-after-recovery'));
    const replay = await db.json(sql.bind(sql.replay, ['abc', 0]));
    assert.deepEqual(replay.map(({ cursor, output }) => [cursor, output]), [[1, 'committed-before-crash'], [2, 'committed-after-recovery']]);
    await container.capture('recovered');
    assert.match(await readFile(join(directory, 'recovered-postgres.log'), 'utf8'), /database system was interrupted/);
    await writeFile(join(directory, 'after-recovery.json'), JSON.stringify({
        containerId: container.id, schema: db.schema, sources: sql.hashes, replay,
        exclusiveReplay: await db.json(sql.bind(sql.replay, ['abc', 1])),
    }, null, 2));
});