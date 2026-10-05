const { ESLint } = require('../../marketing-site/node_modules/eslint');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
(async () => {
  const eslint = new ESLint({ cwd: path.join(root, 'marketing-site') });
  const names = ['diff', '--name-only', '--', 'marketing-site'];
  const changed = execFileSync('git', names, { cwd: root, encoding: 'utf8' });
  const added = execFileSync('git', ['ls-files', '--others', '--exclude-standard', '--', 'marketing-site/src', 'marketing-site/tests', 'marketing-site/e2e', 'marketing-site/jest.*.config.cjs'], { cwd: root, encoding: 'utf8' });
  const files = [...new Set((changed + added).trim().split('\n'))].filter(file => /\.(tsx?|cjs)$/.test(file) && !file.endsWith('next-env.d.ts'));
  const results = [];
  for (const file of files) {
    let baseline = '';
    try { baseline = execFileSync('git', ['show', `HEAD:${file}`], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); } catch {}
    const filePath = path.join(root, file);
    const before = baseline ? await eslint.lintText(baseline, { filePath }) : [];
    const after = await eslint.lintFiles([filePath]);
    const errors = after.flatMap(result => result.messages).filter(message => message.severity === 2);
    const existing = before.flatMap(result => result.messages).filter(message => message.severity === 2);
    const key = message => `${message.ruleId}:${message.message.split('\n\n')[0]}`;
    const counts = new Map();
    for (const error of existing) counts.set(key(error), (counts.get(key(error)) || 0) + 1);
    const introduced = errors.filter(error => {
      const count = counts.get(key(error)) || 0;
      if (!count) return true;
      counts.set(key(error), count - 1); return false;
    });
    results.push({ file, errorCount: errors.length, baselineErrorCount: existing.length, introduced, messages: after.flatMap(result => result.messages) });
  }
  fs.writeFileSync(path.join(__dirname, 'lint-comparison.json'), JSON.stringify(results, null, 2));
  const introduced = results.reduce((n, result) => n + result.introduced.length, 0);
  console.log(JSON.stringify({ level: 'static/local', files: files.length, existingErrors: results.reduce((n, r) => n + r.baselineErrorCount, 0), currentErrors: results.reduce((n, r) => n + r.errorCount, 0), introducedErrors: introduced }));
  for (const result of results) if (result.introduced.length) console.log(JSON.stringify({ file: result.file, introduced: result.introduced }));
  process.exitCode = introduced ? 1 : 0;
})().catch(error => { console.error(error); process.exitCode = 1; });