import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const getShortName = [
  'import ctypes, sys',
  'read = ctypes.windll.kernel32.GetShortPathNameW',
  'read.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong)',
  'read.restype = ctypes.c_ulong',
  'buffer = ctypes.create_unicode_buffer(32768)',
  'size = read(sys.argv[1], buffer, len(buffer))',
  'assert 0 < size < len(buffer)',
  'print(buffer.value)',
].join('\n');

export function createWindowsAliasDirectory(root: string) {
  assert.equal(process.platform, 'win32');
  const systemTemp = path.join(process.env.SystemRoot || 'C:/Windows','Temp');
  for (const parent of [root,systemTemp]) {
    if (!fs.existsSync(parent)) continue;
    const directory = fs.mkdtempSync(path.join(fs.realpathSync.native(parent),'KDD evidence directory '));
    const alias = execFileSync(process.env.KDD_PYTHON || 'python',
      ['-I','-X','utf8','-c',getShortName,directory],
      {encoding:'utf8',stdio:'pipe',timeout:15000}).trim();
    if (path.relative(directory,alias)) {
      assert.equal(path.relative(directory,fs.realpathSync.native(alias)),'');
      assert.equal(fs.lstatSync(alias).isSymbolicLink(),false);
      return {directory,alias};
    }
    fs.rmdirSync(directory);
  }
  throw new Error('No Windows test volume supplied an actual 8.3 directory alias');
}
