import fs from 'node:fs';
import {test} from '@e2e-dev/web';
import {expect} from 'e2e';

const {ready, missing} = JSON.parse(fs.readFileSync(process.env.KDD_BOARD_BROWSER_FIXTURE!, 'utf8'));
const entry = '/#token=synthetic-browser-pilot-token';

test('ready candidate requires human approval', async ({app, screen}) => {
  await app.open(entry);
  await screen.getByText('Relevo listo', {exact: true}).click();
  await expect(screen.getByRole('heading', 'TASK-001: Relevo listo')).toBeVisible();
  await screen.getByRole('button', 'Consultar revisión').click();
  await expect(screen.getByText('Revisión lista', {exact: true})).toBeVisible();
  await expect(screen.getByText(ready, {exact: true})).toBeVisible();
  await expect(screen.getByText('Pendiente de aprobación humana del candidato.', {exact: true})).toBeVisible();
  await expect(screen.getByRole('button', 'Consultar revisión')).toBeEnabled();
});

test('missing evidence stays pending', async ({app, screen}) => {
  await app.open(entry);
  await screen.getByText('Relevo pendiente', {exact: true}).click();
  await expect(screen.getByRole('heading', 'TASK-002: Relevo pendiente')).toBeVisible();
  await screen.getByRole('button', 'Consultar revisión').click();
  await expect(screen.getByText('Pendiente de revisión', {exact: true})).toBeVisible();
  await expect(screen.getByText(missing, {exact: true})).toBeVisible();
  await expect(screen.getByText('Revisión lista', {exact: true})).toHaveCount(0);
  await expect(screen.getByRole('button', 'Consultar revisión')).toBeEnabled();
});
