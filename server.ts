import express from 'express';
import { execFile } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CURATED_FILES = [
  { path: 'README.md', group: 'Hub Root' },
  { path: 'donate.md', group: 'Agent Entry Points' },
  { path: 'launch.md', group: 'Agent Entry Points' },
  { path: 'registry/3sum-exponent.toml', group: 'Registry' },
  { path: 'registry/fast-int-sort.toml', group: 'Registry' },
  { path: 'registry/nanogpt-speedrun.toml', group: 'Registry' },
  { path: 'registry/nanogpt-speedrun.records.toml', group: 'Registry' },
  { path: 'registry/cap-set-dimension-7.toml', group: 'Registry' },
  { path: 'skills/new-challenge/SKILL.md', group: 'Claude Code Skills' },
  { path: 'skills/register-repo/SKILL.md', group: 'Claude Code Skills' },
  { path: 'skills/donate/SKILL.md', group: 'Claude Code Skills' },
  { path: '.claude-plugin/marketplace.json', group: 'Claude Code Skills' },
  { path: '.claude-plugin/plugin.json', group: 'Claude Code Skills' },
  { path: 'templates/_common/AGENTS.md', group: 'Templates' },
  { path: 'templates/_common/.github/workflows/verify.yml', group: 'Templates' },
  { path: 'templates/_common/.github/workflows/report.yml', group: 'Templates' },
  { path: 'templates/_common/.github/workflows/leaderboard.yml', group: 'Templates' },
  { path: 'templates/script/superautoresearch.toml', group: 'Templates' },
  { path: 'templates/script/verifier/score.py', group: 'Templates' },
  { path: 'templates/lean/superautoresearch.toml', group: 'Templates' },
  { path: 'templates/lean/statement/Statement.lean', group: 'Templates' },
  { path: 'templates/manual/superautoresearch.toml', group: 'Templates' },
  { path: '.github/workflows/validate-entry.yml', group: 'Hub Workflows' },
  { path: '.github/workflows/sync.yml', group: 'Hub Workflows' },
  { path: '.github/workflows/pages.yml', group: 'Hub Workflows' },
  { path: '.github/workflows/ci.yml', group: 'Hub Workflows' },
  { path: 'site/index.html', group: 'Static Site (site/)' },
  { path: 'site/app.js', group: 'Static Site (site/)' },
  { path: 'sar/cli.py', group: 'sar Python Package' },
  { path: 'sar/validate.py', group: 'sar Python Package' },
  { path: 'sar/leaderboard.py', group: 'sar Python Package' },
  { path: 'sar/report.py', group: 'sar Python Package' },
  { path: 'sar/sync.py', group: 'sar Python Package' },
  { path: 'tests/e2e_dry_run.sh', group: 'Tests & E2E' },
];

