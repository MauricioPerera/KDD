import http from 'node:http';
import { z } from 'zod';
import { httpSchemas, InputError, statusSchema } from './input-validation.ts';
import crypto from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import { runTaskTests } from './task-execution.ts';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { TaskStore } from './task-store.ts';
import { BlindVault } from './blind-vault.ts';
import { createWebMcpBridge } from './webmcp-bridge.ts';
import { executeTaskTest } from './test-runner.ts';
import { GitTaskStore, isGitProject } from './git-task-store.ts';
import { createGitBridge } from './git-bridge.ts';
import { createGitApi } from './git-api.ts';
import type { TaskStatus, TaskAssignee, TaskPriority } from './types.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

// Target KDD project directory (CLI arg, env var, or auto-detected)
let projectDir = process.env.KDD_PROJECT_DIR || process.argv[2];
if (!projectDir) {
  if (fs.existsSync(path.join(process.cwd(), 'knowledge'))) {
    projectDir = process.cwd();
  } else if (fs.existsSync(path.join(rootDir, '..', '..', 'knowledge'))) {
    projectDir = path.resolve(rootDir, '..', '..');
  } else {
    projectDir = rootDir;
  }
}
projectDir = path.resolve(projectDir);

const dataDir = path.join(projectDir, '.kdd-board');
const tasksFile = path.join(dataDir, 'tasks.json');
const vaultFile = path.join(dataDir, 'vault.env');
const legacyVaultFile = path.join(projectDir, '.env.local');
const publicDir = path.join(rootDir, 'public');

const gitStore = isGitProject(projectDir) ? new GitTaskStore(projectDir) : undefined;
const taskStore = gitStore ? undefined : new TaskStore(tasksFile, key => Boolean(vault.getSecretValue(key)?.trim()));
const vault = new BlindVault(vaultFile, legacyVaultFile);
const bridge = gitStore ? createGitBridge(gitStore) : createWebMcpBridge(taskStore!, vault, projectDir);
const gitApi = gitStore ? createGitApi(gitStore, parseJsonBody, sendJson) : undefined;
const runGit = promisify(execFile);

class BoardRestartRequired extends Error {
  constructor() { super('El proyecto ahora usa Git; reinicia Board antes de modificarlo.'); }
}

function requireStableLegacyContext(): void {
  if (!gitStore && isGitProject(projectDir)) throw new BoardRestartRequired();
}

async function checkVaultExclusion(): Promise<'ok' | 'unprotected' | 'unavailable'> {
  try {
    if (!gitStore) return isGitProject(projectDir) ? 'unprotected' : 'ok';
    if (fs.existsSync(dataDir) && fs.lstatSync(dataDir).isSymbolicLink()) return 'unprotected';
    const env = {...process.env};
    delete env.KDD_BOARD_TOKEN;
    for (const key of Object.keys(env)) {
      if (['GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
           'GIT_CONFIG_COUNT', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_GLOBAL',
           'GIT_CONFIG_SYSTEM', 'GIT_CONFIG_NOSYSTEM'].includes(key) ||
          /^GIT_CONFIG_(KEY|VALUE)_\d+$/.test(key)) delete env[key];
    }
    for (const target of ['.kdd-board/', '.kdd-board/vault.env']) {
      await runGit('git', ['-C', projectDir, 'check-ignore', '-q', '--', target],
        {cwd:projectDir, env, timeout:10000, windowsHide:true});
    }
    return 'ok';
  } catch (error: any) {
    return error?.code === 1 ? 'unprotected' : 'unavailable';
  }
}

async function allowVaultWrite(res: http.ServerResponse): Promise<boolean> {
  const status = await checkVaultExclusion();
  if (status === 'ok') return true;
  if (status === 'unprotected') {
    sendJson(res, 409, {error: 'Excluye .kdd-board/ de Git y retira el vault del indice antes de guardar.', code: 'VAULT_GIT_EXCLUSION'});
  } else {
    sendJson(res, 503, {error: 'No se pudo comprobar la exclusion Git del vault.', code: 'VAULT_GIT_UNAVAILABLE'});
  }
  return false;
}

