import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
// Explicit external runtime: this example does not install or download code.
assert.equal(process.argv.length,4,'Usage: node verify.mjs /path/kite_lite_wasm.js /path/kite_lite_wasm_bg.wasm');
const runtimeURL=pathToFileURL(resolve(process.argv[2]));
const wasm=await readFile(resolve(process.argv[3]));
const runtime=await readFile(runtimeURL);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
assert.equal(sha(runtime),'09073dfdbef457ccf237b6062d174c6ec896c8666eb21d0511522d552ce432ad','Unrecognized JS runtime');
assert.equal(sha(wasm),'b68e6a5aff31b54a3d3378601f0ff261d79b797988b5e46d0840c64bbe6900a8','Unrecognized WASM runtime');
const {default:init,run_lua_policy}=await import(runtimeURL.href);
await init({module_or_path:wasm});
const contract=JSON.parse(await readFile(new URL('./contract.json',import.meta.url)));
const observed=JSON.parse(await readFile(new URL('./observed.json',import.meta.url)));
const policy=`
local function equal(a,b)
 if type(a) ~= type(b) then return false end
 if type(a) ~= 'table' then return a == b end
 for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
 for k,v in pairs(b) do if a[k] == nil then return false end end
 return true
end
local models = equal(input.expected.models,input.observed.models)
local scene = equal(input.expected.scene,input.observed.scene)
local camera = equal(input.expected.camera,input.observed.camera)
return {passed=models and scene and camera,models_match=models,scene_match=scene,camera_match=camera}
`;
const check=(expected,actual)=>Object.fromEntries(run_lua_policy({expected,observed:actual},policy));
const verdict=check(contract.expected,observed);
console.log('RECORDED READBACK REPLAY',JSON.stringify(verdict));
assert.equal(verdict.passed,true,'Real readback must match the pre-action contract');
assert.equal(check(contract.expected,contract.before).passed,false,'A no-op must not pass');
const wrong=structuredClone(contract.expected);wrong.models[0].transform.position[0]+=1;
assert.equal(check(wrong,observed).passed,false,'Wrong expected position must not pass');
const tampered=structuredClone(observed);tampered.models[1].material.color='#ff0000';
assert.equal(check(contract.expected,tampered).passed,false,'A synthetic unrelated model mutation must not pass');
console.log('PASS: 1 recorded readback replay + 3 negative fixture checks; Lua in real WASM. No persistence or pixel guarantee.');
