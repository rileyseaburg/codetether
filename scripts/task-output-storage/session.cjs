// Persistent psql connection with explicit barriers, not timing assumptions.
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
function session(t, db) {
    const name = `output_contract_${randomBytes(8).toString('hex')}`;
    const child = spawn('psql', db.args, { env: { ...db.env, PGAPPNAME: name } });
    let output = '', stderr = '', failure, notify = () => {};
    child.stdout.on('data', (data) => { output += data; notify(); });
    child.stderr.on('data', (data) => { stderr += data; });
    child.on('error', (error) => { failure = error; notify(); });
    child.on('exit', (code) => {
        failure = new Error(`psql exited (${code}): ${stderr.trim()}`); notify();
    });
    child.stdin.on('error', (error) => { failure = error; notify(); });
    t.after(() => { child.stdin.end(); child.kill(); });
    function send(statement) {
        const marker = `barrier_${randomBytes(8).toString('hex')}`;
        const start = output.length;
        child.stdin.write(`${statement}\n\\echo ${marker}\n`);
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error(`psql barrier timeout: ${stderr}`)), 16000);
            notify = () => {
                const end = output.indexOf(marker, start);
                if (end >= 0 || failure) {
                    clearTimeout(timer);
                    notify = () => {};
                    if (failure) reject(failure);
                    else resolve(output.slice(start, end).trim());
                }
            };
            notify();
        });
    }
    return { name, send };
}
async function waitForLock(db, name) {
    for (let attempt = 0; attempt < 100; attempt++) {
        if (await db.run(`SELECT count(*) FROM pg_stat_activity WHERE
            application_name = '${name}' AND wait_event_type = 'Lock';`) === '1') return;
        await new Promise((resolve) => setTimeout(resolve, 25));
    }
    throw new Error('Expected a PostgreSQL lock wait, not elapsed-time ordering');
}
module.exports = { session, waitForLock };