function parseJsonBody<T>(req: http.IncomingMessage, schema?: z.ZodType<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk: Buffer | string) => {
      body += chunk;
      if (Buffer.byteLength(body) > 1024 * 1024) { reject(new Error('Request body too large')); req.destroy(); }
    });
    req.on('end', () => {
      try {
        const parsed = body ? JSON.parse(body) : ({} as T);
        requireStableLegacyContext();
        resolve(schema ? schema.parse(parsed) : parsed);
      } catch (err) {
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res: http.ServerResponse, statusCode: number, data: unknown) {
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
  });
  res.end(JSON.stringify(data));
}

function serveStatic(res: http.ServerResponse, filePath: string, contentType: string) {
  if (!fs.existsSync(filePath)) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
    return;
  }
  res.writeHead(200, { 'Content-Type': contentType });
  fs.createReadStream(filePath).pipe(res);
}

interface DocItem {
  id: string;
  title: string;
  category: 'definition' | 'contracts-app' | 'spec';
  path: string;
  filename: string;
  isContract: boolean;
}

function getDocsCatalog(): DocItem[] {
  const docs: DocItem[] = [];

  // 0. Project Definition (DEFINITION.md - KDD Standard)
  const defCandidates = [
    path.join(projectDir, 'DEFINITION.md'),
    path.join(rootDir, 'DEFINITION.md'),
  ];
  for (const defPath of defCandidates) {
    if (fs.existsSync(defPath)) {
      docs.push({
        id: 'project-definition',
        title: '🎯 Definición del Proyecto (DEFINITION.md)',
        category: 'definition',
        path: defPath,
        filename: 'DEFINITION.md',
        isContract: false,
      });
      break;
    }
  }

  // 1. Contracts (in target project or kdd-board)
  const contractDirs = [
    path.join(projectDir, 'knowledge', 'contracts'),
    path.join(rootDir, 'knowledge', 'contracts'),
  ];

  const seenContracts = new Set<string>();
  for (const cDir of contractDirs) {
    if (fs.existsSync(cDir)) {
      for (const file of fs.readdirSync(cDir)) {
        if (file.endsWith('.md') && !seenContracts.has(file)) {
          seenContracts.add(file);
          const fullPath = path.join(cDir, file);
          docs.push({
            id: `app-${file}`,
            title: `Contrato: ${file.replace('.md', '')}`,
            category: 'contracts-app',
            path: fullPath,
            filename: file,
            isContract: true,
          });
        }
      }
    }
  }

  // 2. Specifications (OKF Standard & Architecture)
  const specFiles = [
    { name: 'OKF-SPEC.md', title: 'Especificación Normativa OKF' },
    { name: 'RESUMEN-EJECUTIVO.md', title: 'Resumen Ejecutivo KDD' },
  ];
  for (const s of specFiles) {
    const candidates = [
      path.join(projectDir, 'knowledge', s.name),
      path.join(rootDir, '..', 'knowledge', s.name),
      path.join(rootDir, 'knowledge', s.name),
    ];
    for (const fullPath of candidates) {
      if (fs.existsSync(fullPath)) {
        docs.push({
          id: `spec-${path.basename(s.name)}`,
          title: s.title,
          category: 'spec',
          path: fullPath,
          filename: path.basename(s.name),
          isContract: false,
        });
        break;
      }
    }
  }

  return docs;
}

