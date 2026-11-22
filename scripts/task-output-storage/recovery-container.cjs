// Only control the fresh container created here; never accept an existing ID.
const { execFile } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const { promisify } = require('node:util');
const { writeFile } = require('node:fs/promises');
const { join } = require('node:path');
const execute = promisify(execFile);
const label = 'codetether.task-output-recovery';
function owned(info, id, token) {
    if (!/^[a-f0-9]{64}$/.test(id) || info.Id !== id || info.Config?.Labels?.[label] !== token) {
        throw new Error('Refusing control: container ownership does not match this run');
    }
    const ports = info.HostConfig?.PortBindings;
    if (info.HostConfig?.NetworkMode === 'host' || Object.keys(ports || {}).length !== 1 ||
        ports['5432/tcp']?.length !== 1 || ports['5432/tcp'][0].HostIp !== '127.0.0.1') {
        throw new Error('Refusing control: container is not exclusively loopback-bound');
    }
}
function isolatedEnvironment(port, base = process.env) {
    const env = Object.fromEntries(Object.entries(base).filter(([key]) => !/^PG/i.test(key)));
    return { ...env, PGHOST: '127.0.0.1', PGPORT: port, PGDATABASE: 'task_output_recovery',
        PGUSER: 'postgres', PGCONNECT_TIMEOUT: '2', TASK_OUTPUT_TEST_DATABASE: '1' };
}
async function createContainer(directory) {
    if (process.env.TASK_OUTPUT_RECOVERY_DOCKER !== '1') {
        throw new Error('Set TASK_OUTPUT_RECOVERY_DOCKER=1 to create and crash a new test container');
    }
    const token = randomUUID();
    const docker = async (...args) => (await execute('docker', args,
        { timeout: 60000, maxBuffer: 4 * 1024 * 1024 })).stdout.trim();
    const id = await docker('run', '--detach', '--pull=never', '--name', `output-recovery-${token}`,
        '--label', `${label}=${token}`, '--publish', '127.0.0.1::5432',
        '--env', 'POSTGRES_DB=task_output_recovery', '--env', 'POSTGRES_HOST_AUTH_METHOD=trust',
        'postgres:16-alpine');
    // Persist the ID before readiness so startup failures still retain evidence.
    await writeFile(join(directory, 'container-id.txt'), `${id}\n`);
    async function inspect() {
        const info = JSON.parse(await docker('inspect', id))[0];
        owned(info, id, token);
        return info;
    }
    async function capture(stage) {
        const info = await inspect();
        // Never persist Config.Env: a caller may have sensitive Docker defaults.
        await writeFile(join(directory, `${stage}-container.json`), JSON.stringify({
            Id: info.Id, Name: info.Name, Image: info.Image, State: info.State,
            Ports: info.NetworkSettings.Ports,
            Volumes: info.Mounts.map(({ Type, Name, Destination }) => ({ Type, Name, Destination })),
        }, null, 2));
        const logs = await execute('docker', ['logs', '--timestamps', id],
            { timeout: 15000, maxBuffer: 4 * 1024 * 1024 });
        await writeFile(join(directory, `${stage}-postgres.log`), logs.stdout + logs.stderr);
    }
    async function ready() {
        const info = await inspect();
        const port = info.NetworkSettings.Ports['5432/tcp']?.[0];
        if (port?.HostIp !== '127.0.0.1' || !/^\d+$/.test(port.HostPort)) {
            throw new Error('Missing loopback-only PostgreSQL port');
        }
        const env = isolatedEnvironment(port.HostPort);
        let lastError;
        for (let attempt = 0; attempt < 60; attempt++) {
            try {
                await execute('psql', ['-X', '--no-password', '--set=ON_ERROR_STOP=1', '-c', 'SELECT 1'],
                    { env, timeout: 3000 });
                return env;
            } catch (error) { lastError = error; }
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
        throw new Error(`Test PostgreSQL did not become ready: ${lastError.message}`);
    }
    return {
        id, ready, capture,
        async crash() {
            await inspect();
            await docker('kill', '--signal=KILL', id);
            const info = await inspect();
            if (info.State.Running || info.State.ExitCode !== 137) throw new Error('Expected SIGKILL exit 137');
            await capture('crashed');
        },
        async restart() { await inspect(); await docker('start', id); return ready(); },
        async retain() {
            const info = await inspect();
            if (info.State.Running) await docker('stop', '--time=3', id);
            await capture('retained');
        },
    };
}
module.exports = { createContainer, owned, isolatedEnvironment };