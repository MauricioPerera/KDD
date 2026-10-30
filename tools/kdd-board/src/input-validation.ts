import { z } from 'zod';

export const assigneeSchema = z.enum(['human', 'agent', 'unassigned']);
export const statusSchema = z.enum(['backlog', 'ready', 'in_progress', 'needs_human_input', 'done']);
export const prioritySchema = z.enum(['low', 'medium', 'high', 'urgent']);
const nonempty = z.string().trim().min(1);
const contractId = z.string().regex(/^(app-|core-|spec-)[\w.-]+\.md$/).optional();
export const fieldKeySchema = nonempty.transform(key => key.toUpperCase().replace(/[^A-Z0-9_]/g, '_'));
const authorSchema = z.enum(['human', 'agent', 'system']);
const commentInput = z.object({author: authorSchema, text: z.string()}).strict();
export const taskInputSchema = z.object({
  title: nonempty, description: z.string().optional(), assignee: assigneeSchema.optional(),
  priority: prioritySchema.optional(), contractId, testCommand: nonempty.optional(),
}).strict();
export const requirementInputSchema = z.object({
  fieldKey: fieldKeySchema, label: nonempty, description: z.string(), isSecret: z.boolean().optional(),
}).strict();
export const httpSchemas = {
  task: taskInputSchema,
  status: z.object({status: statusSchema, comment: commentInput.optional()}).strict(),
  assign: z.object({assignee: assigneeSchema}).strict(),
  contract: z.object({contractId}).strict(),
  requirement: requirementInputSchema,
  fulfill: z.object({fieldKey: fieldKeySchema, value: nonempty.optional(), secretValue: z.string().refine(value => Boolean(value.trim()), 'Secret required').optional()}).strict(),
  vault: z.object({key: fieldKeySchema, value: z.string().refine(value => Boolean(value.trim()), 'Secret required')}).strict(),
};
const requirementSchema = z.object({
  fieldKey: z.string().regex(/^[A-Z0-9_]+$/), label: z.string(), description: z.string(),
  isSecret: z.boolean(), isSatisfied: z.boolean(), value: z.string().optional(),
}).strict().refine(r => !r.isSecret || r.value === undefined, 'Secret values cannot be stored in tasks');
const reportSchema = z.object({
  lastRun: z.string(), success: z.boolean(), durationMs: z.number().nonnegative(),
  passedTests: z.number().int().nonnegative(), failedTests: z.number().int().nonnegative(),
  oracleRunner: z.literal('python-unittest-recorder-v1').optional(),
  verifiedOracle: z.boolean().optional(), status: z.enum(['PASS', 'FAIL', 'SKIP', 'TIMEOUT']).optional(),
  output: z.string(), reportPath: z.string().optional(), command: z.string().optional(),
  cwd: z.string().optional(), contractId: z.string().optional(), evidence: z.record(z.string(), z.string()).optional(),
}).strict();
export const storedTasksSchema = z.array(z.object({
  id: z.string().regex(/^task-[\w-]+$/), title: nonempty, description: z.string(),
  status: statusSchema, assignee: assigneeSchema, priority: prioritySchema, contractId,
  testCommand: z.string().optional(), testReport: reportSchema.optional(),
  metrics: z.object({requirementsCount: z.number(), satisfiedCount: z.number(), commentsCount: z.number(), lastRunDurationMs: z.number().optional()}).strict().optional(),
  requirements: z.array(requirementSchema),
  comments: z.array(commentInput.extend({id: z.string(), timestamp: z.string()})),
  createdAt: z.string(), updatedAt: z.string(),
}).strict());

export class InputError extends Error {}
