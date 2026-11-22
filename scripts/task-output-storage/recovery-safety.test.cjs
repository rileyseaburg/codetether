const test = require('node:test');
const assert = require('node:assert/strict');
const { owned, isolatedEnvironment } = require('./recovery-container.cjs');
const id = 'a'.repeat(64);
function info() {
    return { Id: id, Config: { Labels: { 'codetether.task-output-recovery': 'this-run' } },
        HostConfig: { NetworkMode: 'default', PortBindings: { '5432/tcp': [{ HostIp: '127.0.0.1', HostPort: '' }] } } };
}
test('only the exact owned loopback-bound container can be controlled', () => {
    assert.doesNotThrow(() => owned(info(), id, 'this-run'));
    assert.throws(() => owned(info(), 'b'.repeat(64), 'this-run'), /ownership/);
    assert.throws(() => owned(info(), 'postgres', 'this-run'), /ownership/);
    assert.throws(() => owned(info(), id, 'another-run'), /ownership/);
    for (const binding of ['0.0.0.0', '', '::']) {
        const altered = info();
        altered.HostConfig.PortBindings['5432/tcp'][0].HostIp = binding;
        assert.throws(() => owned(altered, id, 'this-run'), /loopback/);
    }
    const altered = info();
    altered.HostConfig.NetworkMode = 'host';
    assert.throws(() => owned(altered, id, 'this-run'), /loopback/);
    altered.HostConfig.NetworkMode = 'default';
    altered.HostConfig.PortBindings['9999/tcp'] = [{ HostIp: '127.0.0.1' }];
    assert.throws(() => owned(altered, id, 'this-run'), /loopback/);
});
test('recovery connections never inherit libpq service, credentials, or options', () => {
    const env = isolatedEnvironment('15432', { PATH: '/usr/bin', PGHOST: 'production.invalid',
        PGPASSWORD: 'fixture-only', PGSERVICE: 'external', PGOPTIONS: '-c search_path=public' });
    assert.equal(env.PGHOST, '127.0.0.1');
    assert.equal(env.PGPORT, '15432');
    assert.equal(env.PATH, '/usr/bin');
    assert(!('PGPASSWORD' in env) && !('PGSERVICE' in env) && !('PGOPTIONS' in env));
});