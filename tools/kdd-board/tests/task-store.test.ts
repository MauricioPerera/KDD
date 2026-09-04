import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { TaskStore } from '../src/task-store.ts';

test('TaskStore: ciclo completo de creación, asignación y transición de estados', () => {
  const tmpFile = path.join(os.tmpdir(), `test-tasks-${Date.now()}.json`);
  try {
    const store = new TaskStore(tmpFile);

    // 1. Crear tarea
    const task = store.createTask({
      title: 'Implementar autenticación OAuth',
      description: 'Integrar login con GitHub',
      priority: 'high',
    });

    assert.equal(task.title, 'Implementar autenticación OAuth');
    assert.equal(task.status, 'backlog');
    assert.equal(task.assignee, 'unassigned');
    assert.equal(task.priority, 'high');

    // 2. Asignar al Agente y mover a Ready
    store.assignTask(task.id, 'agent');
    store.updateTaskStatus(task.id, 'ready', {
      author: 'human',
      text: 'Tarea lista para que el agente la tome.',
    });

    let updated = store.getTask(task.id)!;
    assert.equal(updated.status, 'ready');
    assert.equal(updated.assignee, 'agent');

    // 3. El Agente solicita credencial (pasa a needs_human_input y se asigna al Humano)
    store.requestHumanInput(task.id, {
      fieldKey: 'GITHUB_CLIENT_SECRET',
      label: 'GitHub Client Secret',
      description: 'Necesario para la autenticación OAuth',
      isSecret: true,
    });

    updated = store.getTask(task.id)!;
    assert.equal(updated.status, 'needs_human_input');
    assert.equal(updated.assignee, 'human');
    assert.equal(updated.requirements.length, 1);
    assert.equal(updated.requirements[0].isSatisfied, false);

    // 4. El Humano suministra la credencial -> se satisface y la tarea vuelve a Ready para el Agente
    store.satisfyHumanInput(task.id, 'GITHUB_CLIENT_SECRET');

    updated = store.getTask(task.id)!;
    assert.equal(updated.requirements[0].isSatisfied, true);
    assert.equal(updated.status, 'ready');
    assert.equal(updated.assignee, 'agent');

    // 5. El Agente trabaja y la completa
    store.updateTaskStatus(task.id, 'in_progress', {
      author: 'agent',
      text: 'Iniciando implementación con la credencial cargada.',
    });
    store.updateTaskStatus(task.id, 'done', {
      author: 'agent',
      text: 'Implementación finalizada y testeada.',
    });

    updated = store.getTask(task.id)!;
    assert.equal(updated.status, 'done');
    assert.ok(updated.comments.length >= 4);
  } finally {
    if (fs.existsSync(tmpFile)) {
      fs.unlinkSync(tmpFile);
    }
  }
});