function parseDocContent(filePath: string) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  let frontmatter: Record<string, any> | null = null;
  let body = raw;

  if (raw.startsWith('---')) {
    const endIdx = raw.indexOf('\n---', 3);
    if (endIdx !== -1) {
      const ymlStr = raw.substring(3, endIdx).trim();
      body = raw.substring(endIdx + 4).trim();
      frontmatter = {};
      for (const line of ymlStr.split('\n')) {
        const colonIdx = line.indexOf(':');
        if (colonIdx !== -1) {
          const k = line.substring(0, colonIdx).trim();
          const v = line.substring(colonIdx + 1).trim().replace(/^['"]|['"]$/g, '');
          frontmatter[k] = v;
        }
      }
    }
  }

  return { raw, body, frontmatter };
}

export function createServer(apiToken = process.env.KDD_BOARD_TOKEN || crypto.randomBytes(32).toString('hex')) {
  return http.createServer(async (req: http.IncomingMessage, res: http.ServerResponse) => {
    let url: URL;
    try { url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`); }
    catch { return sendJson(res, 400, {error: 'Invalid URL'}); }
    const pathname = url.pathname;

    const allowedHosts = new Set(['localhost', '127.0.0.1', '[::1]']);
    if (!allowedHosts.has(url.hostname)) return sendJson(res, 403, {error: 'Local host required'});
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    if (req.headers.origin && req.headers.origin !== url.origin) return sendJson(res, 403, {error: 'Origin rejected'});
    if (pathname.startsWith('/api/')) {
      const supplied = Buffer.from(req.headers.authorization || '');
      const expected = Buffer.from(`Bearer ${apiToken}`);
      if (supplied.length !== expected.length || !crypto.timingSafeEqual(supplied, expected)) {
        return sendJson(res, 401, {error: 'Open the authenticated URL printed by the launcher'});
      }
    }

    // Handle same-origin authenticated preflight
    if (req.method === 'OPTIONS') {
      res.writeHead(204, {
      });
      res.end();
      return;
    }

    try {
      // A server started in legacy mode must not keep writing JSON or secrets
      // after its project becomes a Git checkout. Restart to select Git mode.
      if (pathname.startsWith('/api/') && ['POST', 'PATCH', 'PUT', 'DELETE'].includes(req.method || '')) {
        requireStableLegacyContext();
      }
      if (gitApi && await gitApi(req, res, url)) return;
      if (req.method === 'GET' && pathname === '/api/board') {
        return sendJson(res, 200, {mode:'legacy', sourceRef:null});
      }
      // 1. GET /api/tasks
      if (req.method === 'GET' && pathname === '/api/tasks') {
        const rawStatus = url.searchParams.get('status');
        const status = rawStatus ? statusSchema.parse(rawStatus) : undefined;
        return sendJson(res, 200, taskStore!.getAllTasks(status || undefined));
      }

      // 2. POST /api/tasks
      if (req.method === 'POST' && pathname === '/api/tasks') {
        const body = await parseJsonBody(req, httpSchemas.task);
        if (body.priority !== undefined && !['low', 'medium', 'high', 'urgent'].includes(body.priority)) {
          return sendJson(res, 400, {error: 'Invalid priority'});
        }
        const task = taskStore!.createTask({
          title: body.title,
          description: body.description || '',
          assignee: body.assignee,
          priority: body.priority,
          contractId: body.contractId,
          testCommand: body.testCommand,
        });
        return sendJson(res, 201, task);
      }

      // 3. PATCH /api/tasks/:id/status
      const statusMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/status$/);
      if (req.method === 'PATCH' && statusMatch) {
        const taskId = statusMatch[1];
        const body = await parseJsonBody(req, httpSchemas.status);
        const task = taskStore!.updateTaskStatus(taskId, body.status, body.comment);
        return sendJson(res, 200, task);
      }

      // 4. PATCH /api/tasks/:id/assign
      const assignMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/assign$/);
      if (req.method === 'PATCH' && assignMatch) {
        const taskId = assignMatch[1];
        const body = await parseJsonBody(req, httpSchemas.assign);
        const task = taskStore!.assignTask(taskId, body.assignee);
        return sendJson(res, 200, task);
      }

      // 4.1 PATCH /api/tasks/:id/contract
      const contractMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/contract$/);
      if (req.method === 'PATCH' && contractMatch) {
        const taskId = contractMatch[1];
        const body = await parseJsonBody(req, httpSchemas.contract);
        const task = taskStore!.linkContract(taskId, body.contractId);
        return sendJson(res, 200, task);
      }

      // 5. POST /api/tasks/:id/requirements
      const reqMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/requirements$/);
      if (req.method === 'POST' && reqMatch) {
        const taskId = reqMatch[1];
        const body = await parseJsonBody(req, httpSchemas.requirement);
        const task = taskStore!.requestHumanInput(taskId, body);
        return sendJson(res, 200, task);
      }

      // 6. POST /api/tasks/:id/fulfill
      const fulfillMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/fulfill$/);
      if (req.method === 'POST' && fulfillMatch) {
        const taskId = fulfillMatch[1];
        const body = await parseJsonBody(req, httpSchemas.fulfill);

        const requirement = taskStore!.getTask(taskId)?.requirements.find(r => r.fieldKey === body.fieldKey);
        if (!requirement) throw new InputError('Unknown requirement');
        if (requirement.isSecret) {
          if (body.value !== undefined || (!body.secretValue && !vault.getSecretValue(body.fieldKey)?.trim())) throw new InputError('A saved credential is required');
          if (body.secretValue) {
            if (!await allowVaultWrite(res)) return;
            requireStableLegacyContext();
            vault.setSecret(body.fieldKey, body.secretValue);
          }
        } else if (!body.value?.trim() || body.secretValue !== undefined) {
          throw new InputError('A non-empty answer is required');
        }
        const task = taskStore!.satisfyHumanInput(taskId, body.fieldKey, body.value);
        return sendJson(res, 200, {
          task,
          vault: vault.listSecrets(),
        });
      }

      // 7. POST /api/tasks/:id/run-tests
      const testMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/run-tests$/);
      if (req.method === 'POST' && testMatch) {
        const taskId = testMatch[1];
        const task = taskStore!.getTask(taskId);
        if (!task) {
          return sendJson(res, 404, { error: `Tarea "${taskId}" no encontrada` });
        }
        return sendJson(res, 200, await runTaskTests(taskStore!, vault, projectDir, taskId));
      }

      // 7.1 POST /api/tasks/:id/report (Generate .agents/logs/<TASK>-REPORT.md)
      const reportMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/report$/);
      if (req.method === 'POST' && reportMatch) {
        const taskId = reportMatch[1];
        try {
          const generated = taskStore!.generateKddReport(taskId);
          return sendJson(res, 200, {
            success: true,
            ...generated,
            task: taskStore!.getTask(taskId),
          });
        } catch (err: any) {
          return sendJson(res, 404, { error: err.message });
        }
      }

      // 8. GET /api/vault
      if (req.method === 'GET' && pathname === '/api/vault') {
        return sendJson(res, 200, vault.listSecrets());
      }

      // 8. POST /api/vault (Add or modify secret)
      if (req.method === 'POST' && pathname === '/api/vault') {
        const body = await parseJsonBody(req, httpSchemas.vault);
        if (!body.key || !body.value) {
          return sendJson(res, 400, { error: 'Clave y valor requeridos' });
        }
        if (!await allowVaultWrite(res)) return;
        requireStableLegacyContext();
        vault.setSecret(body.key, body.value);
        const sanitized = body.key.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
        
        // Auto-satisfy any task waiting for this credential
        const allTasks = taskStore?.getAllTasks() || [];
        for (const t of allTasks) {
          const req = t.requirements?.find((r) => r.isSecret && !r.isSatisfied && r.fieldKey.toUpperCase() === sanitized);
          if (req) {
            taskStore!.satisfyHumanInput(t.id, req.fieldKey);
          }
        }

        return sendJson(res, 200, vault.listSecrets());
      }

      // 9. DELETE /api/vault/:key
      const vaultDelMatch = pathname.match(/^\/api\/vault\/([^/]+)$/);
      if (req.method === 'DELETE' && vaultDelMatch) {
        const key = decodeURIComponent(vaultDelMatch[1]);
        if (!await allowVaultWrite(res)) return;
        requireStableLegacyContext();
        vault.deleteSecret(key);
        return sendJson(res, 200, vault.listSecrets());
      }

      // 10. GET /api/tools
      if (req.method === 'GET' && pathname === '/api/tools') {
        const defined = bridge.getDefinedTools();
        return sendJson(res, 200, defined.map((t) => ({
          name: t.name,
          description: t.description,
          inputSchema: t.inputSchema,
        })));
      }

      // 11. GET /api/docs
      if (req.method === 'GET' && pathname === '/api/docs') {
        const catalog = getDocsCatalog();
        return sendJson(res, 200, catalog);
      }

      // 12. GET /api/docs/item?id=...
      if (req.method === 'GET' && pathname === '/api/docs/item') {
        const docId = url.searchParams.get('id');
        const catalog = getDocsCatalog();
        const item = catalog.find((d) => d.id === docId);
        if (!item) {
          return sendJson(res, 404, { error: 'Documento no encontrado' });
        }
        const { raw, body, frontmatter } = parseDocContent(item.path);
        return sendJson(res, 200, {
          item,
          raw,
          body,
          frontmatter,
        });
      }

      // 13. POST /api/docs/validate
      if (req.method === 'POST' && pathname === '/api/docs/validate') {
        let cmd = 'python scripts/validate_contracts.py knowledge/contracts';
        let execDir = projectDir;
        if (!fs.existsSync(path.join(projectDir, 'scripts', 'validate_contracts.py'))) {
          return sendJson(res, 400, {error: 'Project has no KDD validator; use a KDD project'});
        }
        const report = await executeTaskTest(cmd, execDir);

        return sendJson(res, 200, {
          success: report.success,
          output: `=== CONTRATOS DEL PROYECTO (${path.basename(execDir)}) ===\n${report.output}`,
        });
      }

      // Static files
      if (pathname === '/' || pathname === '/index.html') {
        return serveStatic(res, path.join(publicDir, 'index.html'), 'text/html; charset=utf-8');
      }
      if (pathname === '/app.js') {
        return serveStatic(res, path.join(publicDir, 'app.js'), 'application/javascript; charset=utf-8');
      }
      if (pathname === '/git-board.js') {
        return serveStatic(res, path.join(publicDir, 'git-board.js'), 'application/javascript; charset=utf-8');
      }
      if (pathname === '/style.css') {
        return serveStatic(res, path.join(publicDir, 'style.css'), 'text/css; charset=utf-8');
      }

      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    } catch (err: any) {
      if (err instanceof BoardRestartRequired) {
        return sendJson(res, 409, {error:err.message, code:'BOARD_RESTART_REQUIRED'});
      }
      if (err instanceof z.ZodError || err instanceof SyntaxError || err instanceof InputError) return sendJson(res, 400, {error: 'Invalid request or unsatisfied requirement'});
      sendJson(res, 500, { error: err?.message || 'Internal Server Error' });
    }
  });
}

// Start server if executed directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const PORT = Number(process.env.PORT) || 3456;
  const token = process.env.KDD_BOARD_TOKEN || crypto.randomBytes(32).toString('hex');
  const server = createServer(token);
  server.listen(PORT, '127.0.0.1', () => {
    console.log(`\n======================================================`);
    console.log(`🚀 KDD-Board escuchando en http://127.0.0.1:${PORT}/#token=${encodeURIComponent(token)}`);
    console.log(`🤖 Soporte WebMCP activo con fastwebmcp`);
    console.log(`🔒 Vault local activo (no aisla codigo hostil)`);
    console.log(`======================================================\n`);
  });
}
