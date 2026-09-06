import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('contracts are available at startup without visiting documentation', async () => {
  const nodes = new Map<string, any>();
  const getNode = (id: string) => {
    if (!nodes.has(id)) nodes.set(id, {innerHTML:'', value:'', textContent:'', dataset:{},
      classList: {add(){},remove(){},toggle(){}}, addEventListener(){}, appendChild(){}});
    return nodes.get(id);
  };
  const requests: string[] = [];
  const context = vm.createContext({
    document: {getElementById:getNode, querySelectorAll:()=>[]},
    location: {hash:'', pathname:'/', search:''}, sessionStorage: {getItem:()=> 'test-token'},
    URLSearchParams, Headers, console, setInterval:()=>0,
    fetch: async (url: string) => {
      requests.push(url);
      return {ok:true,json:async()=>url==='/api/docs' ? [{id:'app-fixture.md', title:'Fixture', isContract:true}] : []};
    },
  });
  context.window = context;
  vm.runInContext(fs.readFileSync(new URL('../public/app.js', import.meta.url), 'utf8'), context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(requests.includes('/api/docs'));
  assert.match(getNode('task-contract').innerHTML, /app-fixture\.md/);
  await vm.runInContext('loadTasks()', context);
  assert.equal(requests.filter(url=>url==='/api/docs').length, 1);
});
