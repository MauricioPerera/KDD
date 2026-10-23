import {z} from 'zod';
import {defineTool,registerTool,type RegisterToolOptions} from 'fastwebmcp';
import {GitTaskStore} from './git-task-store.ts';

export const taskId = z.string().regex(/^TASK-\d{3,}$/);
export const statusSchema = z.enum(['backlog','ready','in_progress','needs_human_input','done']);
export const creationSchema = z.object({
  task_id:taskId,title:z.string().min(1),description:z.string().min(1),contract:z.string().min(1),
  depends_on:z.array(taskId).optional(),
}).strict();
export const transitionSchema = z.object({
  status:statusSchema,approved_ref:z.string().regex(/^[a-f0-9]{40}$/).optional(),
  assignee:z.string().min(1).optional(),reason:z.string().min(1).optional(),
}).strict();

export function createGitBridge(store: GitTaskStore) {
  const specs = [
    {name:'list_tasks',description:'Lee tareas OKF confirmadas en main.',inputSchema:z.object({status:statusSchema.optional()}).strict(),
      execute:async (input: {status?:string})=>store.list(input.status),annotations:{readOnlyHint:true}},
    {name:'get_task',description:'Lee una tarea de main y su historial de commits.',inputSchema:z.object({task_id:taskId}).strict(),
      execute:async (input: {task_id:string})=>store.get(input.task_id),annotations:{readOnlyHint:true}},
    {name:'create_task',description:'Crea un nodo Task en main mediante un commit; exige main limpio.',inputSchema:creationSchema,
      execute:async (input: z.infer<typeof creationSchema>)=>store.create(input)},
    {name:'update_task_status',description:'Registra una transicion canonica con commit. Preparar exige SHA aprobado; iniciar propietario; bloquear/reanudar motivo; cerrar integra y verifica tests.',
      inputSchema:transitionSchema.extend({task_id:taskId}),
      execute:async ({task_id,...input}: z.infer<typeof transitionSchema> & {task_id:string})=>store.transition(task_id,input)},
    {name:'task_history',description:'Lista el diario de commits de una tarea en main.',inputSchema:z.object({task_id:taskId}).strict(),
      execute:async (input:{task_id:string})=>store.history(input.task_id),annotations:{readOnlyHint:true}},
  ];
  return {specs,getDefinedTools:()=>specs.map(spec=>defineTool(spec as any)),
    registerAll:(options?:RegisterToolOptions)=>specs.map(spec=>registerTool(spec as any,options))};
}
