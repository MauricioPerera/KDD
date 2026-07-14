---
task: <task>
agent: <glm-5.2:cloud | claude-opus-4-8 | human | ...>
model: <mismo valor que agent, o 'n/a' si es humano>
command: "<comando exacto corrido, ej. 'python -m unittest tests/test_x.py'>"
exit_code: <0 o el codigo real>
output_sha256: <sha256 LF-normalizado del texto pegado abajo del segundo '---'; generarlo con: python scripts/validate_contracts.py --hash <este_archivo> NO sirve directo (ese hash es del archivo completo) -- calcula el sha256 solo del BODY, ej. con: python -c "import hashlib; print(hashlib.sha256(open('body.txt','rb').read().replace(b'\r\n',b'\n').replace(b'\r',b'\n')).hexdigest())">
contract_sha256: <sha256 de knowledge/contracts/<task>.md AL MOMENTO de verificar; python scripts/validate_contracts.py --hash knowledge/contracts/<task>.md da el hash del archivo de TESTS, no del contrato -- para el contrato usa el mismo comando pero apuntando a knowledge/contracts/<task>.md>
repo_head: <git rev-parse HEAD>
timestamp: <YYYY-MM-DDTHH:MM:SSZ>
---
<Pega ACA, sin modificar, la salida REAL de correr `command` (y del validador de
Nivel 1 si aplica). No la narres ni la resumas -- el texto exacto es lo que
`output_sha256` sella arriba.>

<!--
COMO USAR ESTA PLANTILLA (borrar este bloque en tu copia):

1. Copiala: cp .agents/logs/TEMPLATE-REPORT.md .agents/logs/<task>-REPORT.md
2. Corre el comando real, pega su salida COMPLETA abajo del segundo '---'
   (reemplazando este bloque de instrucciones).
3. Calcula output_sha256 sobre ESE body pegado (LF-normalizado) y
   contract_sha256 sobre knowledge/contracts/<task>.md tal como esta AHORA.
4. Completa el resto de los campos del envelope.
5. Verifica: python scripts/validate_attestation.py .agents/logs .
   -- debe reportar [] (sin findings) para tu archivo. ERROR = algo no calza.

Este directorio (.agents/logs/) esta gitignorado a proposito: es evidencia
LOCAL, no se commitea. El gate NO corre en CI por el mismo motivo.
Ver knowledge/contracts/attestation-gate.md y knowledge/validacion.md
(ciclo de vida del contrato, paso "verified").
-->
