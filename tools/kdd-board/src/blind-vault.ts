import fs from 'node:fs';
import path from 'node:path';
import type { BlindSecretMeta } from './types.ts';

export class BlindVault {
  private filePath: string;
  private secrets: Map<string, { value: string; updatedAt: string }> = new Map();

  constructor(filePath: string) {
    this.filePath = filePath;
    this.load();
  }

  private load(): void {
    if (!fs.existsSync(this.filePath)) {
      return;
    }
    const content = fs.readFileSync(this.filePath, 'utf-8');
    const lines = content.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const eqIdx = trimmed.indexOf('=');
      if (eqIdx === -1) continue;
      const key = trimmed.substring(0, eqIdx).trim();
      let val = trimmed.substring(eqIdx + 1).trim();
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.substring(1, val.length - 1);
      }
      this.secrets.set(key, { value: val, updatedAt: new Date().toISOString() });
    }
  }

  private save(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const lines: string[] = ['# Blind Vault managed credentials (KDD-Board)'];
    for (const [key, item] of this.secrets.entries()) {
      lines.push(`${key}=${JSON.stringify(item.value)}`);
    }
    fs.writeFileSync(this.filePath, lines.join('\n') + '\n', 'utf-8');
  }

  public setSecret(key: string, secretValue: string): void {
    const sanitizedKey = key.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    if (!sanitizedKey) {
      throw new Error('BlindVault: key must be a non-empty string');
    }
    this.secrets.set(sanitizedKey, {
      value: secretValue,
      updatedAt: new Date().toISOString(),
    });
    this.save();
  }

  public hasSecret(key: string): boolean {
    this.load();
    const sanitizedKey = key.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    return this.secrets.has(sanitizedKey);
  }

  public maskSecret(value: string): string {
    if (!value) return '***';
    if (value.length <= 8) {
      return `***[${value.length} chars]***`;
    }
    const prefix = value.substring(0, 3);
    const suffix = value.substring(value.length - 2);
    return `${prefix}***...***${suffix}`;
  }

  public listSecrets(): BlindSecretMeta[] {
    this.load();
    const list: BlindSecretMeta[] = [];
    for (const [key, item] of this.secrets.entries()) {
      list.push({
        key,
        isSet: true,
        maskedValue: this.maskSecret(item.value),
        updatedAt: item.updatedAt,
      });
    }
    return list;
  }

  public getSecretValue(key: string): string | undefined {
    this.load();
    const sanitizedKey = key.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    return this.secrets.get(sanitizedKey)?.value;
  }

  public deleteSecret(key: string): boolean {
    this.load();
    const sanitizedKey = key.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    const existed = this.secrets.delete(sanitizedKey);
    if (existed) {
      this.save();
    }
    return existed;
  }

  public exportToProcessEnv(): void {
    for (const [key, item] of this.secrets.entries()) {
      process.env[key] = item.value;
    }
  }
}
