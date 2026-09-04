export type TaskStatus =
  | 'backlog'
  | 'ready'
  | 'in_progress'
  | 'needs_human_input'
  | 'done';

export type TaskAssignee = 'human' | 'agent' | 'unassigned';

export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface HumanInputRequirement {
  fieldKey: string;
  label: string;
  description: string;
  isSecret: boolean;
  isSatisfied: boolean;
  value?: string; // Stored only if isSecret === false
}

export interface TaskComment {
  id: string;
  author: 'human' | 'agent' | 'system';
  text: string;
  timestamp: string;
}

export interface TaskTestReport {
  lastRun: string;
  success: boolean;
  durationMs: number;
  passedTests: number;
  failedTests: number;
  output: string;
  reportPath?: string;
}

export interface TaskMetrics {
  requirementsCount: number;
  satisfiedCount: number;
  commentsCount: number;
  lastRunDurationMs?: number;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: TaskAssignee;
  priority: TaskPriority;
  contractId?: string;
  testCommand?: string;
  testReport?: TaskTestReport;
  metrics?: TaskMetrics;
  requirements: HumanInputRequirement[];
  comments: TaskComment[];
  createdAt: string;
  updatedAt: string;
}

export interface BlindSecretMeta {
  key: string;
  isSet: boolean;
  maskedValue: string;
  updatedAt: string;
}
