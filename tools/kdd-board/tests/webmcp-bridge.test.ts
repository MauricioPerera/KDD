import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createWebMcpMock, withMockDocument } from 'fastwebmcp';
import { TaskStore } from '../src/task-store.ts';
import { BlindVault } from '../src/blind-vault.ts';
import { createWebMcpBridge } from '../src/webmcp-bridge.ts';

test('createWebMcpBridge: flujo WebMCP de extremo a extremo con mock', async () => {
  const tmpTasks = path.join(os.tmpdir(), `bridge-tasks-${Date.now()}.json`);
  const tmpVault = path.join(os.tmpdir(), `bridge-vault-${Date.now()}.env`);

  try {
    const taskStore = new TaskStore(tmpTasks);
    const vault = new BlindVault(tmpVault);
    const bridge = createWebMcpBridge(taskStore, vault);
    const mock = createWebMcpMock();

    await withMockDocument(mock, async () => {
      // 1. Registrar todas las tools en el mock de WebMCP
      const registrationResults = bridge.registerAll();
      assert.equal(registrationResults.every(Boolean), true);
      assert.equal(mock.registeredTools.size, 8);

      // 2. Agente invoca "create_task"
      const created = (await mock.invokeTool('create_task', {
        title: 'Entrenar modelo de embeddings',
        description: 'Requiere HuggingFace API Token',
        assignee: 'agent',
        priority: 'high',
      })) as any;

      assert.ok(created.id);
      assert.equal(created.title, 'Entrenar modelo de embeddings');
      assert.equal(created.status, 'backlog');

      // 3. Agente mueve la tarea a "in_progress"
      const progressTask = (await mock.invokeTool('update_task_status', {
        task_id: created.id,
        status: 'in_progress',
        comment: 'Comenzando preparación de dataset.',
      })) as any;
      assert.equal(progressTask.status, 'in_progress');

      // 4. Agente solicita credencial ciega al humano (HF_TOKEN)
      const inputResult = (await mock.invokeTool('request_human_input', {
        task_id: created.id,
        field_key: 'HF_TOKEN',
        label: 'Hugging Face API Token',
        description: 'Token de acceso de lectura a HuggingFace',
        is_secret: true,
      })) as any;

      assert.equal(inputResult.task.status, 'needs_human_input');
      assert.equal(inputResult.task.assignee, 'human');

      // 5. El humano completa la credencial en el servidor / UI
      vault.setSecret('HF_TOKEN', 'hf_live_secretToken9988776655');
      taskStore.satisfyHumanInput(created.id, 'HF_TOKEN');

      // 6. El agente invoca "list_available_credentials"
      const credsResult = (await mock.invokeTool('list_available_credentials', {})) as any;
      const hfSecret = credsResult.credentials.find((c: any) => c.key === 'HF_TOKEN');
      assert.ok(hfSecret);
      assert.equal(hfSecret.isSet, true);
      // Blind security: nunca expone el token en texto plano al agente
      assert.equal(hfSecret.maskedValue.includes('hf_live_secretToken'), false);
      assert.equal(hfSecret.maskedValue.includes('***'), true);

      // 7. La tarea vuelve a estar lista para el agente
      const readyTask = (await mock.invokeTool('get_task', { task_id: created.id })) as any;
      assert.equal(readyTask.status, 'ready');
      assert.equal(readyTask.assignee, 'agent');

      // 8. El agente ejecuta la batería de tests de la tarea
      const testRunResult = (await mock.invokeTool('run_task_tests', { task_id: created.id })) as any;
      assert.ok(testRunResult.report);
      assert.equal(testRunResult.report.success, true);
      assert.ok(testRunResult.report.passedTests >= 1);
      assert.equal(testRunResult.task.metrics.requirementsCount, 1);
      assert.equal(testRunResult.task.metrics.satisfiedCount, 1);

      // 9. El agente genera el reporte KDD formal
      const reportRes = (await mock.invokeTool('generate_kdd_report', { task_id: created.id })) as any;
      assert.ok(reportRes.filePath);
      assert.ok(reportRes.relativePath.startsWith('.agents/logs/'));
      assert.equal(fs.existsSync(reportRes.filePath), true);
      if (fs.existsSync(reportRes.filePath)) fs.unlinkSync(reportRes.filePath);
    });
  } finally {
    if (fs.existsSync(tmpTasks)) fs.unlinkSync(tmpTasks);
    if (fs.existsSync(tmpVault)) fs.unlinkSync(tmpVault);
  }
});
