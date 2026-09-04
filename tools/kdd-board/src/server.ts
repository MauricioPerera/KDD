import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { TaskStore } from './task-store.ts';
import { BlindVault } from './blind-vault.ts';
import { createWebMcpBridge } from './webmcp-bridge.ts';
import { executeTaskTest } from './test-runner.ts';
import type { TaskStatus, TaskAssignee, TaskPriority } from './types.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

// Target KDD project directory (CLI arg, env var, or auto-detected)
let projectDir = process.env.KDD_PROJECT_DIR || process.argv[2];
if (!projectDir) {
  if (fs.existsSync(path.join(process.cwd(), 'knowledge'))) {
    projectDir = process.cwd();
  } else if (fs.existsSync(path.join(rootDir, '..', 'knowledge'))) {
    projectDir = path.resolve(rootDir, '..');
  } else {
    projectDir = rootDir;
  }
}
projectDir = path.resolve(projectDir);

const dataDir = path.join(rootDir, 'data');
const tasksFile = path.join(dataDir, 'tasks.json');
const vaultFile = path.join(projectDir, '.env.local');
const publicDir = path.join(rootDir, 'public');

const taskStore = new TaskStore(tasksFile);
const vault = new BlindVault(vaultFile);
const bridge = createWebMcpBridge(taskStore, vault);

// Populate default sample tasks if store is empty
if (taskStore.getAllTasks().length === 0) {
  const t1 = taskStore.createTask({
    title: 'Definir especificación KDD del pipeline de datos',
    description: 'Crear contrato con invariantes y budgets para el ingestor.',
    assignee: 'human',
    priority: 'high',
  });
  taskStore.updateTaskStatus(t1.id, 'ready');

  const t2 = taskStore.createTask({
    title: 'Generar parser de eventos con Zod y fastwebmcp',
    description: 'Implementar validación estricta y esquemas declarativos.',
    assignee: 'agent',
    priority: 'high',
  });
  taskStore.updateTaskStatus(t2.id, 'in_progress');
  taskStore.requestHumanInput(t2.id, {
    fieldKey: 'DATABASE_URL',
    label: 'URL de Base de Datos PostgreSQL',
    description: 'Cadena de conexión para pruebas de integración local',
    isSecret: true,
  });

  const t3 = taskStore.createTask({
    title: 'Refactorizar suite de pruebas unitarias',
    description: 'Asegurar cobertura >90% en la máquina de estados.',
    assignee: 'unassigned',
    priority: 'medium',
  });
}

function parseJsonBody<T>(req: http.IncomingMessage): Promise<T> {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk: Buffer | string) => (body += chunk));
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : ({} as T));
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
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
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

