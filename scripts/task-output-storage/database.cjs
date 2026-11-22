// Native PostgreSQL transport. Credentials stay in libpq's environment.
const { execFile } = require('node:child_process');
const args = ['-X', '--no-password', '--set=ON_ERROR_STOP=1', '--quiet', '--tuples-only', '--no-align'];
function database(schema) {
    if (process.env.TASK_OUTPUT_TEST_DATABASE !== '1') {
        throw new Error('Set TASK_OUTPUT_TEST_DATABASE=1 only for an isolated test database');
    }
    if (!/^output_contract_[a-z0-9_]+$/.test(schema)) throw new Error('Invalid fixture schema');
    for (const name of ['PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER']) {
        if (!process.env[name]) throw new Error(`${name} must explicitly identify the test database`);
    }
    const env = { ...process.env, PGOPTIONS: `${process.env.PGOPTIONS || ''} -c search_path=${schema},pg_catalog -c statement_timeout=15000 -c lock_timeout=10000` };
    // SQL travels over stdin, never shell interpolation or credential-bearing argv.
    async function query(sql) {
        return new Promise((resolve, reject) => {
            const child = execFile('psql', args, { env, timeout: 20000, maxBuffer: 4 * 1024 * 1024 },
                (error, stdout, stderr) => error ? reject(new Error(stderr.trim() || error.message)) : resolve(stdout.trim()));
            child.stdin.on('error', reject);
            child.stdin.end(sql);
        });
    }
    async function json(sql) {
        return JSON.parse(await query(`SELECT COALESCE(json_agg(row_to_json(r)), '[]'::json) FROM (${sql}) r;`));
    }
    return { schema, env, args, run: query, json };
}
module.exports = { database };