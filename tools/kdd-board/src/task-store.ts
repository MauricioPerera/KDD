import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import type { Task, TaskStatus, TaskAssignee, TaskPriority, HumanInputRequirement, TaskComment, TaskTestReport } from './types.ts';

export class TaskStore {
  private filePath: string;
  private tasks: Map<string, Task> = new Map();

  constructor(filePath: string) {
    this.filePath = filePath;
    this.load();
  }

  private load(): void {
    if (!fs.existsSync(this.filePath)) {
      return;
    }
    try {
      const data = fs.readFileSync(this.filePath, 'utf-8');
      const list: Task[] = JSON.parse(data);
      for (const t of list) {
        this.tasks.set(t.id, t);
      }
    } catch {
      // Ignore initial parse errors on empty or corrupted file
    }
  }

  private save(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const list = Array.from(this.tasks.values());
    fs.writeFileSync(this.filePath, JSON.stringify(list, null, 2), 'utf-8');
  }

  public getAllTasks(status?: TaskStatus): Task[] {
    this.load();
    const all = Array.from(this.tasks.values()).sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
    if (!status) return all;
    return all.filter((t) => t.status === status);
  }

  public getTask(id: string): Task | undefined {
    this.load();
    return this.tasks.get(id);
  }

  public createTask(params: {
    title: string;
    description: string;
    assignee?: TaskAssignee;
    priority?: TaskPriority;
    testCommand?: string;
    contractId?: string;
  }): Task {
    if (!params.title || params.title.trim() === '') {
      throw new Error('TaskStore: title must be a non-empty string');
    }
    const now = new Date().toISOString();
    const id = `task-${crypto.randomBytes(4).toString('hex')}`;
    const task: Task = {
      id,
      title: params.title.trim(),
      description: params.description?.trim() ?? '',
      status: 'backlog',
      assignee: params.assignee ?? 'unassigned',
      priority: params.priority ?? 'medium',
      contractId: params.contractId,
      testCommand: params.testCommand || 'npm test',
      requirements: [],
      comments: [
        {
          id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
          author: 'system',
          text: 'Tarea creada en Backlog.',
          timestamp: now,
        },
      ],
      createdAt: now,
      updatedAt: now,
    };
    this.tasks.set(id, task);
    this.save();
    return task;
  }

