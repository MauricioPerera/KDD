import { BlindVault } from '../src/blind-vault.ts';
import { TaskStore } from '../src/task-store.ts';
import { createWebMcpBridge } from '../src/webmcp-bridge.ts';
import path from 'node:path';

const rootDir = path.resolve(import.meta.dirname, '..');
const taskStore = new TaskStore(path.join(rootDir, 'data', 'tasks.json'));
const vault = new BlindVault(path.join(rootDir, 'data', '.env.local'));
const bridge = createWebMcpBridge(taskStore, vault);

async function runDemo() {
  console.log('🤖 AGENTE: 1. Creando nueva tarea en el tablero...');
  const task = taskStore.createTask({
    title: 'Integrar pasarela de pagos Stripe',
    description: 'Configurar procesamiento de pagos seguros con webhooks.',
    assignee: 'agent',
    priority: 'urgent',
  });
  console.log(`✅ Tarea creada: "${task.title}" (ID: ${task.id})`);

  console.log('\n🤖 AGENTE: 2. Moviendo tarea a "in_progress"...');
  taskStore.updateTaskStatus(task.id, 'in_progress', {
    author: 'agent',
    text: 'Iniciando diseño del endpoint de checkout.',
  });

  console.log('\n🤖 AGENTE: 3. Solicitando credencial ciega (STRIPE_SECRET_KEY)...');
  taskStore.requestHumanInput(task.id, {
    fieldKey: 'STRIPE_SECRET_KEY',
    label: 'Stripe Secret API Key',
    description: 'Clave privada de Stripe que comienza con sk_live_...',
    isSecret: true,
  });
  console.log('🛑 Tarea bloqueada en "needs_human_input", asignada al Humano.');
}

runDemo();
