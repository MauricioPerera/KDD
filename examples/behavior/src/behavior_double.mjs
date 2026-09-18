import { readFileSync } from 'node:fs';

const inputs = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(inputs.map((n) => n * 2)));
