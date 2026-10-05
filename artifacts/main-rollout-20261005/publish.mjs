import { execFileSync, spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync, openSync, closeSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const image = process.argv[2]
const revision = 'eb2051a212a2c729a7963da8e1dda39a4e958513'
if (!/^registry\.quantum-forge\.net\/cluster-ci-cache\/(a2a-server-mcp:main|codetether-marketing:ui)-eb2051a212a2$/.test(image ?? '')) {
  throw new Error('Expected an exact image built from the reviewed source revision')
}
const out = dirname(fileURLToPath(import.meta.url))
const name = image.includes('/a2a-server-mcp:') ? 'server' : 'dashboard'
const docker = ['-H', 'unix:///var/run/docker.sock']
const metadata = JSON.parse(execFileSync('docker', [...docker, 'image', 'inspect', image], { encoding: 'utf8' }))[0]
if (metadata.Config.Labels?.['org.opencontainers.image.revision'] !== revision) {
  throw new Error('Image source-revision label does not match the requested commit')
}
const secret = JSON.parse(execFileSync('kubectl', [
  'get', 'secret', 'harbor-core', '-n', 'container-registry', '-o', 'json',
], { encoding: 'utf8' }))
const password = Buffer.from(secret.data.HARBOR_ADMIN_PASSWORD, 'base64').toString()
const temporary = mkdtempSync(join(tmpdir(), 'codetether-main-publish-'))
try {
  const env = { ...process.env, DOCKER_CONFIG: temporary }
  const login = spawnSync('docker', [
    ...docker, 'login', 'registry.quantum-forge.net', '--username', 'admin', '--password-stdin',
  ], { env, input: password, encoding: 'utf8' })
  console.log(`harbor_login_exit=${login.status}`)
  if (login.status !== 0) throw new Error('Configured Harbor login rejected; no credential values logged')
  const log = openSync(join(out, `${name}-push-harbor.log`), 'w', 0o600)
  let result
  try {
    result = spawnSync('docker', [...docker, 'push', image], { env, stdio: ['ignore', log, log] })
  } finally {
    closeSync(log)
  }
  console.log(`${name}_push_exit=${result.status}`)
  if (result.status !== 0) throw new Error(`Registry publish failed; see ${name}-push-harbor.log`)
  const data = JSON.parse(execFileSync('docker', [...docker, 'image', 'inspect', image], { env, encoding: 'utf8' }))[0]
  const digest = data.RepoDigests.find(value => value.startsWith(`${image.split(':')[0]}@sha256:`))
  if (!digest) throw new Error('No registry digest was recorded after the successful push')
  const release = { image, digest, imageId: data.Id, sourceRevision: revision, pullSecret: 'registry-credentials' }
  writeFileSync(join(out, `${name}-release.json`), `${JSON.stringify(release, null, 2)}\n`)
  console.log(JSON.stringify(release, null, 2))
} finally {
  rmSync(temporary, { recursive: true, force: true })
}