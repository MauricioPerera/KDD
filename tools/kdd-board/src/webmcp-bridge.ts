import { z } from 'zod';
import { registerTool, defineTool, type ToolSpec, type DefinedTool, type RegisterToolOptions } from 'fastwebmcp';
import type { TaskStore } from './task-store.ts';
import type { BlindVault } from './blind-vault.ts';
import type { TaskStatus } from './types.ts';
import { executeTaskTest } from './test-runner.ts';

export function createWebMcpBridge(taskStore: TaskStore, vault: BlindVault) {
  // 1. list_tasks
  const listTasksSpec = {
    name: 'list_tasks',
    description: 'Lista tareas del tablero Kanban con su estado, asignado y prioridad.',
    inputSchema: z.object({
      status: z.enum(['backlog', 'ready', 'in_progress', 'needs_human_input', 'done']).optional(),
    }),
    execute: async ({ status }: { status?: TaskStatus }) => {
      return taskStore.getAllTasks(status);
    },
    annotations: { readOnlyHint: true },
  };

  // 2. get_task
  const getTaskSpec = {
    name: 'get_task',
    description: 'Obtiene detalles completos de una tarea, incluyendo requerimientos pendientes e historial.',
    inputSchema: z.object({
      task_id: z.string().min(1),
    }),
    execute: async ({ task_id }: { task_id: string }) => {
      const task = taskStore.getTask(task_id);
      if (!task) throw new Error(`Tarea "${task_id}" no encontrada`);
      return task;
    },
    annotations: { readOnlyHint: true },
  };

  // 3. create_task
  const createTaskSpec = {
    name: 'create_task',
    description: 'Crea una nueva tarea en el Backlog del tablero.',
    inputSchema: z.object({
      title: z.string().min(1),
      description: z.string().default(''),
      assignee: z.enum(['human', 'agent', 'unassigned']).default('unassigned'),
      priority: z.enum(['low', 'medium', 'high', 'urgent']).default('medium'),
    }),
    execute: async ({ title, description, assignee, priority }: { title: string; description: string; assignee: 'human' | 'agent' | 'unassigned'; priority: 'low' | 'medium' | 'high' | 'urgent' }) => {
      return taskStore.createTask({ title, description, assignee, priority });
    },
  };

  // 4. update_task_status
  const updateTaskStatusSpec = {
    name: 'update_task_status',
    description: 'Mueve una tarea a una nueva columna del tablero Kanban y opcionalmente agrega un comentario.',
    inputSchema: z.object({
      task_id: z.string().min(1),
      status: z.enum(['backlog', 'ready', 'in_progress', 'needs_human_input', 'done']),
      comment: z.string().optional(),
    }),
    execute: async ({ task_id, status, comment }: { task_id: string; status: TaskStatus; comment?: string }) => {
      return taskStore.updateTaskStatus(
        task_id,
        status,
        comment ? { author: 'agent', text: comment } : undefined,
      );
    },
  };

  // 5. request_human_input (Blind credential or human response)
  const requestHumanInputSpec = {
    name: 'request_human_input',
    description: 'Solicita al humano una credencial ciega o dato de entrada, bloqueando la tarea en Needs Human Input.',
    inputSchema: z.object({
      task_id: z.string().min(1),
      field_key: z.string().min(1),
      label: z.string().min(1),
      description: z.string().min(1),
      is_secret: z.boolean().default(false),
    }),
    execute: async ({ task_id, field_key, label, description, is_secret }: { task_id: string; field_key: string; label: string; description: string; is_secret: boolean }) => {
      const task = taskStore.requestHumanInput(task_id, {
        fieldKey: field_key,
        label,
        description,
        isSecret: is_secret,
      });
      return {
        message: is_secret
          ? `Credencial "${field_key}" solicitada al humano mediante formulario seguro en el tablero.`
          : `Entrada "${field_key}" solicitada al humano en el tablero.`,
        task,
      };
    },
  };

  // 6. list_available_credentials (Blind listing)
  const listAvailableCredentialsSpec = {
    name: 'list_available_credentials',
    description: 'Lista las credenciales configuradas en el entorno local (nombres y estado, sin revelar texto plano).',
    inputSchema: z.object({}),
    execute: async () => {
      const secrets = vault.listSecrets();
      return {
        credentials: secrets,
        note: 'Las credenciales estan disponibles en el entorno local del proceso (ej. process.env.API_KEY). El agente puede invocarlas por nombre pero no leer su valor crudo.',
      };
    },
    annotations: { readOnlyHint: true },
  };

  // 7. run_task_tests
  const runTaskTestsSpec = {
    name: 'run_task_tests',
    description: 'Ejecuta la batería de pruebas de una tarea y registra el reporte de verificación con métricas.',
    inputSchema: z.object({
      task_id: z.string().min(1),
    }),
    execute: async ({ task_id }: { task_id: string }) => {
      const task = taskStore.getTask(task_id);
      if (!task) throw new Error(`Tarea "${task_id}" no encontrada`);
      const cmd = task.testCommand || 'npm test';
      const rootDir = process.cwd();
      const report = await executeTaskTest(cmd, rootDir);
      const updated = taskStore.recordTestReport(task_id, report);
      return {
        task: updated,
        report,
      };
    },
  };

  // 8. generate_kdd_report
  const generateKddReportSpec = {
    name: 'generate_kdd_report',
    description: 'Genera el archivo de evidencia y reporte KDD (.agents/logs/<task>-REPORT.md) con la salida real de los tests.',
    inputSchema: z.object({
      task_id: z.string().min(1),
    }),
    execute: async ({ task_id }: { task_id: string }) => {
      const task = taskStore.getTask(task_id);
      if (!task) throw new Error(`Tarea "${task_id}" no encontrada`);
      return taskStore.generateKddReport(task_id);
    },
  };

  const specs = [
    listTasksSpec,
    getTaskSpec,
    createTaskSpec,
    updateTaskStatusSpec,
    requestHumanInputSpec,
    listAvailableCredentialsSpec,
    runTaskTestsSpec,
    generateKddReportSpec,
  ];

  function registerAll(options?: RegisterToolOptions): boolean[] {
    return specs.map((s) => registerTool(s as any, options));
  }

  function getDefinedTools(): DefinedTool[] {
    return specs.map((s) => defineTool(s as any));
  }

  return {
    specs,
    registerAll,
    getDefinedTools,
    runTaskTestsSpec,
  };
}
