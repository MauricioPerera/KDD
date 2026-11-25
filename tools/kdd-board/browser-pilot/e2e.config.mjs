import fs from 'node:fs';
import {web} from '@e2e-dev/web';

const {origin} = JSON.parse(fs.readFileSync(process.env.KDD_BOARD_BROWSER_FIXTURE, 'utf8'));

export default {
  targets: [{engine: web({browser: 'chromium'}), app: {url: origin}}],
  workers: 1,
  retries: 0,
  timeout: 20000,
};
