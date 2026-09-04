import { BlindVault } from '../src/blind-vault.ts';
import { TaskStore } from '../src/task-store.ts';
import { createWebMcpBridge } from '../src/webmcp-bridge.ts';
import path from 'node:path';

const rootDir = path.resolve(import.meta.dirname, '..');
const taskStore = new TaskStore(path.join(rootDir, 'data', 'tasks.json'));
const vault = new BlindVault(path.join(rootDir, 'data', '.env.local'));
const bridge = createWebMcpBridge(taskStore, vault);

async function agentResumeWork() {
  console.log('🤖 AGENTE: 1. Consultando credenciales disponibles vía WebMCP tool...');
  const credsSpec = bridge.specs.find((s) => s.name === 'list_available_credentials')!;
  const credsResult = (await (credsSpec.execute as any)({})) as any;

  console.log('🔍 Resultado de WebMCP list_available_credentials (lo que el agente ve):');
  console.log(JSON.stringify(credsResult, null, 2));

  const stripeCred = credsResult.credentials.find((c: any) => c.key === 'STRIPE_SECRET_KEY');
  if (!stripeCred || !stripeCred.isSet) {
    throw new Error('STRIPE_SECRET_KEY no está configurada!');
  }

  console.log('\n🤖 AGENTE: 2. Exportando credenciales al proceso de ejecución local...');
  vault.exportToProcessEnv();

  console.log('\n⚡ CÓDIGO EN EJECUCIÓN (Stripe Checkout Mock):');
  // El código del agente corre de forma segura
  const secretKey = process.env.STRIPE_SECRET_KEY;
  console.log(`[StripeSDK] Inicializado con clave: ${secretKey ? 'OK (Presente en proceso)' : 'ERROR'}`);
  console.log(`[StripeSDK] Longitud de clave en entorno: ${secretKey?.length} caracteres`);
  console.log(`[StripeSDK] Simulando llamada a API Stripe https://api.stripe.com/v1/checkout/sessions... Status: 200 OK`);

  console.log('\n🤖 AGENTE: 3. Moviendo tarea a "done" en el tablero...');
  const tasks = taskStore.getAllTasks();
  const stripeTask = tasks.find((t) => t.title.includes('Stripe'))!;
  taskStore.updateTaskStatus(stripeTask.id, 'done', {
    author: 'agent',
    text: 'Integración completada exitosamente con la credencial inyectada en el entorno local.',
  });
  console.log(`🎉 Tarea "${stripeTask.title}" movida a DONE!`);
}

agentResumeWork();