  public updateTaskStatus(
    id: string,
    newStatus: TaskStatus,
    comment?: { author: 'human' | 'agent' | 'system'; text: string }
  ): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    task.status = newStatus;
    task.updatedAt = new Date().toISOString();
    if (comment) {
      task.comments.push({
        id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
        author: comment.author,
        text: comment.text,
        timestamp: task.updatedAt,
      });
    }
    this.save();
    return task;
  }

  public assignTask(id: string, assignee: TaskAssignee): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    task.assignee = assignee;
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author: 'system',
      text: `Tarea asignada a: ${assignee}.`,
      timestamp: task.updatedAt,
    });
    this.save();
    return task;
  }

  public requestHumanInput(
    id: string,
    requirement: {
      fieldKey: string;
      label: string;
      description: string;
      isSecret?: boolean;
    }
  ): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    const key = requirement.fieldKey.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    const existingIdx = task.requirements.findIndex((r) => r.fieldKey === key);
    const req: HumanInputRequirement = {
      fieldKey: key,
      label: requirement.label || key,
      description: requirement.description || '',
      isSecret: requirement.isSecret ?? false,
      isSatisfied: false,
    };
    if (existingIdx >= 0) {
      task.requirements[existingIdx] = req;
    } else {
      task.requirements.push(req);
    }
    task.status = 'needs_human_input';
    task.assignee = 'human';
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author: 'agent',
      text: `Se requiere acción humana: ${req.label} (${req.description}).`,
      timestamp: task.updatedAt,
    });
    this.save();
    return task;
  }

  public satisfyHumanInput(taskId: string, fieldKey: string, value?: string): Task {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`TaskStore: task with id "${taskId}" not found`);
    }
    const key = fieldKey.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    const req = task.requirements.find((r) => r.fieldKey === key);
    if (!req) {
      throw new Error(`TaskStore: requirement "${key}" not found in task "${taskId}"`);
    }
    req.isSatisfied = true;
    if (!req.isSecret && value !== undefined) {
      req.value = value;
    }
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author: 'human',
      text: `Requerimiento completado: ${req.label}.`,
      timestamp: task.updatedAt,
    });
    // Check if all requirements are satisfied
    const allSatisfied = task.requirements.every((r) => r.isSatisfied);
    if (allSatisfied) {
      task.status = 'ready';
      task.assignee = 'agent';
      task.comments.push({
        id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
        author: 'system',
        text: `Todos los requerimientos fueron completados. Tarea reasignada a Agent en Ready.`,
        timestamp: task.updatedAt,
      });
    }
    this.save();
    return task;
  }

  public addComment(id: string, author: 'human' | 'agent' | 'system', text: string): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author,
      text,
      timestamp: task.updatedAt,
    });
    this.save();
    return task;
  }

  public recordTestReport(id: string, report: TaskTestReport): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    task.testReport = report;
    task.metrics = {
      requirementsCount: task.requirements.length,
      satisfiedCount: task.requirements.filter((r) => r.isSatisfied).length,
      commentsCount: task.comments.length + 1,
      lastRunDurationMs: report.durationMs,
    };
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author: 'system',
      text: report.success
        ? `Batería de tests EXITOSA (${report.passedTests} pasados en ${report.durationMs.toFixed(1)}ms).`
        : `Batería de tests FALLIDA (${report.failedTests} fallados, ${report.passedTests} pasados).`,
      timestamp: task.updatedAt,
    });
    this.save();
    return task;
  }

  public setTestCommand(id: string, command: string): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    task.testCommand = command;
    task.updatedAt = new Date().toISOString();
    this.save();
    return task;
  }

  public linkContract(id: string, contractId?: string): Task {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    task.contractId = contractId;
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author: 'system',
      text: contractId ? `Contrato KDD vinculado: ${contractId}` : 'Contrato KDD desvinculado.',
      timestamp: task.updatedAt,
    });
    this.save();
    return task;
  }

  public generateKddReport(id: string): { filePath: string; relativePath: string; content: string } {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }

    const slug =
      task.title
        .toUpperCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^A-Z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || task.id.toUpperCase();

    const parentDir = path.resolve(path.dirname(this.filePath), '..');
    const logsDir = path.join(parentDir, '.agents', 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }

    const filename = `${slug}-REPORT.md`;
    const filePath = path.join(logsDir, filename);
    const relativePath = `.agents/logs/${filename}`;

    const dateStr = new Date().toISOString().split('T')[0];
    const reportContent = `# ${slug}-REPORT — ${task.title} (KDD / CCDD gate)

**Fecha:** ${dateStr}
**Tarea ID:** \`${task.id}\`
**Asignado a:** ${task.assignee}
**Contrato KDD:** ${task.contractId ? `\`${task.contractId}\`` : 'N/A'}
**Estado del Tablero:** \`${task.status}\`

## Resumen
${task.description || 'Sin descripción adicional.'}

### Métricas de Verificación
- **Resultado:** ${task.testReport?.success ? 'PASS ✓' : 'FAIL ✖'}
- **Tests Pasados:** ${task.testReport?.passedTests ?? 0}
- **Tests Fallados:** ${task.testReport?.failedTests ?? 0}
- **Duración:** ${task.testReport?.durationMs ? `${task.testReport.durationMs.toFixed(1)}ms` : 'N/A'}
- **Requerimientos Satisfechos:** ${task.requirements.filter((r) => r.isSatisfied).length}/${task.requirements.length}

---

## DEFINICIÓN DE HECHO — Salida REAL de los Comandos

### Comando Oráculo: \`${task.testCommand || 'npm test'}\`

\`\`\`
${task.testReport?.output || 'No se ha ejecutado batería de tests aún.'}
\`\`\`

### Historial de Auditoría
${task.comments.map((c) => `- [${c.timestamp}] **${c.author.toUpperCase()}**: ${c.text}`).join('\n')}
`;

    fs.writeFileSync(filePath, reportContent, 'utf-8');

    if (task.testReport) {
      task.testReport.reportPath = relativePath;
    }
    task.updatedAt = new Date().toISOString();
    task.comments.push({
      id: `cmt-${crypto.randomBytes(3).toString('hex')}`,
      author: 'system',
      text: `Reporte KDD generado exitosamente: ${relativePath}`,
      timestamp: task.updatedAt,
    });
    this.save();

    return {
      filePath,
      relativePath,
      content: reportContent,
    };
  }

  public deleteTask(id: string): boolean {
    const deleted = this.tasks.delete(id);
    if (deleted) {
      this.save();
    }
    return deleted;
  }
}
