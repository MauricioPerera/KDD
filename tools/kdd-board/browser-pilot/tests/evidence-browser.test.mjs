import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import {test, before, after} from 'node:test';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';
import {tempOutsideGit} from '../../tests/project-fixture.ts';

const pins = JSON.parse(fs.readFileSync(new URL('../pins.json',import.meta.url),'utf8'));
const source = fileURLToPath(new URL('../../../../',import.meta.url));
const artifacts = fileURLToPath(new URL('../../tests/fixtures/board-evidence/',import.meta.url));
const observations = JSON.parse(fs.readFileSync(path.join(artifacts,'receipt.json'),'utf8'));
const report = JSON.parse(fs.readFileSync(path.join(artifacts,'report.json'),'utf8')).run;
const token = 'synthetic-board-evidence-ui';
let root, server, browser, origin;
const env = Object.fromEntries(Object.entries(process.env).filter(([name])=>!name.startsWith('GIT_')));
Object.assign(env,{GIT_CONFIG_GLOBAL:process.platform==='win32'?'NUL':'/dev/null',GIT_CONFIG_NOSYSTEM:'1',
  GIT_NO_LAZY_FETCH:'1',GIT_TERMINAL_PROMPT:'0'});
const git = (cwd,...args) => execFileSync('git',['--no-replace-objects',...args],{cwd,env,encoding:'utf8',stdio:'pipe'}).trim();

before(async () => {
  root = tempOutsideGit('kdd-evidence-browser-');
  const repo = path.join(root,'project');
  const bundle = path.join(root,'bundle');
  fs.mkdirSync(repo);
  fs.cpSync(artifacts,bundle,{recursive:true});
  git(repo,'init','-q','-b','main');
  const objects = git(source,'rev-parse','--path-format=absolute','--git-path','objects');
  fs.writeFileSync(path.join(repo,'.git/objects/info/alternates'),objects.replaceAll('\\','/')+'\n');
  git(repo,'update-ref','refs/heads/main',git(source,'rev-parse','HEAD'));
  const sum = createHash('sha256').update(fs.readFileSync(path.join(bundle,'receipt.json'))).digest('hex');
  for (const key of Object.keys(process.env)) if (key.startsWith('GIT_')) delete process.env[key];
  Object.assign(process.env,{KDD_PROJECT_DIR:repo,KDD_BOARD_BROWSER_EVIDENCE_DIR:bundle,
    KDD_BOARD_BROWSER_EVIDENCE_PIN:observations.checkout+':'+sum});
  const {createServer} = await import('../../src/server.ts');
  server = createServer(token);
  server.listen(0,'127.0.0.1');
  await once(server,'listening');
  origin = 'http://127.0.0.1:'+server.address().port;
  browser = await chromium.launch();
  assert.equal(browser.version(),pins.browser_version);
});

after(async () => {
  await browser?.close();
  if (server) await new Promise(resolve=>server.close(resolve));
  if (root) await fs.promises.rm(root,{force:true,recursive:true,maxRetries:12,retryDelay:125});
});

async function visit(t) {
  const page = await browser.newPage({viewport:{width:1440,height:900}});
  page.setDefaultTimeout(8000);
  t.after(()=>page.close());
  await page.goto(origin+'/#token='+token);
  await page.getByText('Documentar el saludo y probar el flujo Git',{exact:true}).waitFor();
  return page;
}

test('opens the historical evidence inside the real Git task view', {timeout:40000}, async t => {
  const page = await visit(t);
  await page.getByText('Documentar el saludo y probar el flujo Git',{exact:true}).click();
  await page.getByRole('button',{name:'Consultar evidencia',exact:true}).click();
  const panel = page.getByRole('region',{name:'Evidencia de la tarea'});
  await panel.getByText('b9654fbcb1f759c9196edfd64819f8dd1cde435f',{exact:true}).waitFor();
  await panel.getByText('224f722ba263e36f6aa4180a52b83fe41bc8d78e',{exact:true}).waitFor();
  await panel.getByText('83d790b8a6e63c579c4519d07ae68ed6c071710a5ad475ec6116edc8f6242156',{exact:true}).waitFor();
  await panel.getByText('unittest',{exact:true}).waitFor();
  await panel.getByText('1 caso',{exact:true}).waitFor();
  await panel.getByText('Detalle por caso no registrado',{exact:true}).waitFor();
});

test('shows the exact two Chromium cases and empty attachments in their own panel', {timeout:40000}, async t => {
  const page = await visit(t);
  await page.getByRole('button',{name:'Evidencia Chromium',exact:true}).click();
  const panel = page.getByRole('region',{name:'Evidencia Chromium'});
  await panel.getByText(observations.run_id,{exact:true}).waitFor();
  await panel.getByText(observations.checkout,{exact:true}).waitFor();
  await panel.getByText('Paquete local cotejado',{exact:true}).waitFor();
  await panel.getByText(observations.report_sha256,{exact:true}).waitFor();
  const table = panel.getByRole('table');
  assert.equal(await table.getByRole('row').count(),report.results.length+1);
  for (const result of report.results) {
    const row=table.getByRole('row').filter({hasText:result.testId});
    assert.equal(await row.count(),1);
    await row.getByText('PASS',{exact:true}).waitFor();
    await row.getByText(result.attempts[0].durationMs+' ms',{exact:true}).waitFor();
    await row.getByText('Intento '+(result.attempts[0].index+1),{exact:true}).waitFor();
    await row.getByText('Sin adjuntos',{exact:true}).waitFor();
  }
  assert.equal(await panel.getByText('synthetic-browser-pilot-token',{exact:false}).count(),0);
});