function runCmd(cmd: string, args: string[], cwd: string): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    execFile(
      cmd,
      args,
      {
        cwd,
        timeout: 25000,
        env: { ...process.env, PYTHONPATH: __dirname, SAR_SORT_N: '25000' },
      },
      (err, stdout, stderr) => {
        const code = err && typeof (err as any).code === 'number' ? (err as any).code : err ? 1 : 0;
        resolve({ code, stdout: stdout || '', stderr: stderr || '' });
      }
    );
  });
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json({ limit: '1mb' }));

  // Serve generated/*.json and static site/ at /generated and /static-site
  app.use('/generated', express.static(path.join(__dirname, 'generated')));
  app.use('/static-site', express.static(path.join(__dirname, 'site')));

  app.get('/api/hub', (_req, res) => {
    try {
      const globalData = JSON.parse(
        fs.readFileSync(path.join(__dirname, 'generated', 'global.json'), 'utf-8')
      );
      const indexData = JSON.parse(
        fs.readFileSync(path.join(__dirname, 'generated', 'index.json'), 'utf-8')
      );
      const challengesDir = path.join(__dirname, 'generated', 'challenges');
      const details: Record<string, any> = {};
      if (fs.existsSync(challengesDir)) {
        for (const f of fs.readdirSync(challengesDir)) {
          if (f.endsWith('.json')) {
            const slug = f.replace(/\.json$/, '');
            details[slug] = JSON.parse(
              fs.readFileSync(path.join(challengesDir, f), 'utf-8')
            );
          }
        }
      }
      res.json({ global: globalData, index: indexData, details });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.get('/api/files', (req, res) => {
    const requestedPath = typeof req.query.path === 'string' ? req.query.path : 'donate.md';
    const allowed = CURATED_FILES.find((f) => f.path === requestedPath);
    const targetRel = allowed ? allowed.path : 'donate.md';
    const fullPath = path.join(__dirname, targetRel);
    try {
      const content = fs.readFileSync(fullPath, 'utf-8');
      res.json({
        files: CURATED_FILES,
        selected: targetRel,
        content,
      });
    } catch (err: any) {
      res.status(404).json({ error: err.message });
    }
  });

  app.post('/api/sar/action', async (req, res) => {
    const { action } = req.body || {};
    try {
      if (action === 'help') {
        const out = await runCmd('python3', ['-m', 'sar', '--help'], __dirname);
        return res.json(out);
      }
      if (action === 'sync') {
        const out = await runCmd('python3', ['-m', 'sar', 'sync', '--hub', '.'], __dirname);
        return res.json(out);
      }
      if (action === 'validate-registry') {
        const out = await runCmd('python3', ['-m', 'sar', 'validate', 'registry/3sum-exponent.toml', '--json'], __dirname);
        return res.json(out);
      }
      if (action === 'unit-tests') {
        const out = await runCmd('python3', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], __dirname);
        return res.json(out);
      }
      if (action === 'e2e-dry-run') {
        const out = await runCmd('bash', ['tests/e2e_dry_run.sh'], __dirname);
        return res.json(out);
      }
      if (action === 'claim-preview') {
        const out = await runCmd(
          'python3',
          ['-m', 'sar', 'claim', '--challenge', '3sum-exponent', '--track', 'derandomize', '--dry-run'],
          __dirname
        );
        return res.json(out);
      }
      if (action === 'attempt-preview') {
        const out = await runCmd(
          'python3',
          [
            '-m',
            'sar',
            'attempt',
            '--challenge',
            '3sum-exponent',
            '--track',
            'derandomize',
            '--result',
            'fail',
            '--body',
            'Tried replacing random pivot with deterministic median-of-medians; band bound degraded to n^2.',
            '--dry-run',
          ],
          __dirname
        );
        return res.json(out);
      }
      if (action === 'push-github') {
        const token = process.env.GITHUB_TOKEN?.trim();
        if (!token || token === 'MY_GITHUB_TOKEN') {
          return res.json({
            code: 1,
            stdout: '',
            stderr:
              'Missing GITHUB_TOKEN environment variable.\n\n' +
              'To push directly from AI Studio:\n' +
              '1. Click the GitHub icon ("Save to GitHub") in the top toolbar of AI Studio, select the "superautoresearch" organization, and name the repository "hub".\n' +
              'OR\n' +
              '2. Open the Secrets (key) panel in AI Studio, set GITHUB_TOKEN to a GitHub Personal Access Token with repo + workflow scopes for the superautoresearch org, and click "Push to superautoresearch/hub" again.',
          });
        }

        // 1. Check or create superautoresearch/hub via GitHub API
        const checkResp = await fetch('https://api.github.com/repos/superautoresearch/hub', {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/vnd.github+json',
            'User-Agent': 'superautoresearch-hub',
          },
        });

        const logs: string[] = [];
        if (checkResp.status === 404) {
          logs.push('Repository superautoresearch/hub not found; creating via GitHub REST API...');
          const createResp = await fetch('https://api.github.com/orgs/superautoresearch/repos', {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: 'application/vnd.github+json',
              'Content-Type': 'application/json',
              'User-Agent': 'superautoresearch-hub',
            },
            body: JSON.stringify({
              name: 'hub',
              description: 'superAutoResearch — GitHub-native open research challenge hub, templates, skills, and sar CLI',
              private: false,
              has_issues: true,
              has_projects: false,
              has_wiki: false,
            }),
          });
          if (!createResp.ok) {
            const errTxt = await createResp.text();
            return res.json({
              code: 1,
              stdout: logs.join('\n'),
              stderr: `Failed to create superautoresearch/hub (HTTP ${createResp.status}): ${errTxt}`,
            });
          }
          logs.push('Created https://github.com/superautoresearch/hub');
        } else if (checkResp.ok) {
          logs.push('Verified existing repository https://github.com/superautoresearch/hub');
        } else {
          const errTxt = await checkResp.text();
          return res.json({
            code: 1,
            stdout: '',
            stderr: `GitHub API check failed (HTTP ${checkResp.status}): ${errTxt}`,
          });
        }

        // 2. Push branch main to superautoresearch/hub
        const remoteUrl = `https://x-access-token:${token}@github.com/superautoresearch/hub.git`;
        await runCmd('git', ['add', '-A'], __dirname);
        await runCmd('git', ['commit', '-m', 'chore: update superAutoResearch hub'], __dirname);
        const pushOut = await runCmd('git', ['push', '-u', remoteUrl, 'main', '--force'], __dirname);
        const safeStderr = (pushOut.stderr || '').replaceAll(token, '***');
        const safeStdout = (pushOut.stdout || '').replaceAll(token, '***');
        return res.json({
          code: pushOut.code,
          stdout: [...logs, safeStdout, 'Pushed main to https://github.com/superautoresearch/hub'].filter(Boolean).join('\n'),
          stderr: safeStderr,
        });
      }
      res.status(400).json({ error: `Unknown action: ${action}` });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post('/api/sar/verify-sandbox', async (req, res) => {
    const { code, claimed = 0.01, author = 'alice', title = 'Custom Sort Submission' } = req.body || {};
    const tmpBase = fs.mkdtempSync(path.join(os.tmpdir(), 'sar-web-verify-'));
    try {
      await runCmd(
        'python3',
        ['-m', 'sar', 'new', 'sandbox-sort', '--type', 'script', '--dir', tmpBase, '--owner', author],
        __dirname
      );
      const chalDir = path.join(tmpBase, 'sandbox-sort');
      const subDir = path.join(chalDir, 'submissions', `${author}-custom`);
      fs.mkdirSync(subDir, { recursive: true });
      const subToml = [
        'schema = 1',
        `title = ${JSON.stringify(title)}`,
        `author = ${JSON.stringify(author)}`,
        `claimed = ${Number(claimed) || 0.01}`,
        'agent = "Claude Code"',
        'model = "claude-opus-5-5"',
        'description = "Interactive verifier test submission"',
      ].join('\n');
      fs.writeFileSync(path.join(subDir, 'submission.toml'), subToml, 'utf-8');
      fs.writeFileSync(path.join(subDir, 'solution.py'), String(code || ''), 'utf-8');

      const verifyOut = await runCmd(
        'python3',
        ['-m', 'sar', 'verify', subDir, '--no-docker', '--json'],
        chalDir
      );
      let parsed = null;
      try {
        parsed = JSON.parse(verifyOut.stdout);
      } catch (_) {}
      res.json({ ...verifyOut, parsed });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    } finally {
      fs.rmSync(tmpBase, { recursive: true, force: true });
    }
  });

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`superAutoResearch server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
