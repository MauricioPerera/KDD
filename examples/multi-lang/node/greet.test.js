// Oraculo congelado del ejemplo multi-lenguaje (Contrato: example-node-greet).
//
// Demuestra que el sellado tests_sha256 y el perimetro touch_only son
// agnosticos de lenguaje: este archivo se sella con el mismo
// scripts/validate_contracts.py --hash usado para los oraculos Python del
// repo, sin ningun cambio de herramienta.
//
// Usa node:test + node:assert (nucleo de Node.js, sin npm install, sin
// dependencias, sin red) — mismo espiritu que deps_allowed: [] en los
// contratos Python de este repo.

const test = require('node:test');
const assert = require('node:assert/strict');
const { greet } = require('./greet.js');

test('saluda con un nombre simple', () => {
  assert.equal(greet('Ana'), 'Hello, Ana!');
});

test('saluda con nombre vacio', () => {
  assert.equal(greet(''), 'Hello, !');
});

test('no lanza excepcion con caracteres especiales', () => {
  assert.doesNotThrow(() => greet('O\'Brien'));
});
