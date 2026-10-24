import type {IncomingMessage,ServerResponse} from 'node:http';
import {BoardGitError,GitTaskStore,transitions,taskError} from './git-task-store.ts';
import {creationSchema,transitionSchema,createGitBridge} from './git-bridge.ts';

type Send = (res:ServerResponse,status:number,data:unknown)=>void;
type Body = <T>(req:IncomingMessage)=>Promise<T>;

export function createGitApi(store:GitTaskStore,readBody:Body,send:Send) {
  const bridge = createGitBridge(store);
  const unavailable = () => {throw new BoardGitError('This operation is unavailable for Git tasks; use a canonical state transition',409);};
  const routes:Record<string,()=>unknown> = {
    'GET /api/board':()=>({mode:'git',sourceRef:'main',transitions}),
    'GET /api/board/contracts':()=>store.contracts(),
    'GET /api/tools':()=>bridge.getDefinedTools().map(t=>({name:t.name,description:t.description,inputSchema:t.inputSchema})),
  };

  async function dispatch(req:IncomingMessage,url:URL):Promise<unknown> {
    const key = `${req.method} ${url.pathname}`;
    if (Object.hasOwn(routes,key)) return routes[key]();
    if (key === 'GET /api/tasks') return store.list(url.searchParams.get('status') ?? undefined);
    if (key === 'POST /api/tasks') return store.create(creationSchema.parse(await readBody(req)));
    const match=url.pathname.match(/^\/api\/tasks\/(TASK-\d{3,})(?:\/(history|status))?$/);
    if (!match) return unavailable();
    const actions:Record<string,()=>unknown> = {
      'GET task':()=>store.get(match[1]),
      'GET history':()=>store.history(match[1]),
      'PATCH status':async()=>store.transition(match[1],transitionSchema.parse(await readBody(req))),
    };
    const action = `${req.method} ${match[2] || 'task'}`;
    return Object.hasOwn(actions,action) ? actions[action]() : unavailable();
  }

  return async (req:IncomingMessage,res:ServerResponse,url:URL):Promise<boolean> => {
    const route = url.pathname;
    const exact = ['/api/board','/api/tools','/api/tasks'].includes(route);
    const nested = ['/api/board/','/api/tasks/'].some(prefix=>route.startsWith(prefix));
    if (!exact && !nested) return false;
    try {
      const result=await dispatch(req,url);
      send(res,req.method === 'POST' && route === '/api/tasks' ? 201 : 200,result);
    } catch (error:any) {
      const detail=taskError(error);
      send(res,detail.status,{error:detail.message,code:detail.code,status:detail.status,details:detail.details});
    }
    return true;
  };
}
