import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { assigneeSchema, taskInputSchema, requirementInputSchema, fieldKeySchema, storedTasksSchema, InputError } from './input-validation.ts';
import { evidenceCurrent } from './task-execution.ts';
import { readVersion, writeVersion } from './persistence.ts';
import type { Task, TaskStatus, TaskAssignee, TaskPriority, HumanInputRequirement, TaskComment, TaskTestReport } from './types.ts';

export class TaskStore {
  private filePath: string;
  private version: string | null = null;
  private tasks: Map<string, Task> = new Map();
  private legacyTasks: Map<string, Task> = new Map();
  private secretAvailable: (key: string) => boolean;

  constructor(filePath: string, secretAvailable: (key: string) => boolean = () => false) {
    this.filePath = filePath;
    this.secretAvailable = secretAvailable;
    this.load();
  }

  private load(): void {
    const version = readVersion(this.filePath);
    if (version === null) {
      this.version = null;
      this.tasks.clear();
      this.legacyTasks.clear();
      return;
    }
    try {
      const data = version;
      const original = JSON.parse(data);
      const list: Task[] = storedTasksSchema.parse(original);
      if (!Array.isArray(list)) throw new Error('Expected task array');
      const loaded = new Map<string, Task>();
      for (const t of list) {
        if (!t || typeof t.id !== 'string' || !t.id || loaded.has(t.id)) {
          throw new Error('Duplicate or invalid task ID');
        }
        for (const r of t.requirements) {
          if (r.isSatisfied && (r.isSecret ? !this.secretAvailable(r.fieldKey) : !r.value?.trim())) {
            r.isSatisfied = false;
            t.status = 'needs_human_input';
            t.testReport = undefined;
          }
        }
        if (t.testReport) {
          t.testReport.status ??= !t.testReport.success ? 'FAIL' : t.testReport.verifiedOracle && t.testReport.passedTests > 0 ? 'PASS' : 'SKIP';
          if (t.testReport.status === 'PASS' && !evidenceCurrent(t)) t.testReport.status = 'SKIP';
        }
        if (t.status === 'done' && !evidenceCurrent(t)) t.status = 'ready';
        loaded.set(t.id, t);
      }
      this.legacyTasks = new Map(original.filter((t: any) => Object.keys(t).every(key => ['id','title','status','updatedAt'].includes(key))).map((t: Task) => [t.id, {...t, status:loaded.get(t.id)!.status}]));
      this.tasks = loaded;
      this.version = version;
    } catch {
      throw new Error('Invalid task storage; refusing to overwrite it');
    }
  }

  private save(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const list = Array.from(this.tasks.values());
    const content = JSON.stringify(list, null, 2);
    writeVersion(this.filePath, this.version, content);
    this.version = content;
  }

  public getAllTasks(status?: TaskStatus): Task[] {
    this.load();
    const all = Array.from(this.tasks.values()).sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
    const visible = all.map(task => this.legacyTasks.get(task.id) ?? task);
    if (!status) return visible;
    return visible.filter((t) => t.status === status);
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
    this.validateContractId(params.contractId);
    params = taskInputSchema.parse(params) as typeof params;
    if (!params.title || params.title.trim() === '') {
      throw new Error('TaskStore: title must be a non-empty string');
    }
    if (params.priority !== undefined && !['low', 'medium', 'high', 'urgent'].includes(params.priority)) {
      throw new Error('TaskStore: invalid priority');
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
    if (!['backlog', 'ready', 'in_progress', 'needs_human_input', 'done'].includes(newStatus)) throw new Error('Invalid status');
    if (newStatus === 'done' && (!evidenceCurrent(task) || task.requirements.some(r => !r.isSatisfied || (r.isSecret && !this.secretAvailable(r.fieldKey))))) {
      throw new Error('Current contract evidence and satisfied requirements are required');
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
    task.assignee = assigneeSchema.parse(assignee);
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
    requirement = requirementInputSchema.parse(requirement);
    const key = requirement.fieldKey;
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
    task.testReport = undefined;
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
    const key = fieldKeySchema.parse(fieldKey);
    const req = task.requirements.find((r) => r.fieldKey === key);
    if (!req) {
      throw new Error(`TaskStore: requirement "${key}" not found in task "${taskId}"`);
    }
    if (req.isSecret ? !this.secretAvailable(key) : typeof value !== 'string' || !value.trim()) {
      throw new InputError('A saved credential or non-empty answer is required');
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
    report.status ??= !report.success ? 'FAIL' : report.verifiedOracle && report.passedTests > 0 ? 'PASS' : 'SKIP';
    task.testReport = report;
    if (report.status === 'PASS' && !evidenceCurrent(task)) report.status = 'SKIP';
    if (task.status === 'done' && !evidenceCurrent(task)) task.status = 'ready';
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
      text: `Tests ${report.status}: ${report.passedTests} pasados, ${report.failedTests} fallados (${report.durationMs.toFixed(1)}ms).`,
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
    if (task.testCommand !== command) { task.testReport = undefined; if (task.status === 'done') task.status = 'ready'; }
    task.testCommand = command;
    task.updatedAt = new Date().toISOString();
    this.save();
    return task;
  }

  public linkContract(id: string, contractId?: string): Task {
    this.validateContractId(contractId);
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }
    if (task.contractId !== contractId) { task.testReport = undefined; if (task.status === 'done') task.status = 'ready'; }
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

  private validateContractId(id?: string): void {
    if (id !== undefined && (typeof id !== 'string' || !/^(app-|core-|spec-)[\w.-]+\.md$/.test(id))) {
      throw new Error('Invalid contract ID');
    }
  }

  public generateKddReport(id: string): { filePath: string; relativePath: string; content: string } {
    const task = this.tasks.get(id);
    if (!task) {
      throw new Error(`TaskStore: task with id "${id}" not found`);
    }

    if (!evidenceCurrent(task) || task.requirements.some(r => !r.isSatisfied || (r.isSecret && !this.secretAvailable(r.fieldKey)))) throw new Error('Current contract evidence and satisfied requirements are required for a verified report');
    const slug =
      task.title
        .toUpperCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^A-Z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || task.id.toUpperCase();

    const parentDir = task.testReport!.cwd!;
    const logsDir = path.join(parentDir, '.agents', 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }

    const filename = `${slug}-${task.id}-REPORT.md`;
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

### Evidencia
Directorio: ${task.testReport?.cwd}
Hashes SHA-256 (contrato, target y oraculo):
${JSON.stringify(task.testReport?.evidence, null, 2)}

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