export function createServer() {
  return http.createServer(async (req: http.IncomingMessage, res: http.ServerResponse) => {
    const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    const pathname = url.pathname;

    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
      res.writeHead(204, {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      });
      res.end();
      return;
    }

    try {
      // 1. GET /api/tasks
      if (req.method === 'GET' && pathname === '/api/tasks') {
        const status = url.searchParams.get('status') as TaskStatus | null;
        return sendJson(res, 200, taskStore.getAllTasks(status || undefined));
      }

      // 2. POST /api/tasks
      if (req.method === 'POST' && pathname === '/api/tasks') {
        const body = await parseJsonBody<{
          title: string;
          description?: string;
          assignee?: TaskAssignee;
          priority?: TaskPriority;
          contractId?: string;
          testCommand?: string;
        }>(req);
        const task = taskStore.createTask({
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
        const body = await parseJsonBody<{
          status: TaskStatus;
          comment?: { author: 'human' | 'agent' | 'system'; text: string };
        }>(req);
        const task = taskStore.updateTaskStatus(taskId, body.status, body.comment);
        return sendJson(res, 200, task);
      }

      // 4. PATCH /api/tasks/:id/assign
      const assignMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/assign$/);
      if (req.method === 'PATCH' && assignMatch) {
        const taskId = assignMatch[1];
        const body = await parseJsonBody<{ assignee: TaskAssignee }>(req);
        const task = taskStore.assignTask(taskId, body.assignee);
        return sendJson(res, 200, task);
      }

      // 4.1 PATCH /api/tasks/:id/contract
      const contractMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/contract$/);
      if (req.method === 'PATCH' && contractMatch) {
        const taskId = contractMatch[1];
        const body = await parseJsonBody<{ contractId?: string }>(req);
        const task = taskStore.linkContract(taskId, body.contractId);
        return sendJson(res, 200, task);
      }

      // 5. POST /api/tasks/:id/requirements
      const reqMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/requirements$/);
      if (req.method === 'POST' && reqMatch) {
        const taskId = reqMatch[1];
        const body = await parseJsonBody<{
          fieldKey: string;
          label: string;
          description: string;
          isSecret?: boolean;
        }>(req);
        const task = taskStore.requestHumanInput(taskId, body);
        return sendJson(res, 200, task);
      }

      // 6. POST /api/tasks/:id/fulfill
      const fulfillMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/fulfill$/);
      if (req.method === 'POST' && fulfillMatch) {
        const taskId = fulfillMatch[1];
        const body = await parseJsonBody<{
          fieldKey: string;
          value?: string;
          secretValue?: string;
        }>(req);

        if (body.secretValue) {
          vault.setSecret(body.fieldKey, body.secretValue);
        }
        const task = taskStore.satisfyHumanInput(taskId, body.fieldKey, body.value);
        return sendJson(res, 200, {
          task,
          vault: vault.listSecrets(),
        });
      }

      // 7. POST /api/tasks/:id/run-tests
      const testMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/run-tests$/);
      if (req.method === 'POST' && testMatch) {
        const taskId = testMatch[1];
        const task = taskStore.getTask(taskId);
        if (!task) {
          return sendJson(res, 404, { error: `Tarea "${taskId}" no encontrada` });
        }
        const cmd = task.testCommand || 'npm test';
        const report = await executeTaskTest(cmd, rootDir);
        const updated = taskStore.recordTestReport(taskId, report);
        return sendJson(res, 200, {
          task: updated,
          report,
        });
      }

      // 7.1 POST /api/tasks/:id/report (Generate .agents/logs/<TASK>-REPORT.md)
      const reportMatch = pathname.match(/^\/api\/tasks\/([^/]+)\/report$/);
      if (req.method === 'POST' && reportMatch) {
        const taskId = reportMatch[1];
        try {
          const generated = taskStore.generateKddReport(taskId);
          return sendJson(res, 200, {
            success: true,
            ...generated,
            task: taskStore.getTask(taskId),
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
        const body = await parseJsonBody<{ key: string; value: string }>(req);
        if (!body.key || !body.value) {
          return sendJson(res, 400, { error: 'Clave y valor requeridos' });
        }
        vault.setSecret(body.key, body.value);
        const sanitized = body.key.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
        
        // Auto-satisfy any task waiting for this credential
        const allTasks = taskStore.getAllTasks();
        for (const t of allTasks) {
          const req = t.requirements?.find((r) => !r.isSatisfied && r.fieldKey.toUpperCase() === sanitized);
          if (req) {
            taskStore.satisfyHumanInput(t.id, req.fieldKey);
          }
        }

        return sendJson(res, 200, vault.listSecrets());
      }

      // 9. DELETE /api/vault/:key
      const vaultDelMatch = pathname.match(/^\/api\/vault\/([^/]+)$/);
      if (req.method === 'DELETE' && vaultDelMatch) {
        const key = decodeURIComponent(vaultDelMatch[1]);
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
          cmd = 'python scripts/validate_contracts.py kdd-board/knowledge/contracts';
          execDir = path.resolve(rootDir, '..');
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
      if (pathname === '/style.css') {
        return serveStatic(res, path.join(publicDir, 'style.css'), 'text/css; charset=utf-8');
      }

      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    } catch (err: any) {
      sendJson(res, 500, { error: err?.message || 'Internal Server Error' });
    }
  });
}

// Start server if executed directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const PORT = Number(process.env.PORT) || 3456;
  const server = createServer();
  server.listen(PORT, () => {
    console.log(`\n======================================================`);
    console.log(`🚀 KDD-Board escuchando en http://localhost:${PORT}`);
    console.log(`🤖 Soporte WebMCP activo con fastwebmcp`);
    console.log(`🔒 Blind Secrets Vault activo en data/.env.local`);
    console.log(`======================================================\n`);
  });
}
