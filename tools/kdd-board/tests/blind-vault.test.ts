import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { BlindVault } from '../src/blind-vault.ts';

test('BlindVault: guarda, recupera internamente y redacta para agentes', () => {
  const tmpFile = path.join(os.tmpdir(), `test-vault-${Date.now()}.env`);
  try {
    const vault = new BlindVault(tmpFile);

    // Guardar secreto
    vault.setSecret('OPENAI_API_KEY', 'sk-proj-1234567890abcdef12345678');
    vault.setSecret('PIN', '1234');

    assert.equal(vault.hasSecret('OPENAI_API_KEY'), true);
    assert.equal(vault.hasSecret('PIN'), true);
    assert.equal(vault.hasSecret('MISSING'), false);

    // Listar metadata redactada para agentes (sin texto plano)
    const secrets = vault.listSecrets();
    assert.equal(secrets.length, 2);

    const openAiMeta = secrets.find((s) => s.key === 'OPENAI_API_KEY');
    assert.ok(openAiMeta);
    assert.equal(openAiMeta.isSet, true);
    // El maskedValue no expone la clave completa
    assert.equal(openAiMeta.maskedValue.includes('sk-'), true);
    assert.equal(openAiMeta.maskedValue.includes('1234567890abcdef'), false);
    assert.equal(openAiMeta.maskedValue.includes('***'), true);

    const pinMeta = secrets.find((s) => s.key === 'PIN');
    assert.ok(pinMeta);
    assert.equal(pinMeta.maskedValue, '***[4 chars]***');

    // Valor real accesible internamente por el servidor
    assert.equal(vault.getSecretValue('OPENAI_API_KEY'), 'sk-proj-1234567890abcdef12345678');
  } finally {
    if (fs.existsSync(tmpFile)) {
      fs.unlinkSync(tmpFile);
    }
  }
});

test('BlindVault: persistencia en archivo de formato .env', () => {
  const tmpFile = path.join(os.tmpdir(), `test-vault-pers-${Date.now()}.env`);
  try {
    const vault1 = new BlindVault(tmpFile);
    vault1.setSecret('GITHUB_TOKEN', 'ghp_secretTokenHere999');

    // Instancia 2 lee el mismo archivo
    const vault2 = new BlindVault(tmpFile);
    assert.equal(vault2.hasSecret('GITHUB_TOKEN'), true);
    assert.equal(vault2.getSecretValue('GITHUB_TOKEN'), 'ghp_secretTokenHere999');
  } finally {
    if (fs.existsSync(tmpFile)) {
      fs.unlinkSync(tmpFile);
    }
  }
});
