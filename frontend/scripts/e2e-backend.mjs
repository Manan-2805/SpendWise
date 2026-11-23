import { spawn, spawnSync } from 'node:child_process'
import { once } from 'node:events'
import { mkdtempSync, rmSync, symlinkSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const frontend = join(root, 'frontend')
const project = `spendwise-frontend-e2e-${process.pid}`
const temporary = mkdtempSync(join(tmpdir(), 'spendwise-frontend-e2e-'))
const inherited = ['PATH', 'HOME', 'USER', 'CI', 'LD_LIBRARY_PATH', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'SPENDWISE_SCREENSHOTS']
const env = {
  ...Object.fromEntries(inherited.flatMap(key => process.env[key] ? [[key, process.env[key]]] : [])),
  COMPOSE_DISABLE_ENV_FILE: '1',
}

async function availablePort() {
  const socket = createServer()
  socket.listen(0, '127.0.0.1')
  await once(socket, 'listening')
  const { port } = socket.address()
  await new Promise((resolve, reject) => socket.close(error => error ? reject(error) : resolve()))
  return port
}

function run(command, args, cwd, options = env) {
  const status = spawnSync(command, args, { cwd, env: options, stdio: 'inherit' })
  if (status.error || status.status !== 0) throw new Error(`${command} failed`, { cause: status.error })
}

const compose = ['compose', '-p', project, '-f', join(root, 'docker-compose.test.yml')]
let api
let started = false
try {
  const apiPort = await availablePort()
  env.TEST_POSTGRES_PORT = String(await availablePort())
  env.TEST_REDIS_PORT = String(await availablePort())
  started = true
  run('docker', [...compose, 'up', '-d', '--wait'], temporary)
  const settings = {
    ...env,
    PYTHONPATH: root,
    DATABASE_URL: `postgresql://spendwise_test:spendwise_test_local@127.0.0.1:${env.TEST_POSTGRES_PORT}/spendwise_test`,
    REDIS_URL: `redis://127.0.0.1:${env.TEST_REDIS_PORT}/0`,
    CELERY_BROKER_URL: `redis://127.0.0.1:${env.TEST_REDIS_PORT}/1`,
    CELERY_RESULT_BACKEND: `redis://127.0.0.1:${env.TEST_REDIS_PORT}/2`,
    ENVIRONMENT: 'development', DEBUG: 'false', SMTP_HOST: '', SMTP_FROM: '',
    CORS_ORIGINS: '[]', TRUSTED_HOSTS: '[]', FRONTEND_URL: 'http://localhost:3000',
    SECRET_KEY: crypto.randomUUID() + crypto.randomUUID(),
  }
  symlinkSync(join(root, 'alembic'), join(temporary, 'alembic'), 'dir')
  const python = ['run', '--project', root, '--no-sync', 'python']
  run('uv', [...python, '-m', 'alembic', '-c', join(root, 'alembic.ini'), 'upgrade', 'head'], temporary, settings)
  api = spawn('uv', [...python, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(apiPort), '--no-access-log'], {
    cwd: temporary, env: settings, stdio: 'inherit',
  })
  const apiUrl = `http://127.0.0.1:${apiPort}`
  for (let attempt = 0; attempt < 60; attempt++) {
    const live = await fetch(apiUrl + '/api/v1/health/live').then(response => response.ok).catch(() => false)
    if (live) break
    if (api.exitCode !== null || attempt === 59) throw new Error('Disposable API failed to start.')
    await new Promise(resolve => setTimeout(resolve, 250))
  }
  run('npm', ['exec', '--', 'playwright', 'test', ...process.argv.slice(2)], frontend, { ...env, SPENDWISE_E2E_UPSTREAM: apiUrl })
} finally {
  if (api && api.exitCode === null) {
    api.kill()
    await once(api, 'exit').catch(() => {})
  }
  try {
    // The test services mount their storage as tmpfs. This removes their containers and network.
    if (started) run('docker', [...compose, 'down'], temporary)
  } finally {
    rmSync(temporary, { recursive: true, force: true })
  }
}
