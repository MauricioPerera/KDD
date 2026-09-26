import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { BlindVault } from '../src/blind-vault.ts';

test('BlindVault never reveals secret fragments and creates owner-only files on POSIX', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-vault-security-'));
  const vaultPath = path.join(root, '.env.local');
  try {
    const vault = new BlindVault(vaultPath);
    vault.setSecret('API_KEY', 'super-secret-value-12345');
    assert.equal(vault.maskSecret('super-secret-value-12345'), '***');
    if (process.platform !== 'win32') {
      assert.equal(fs.statSync(vaultPath).mode & 0o777, 0o600);
    }
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('the browser registers every HTTP-backed WebMCP tool and safely encodes handler arguments', async () => {
  const nodes = new Map<string, any>();
  const registered: any[] = [];
  const getNode = (id: string) => {
    if (!nodes.has(id)) nodes.set(id, {
      innerHTML: '', value: '', textContent: '', dataset: {}, style: {},
      classList: { add(){}, remove(){}, toggle(){} }, addEventListener(){}, appendChild(){},
    });
    return nodes.get(id);
  };
  const toolNames = [
    'list_tasks', 'get_task', 'create_task', 'update_task_status',
    'request_human_input', 'list_available_credentials', 'run_task_tests',
    'generate_kdd_report',
  ];
  const context = vm.createContext({
    document: {
      getElementById: getNode,
      querySelectorAll: () => [],
      addEventListener(){},
      modelContext: { registerTool: (tool: any) => registered.push(tool) },
    },
    location: { hash: '', pathname: '/', search: '' },
    sessionStorage: { getItem: () => 'test-token', setItem(){} },
    URLSearchParams, Headers, console, setInterval: () => 0,
    fetch: async (url: string) => ({
      ok: true,
      json: async () => url === '/api/tools'
        ? toolNames.map((name) => ({ name, description: name, inputSchema: { type: 'object' } }))
        : [],
    }),
  });
  context.window = context;
  const app = fs.readFileSync(new URL('../public/app.js', import.meta.url), 'utf8');
  vm.runInContext(app, context);
  await vm.runInContext('registerWebMcpTools()', context);
  assert.deepEqual(registered.map((tool) => tool.name).sort(), [...toolNames].sort());
  const encoded = vm.runInContext("escapeJsArgument(\"contract');alert(1);//\")", context);
  assert.equal(encoded.includes("'"), false);
  assert.equal(decodeURIComponent(encoded), "contract');alert(1);//");
});
