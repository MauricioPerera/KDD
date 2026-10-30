// Git tasks use the canonical coordinator; this module owns no task state.
'use strict';
{
  const edges = {backlog:['ready'],ready:['in_progress'],in_progress:['needs_human_input','done'],needs_human_input:['ready'],done:[]};
  const labels = {ready:'Preparar',in_progress:'Iniciar',needs_human_input:'Bloquear',done:'Verificar y cerrar'};
  const node = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let configuration;
  let mode;
  let selectedId;
  let pending = false;

  async function configure(api) {
    if (!configuration) configuration = (async () => {
      const config = await api('/api/board');
      mode = config.mode;
      if (mode !== 'git') return config;
      node('git-create-fields').hidden = false;
      node('task-id').required = true;
      node('task-contract').required = true;
      node('task-desc').required = true;
      node('task-assignee').closest('.form-group').hidden = true;
      node('task-priority').closest('.form-group').hidden = true;
      node('task-assignee').closest('.form-group').style.display = 'none';
      node('task-priority').closest('.form-group').style.display = 'none';
      node('task-contract-label').textContent = 'Contrato confirmado en main';
      node('git-board-notice').hidden = false;
      node('git-board-notice').textContent = 'Tareas OKF de main. Crear y cambiar estado genera commits; requiere main limpio.';
      return config;
    })().catch(error => {configuration=undefined;throw error;});
    const config = await configuration;
    if (mode === 'git') {
      const contracts = await api('/api/board/contracts');
      if (!Array.isArray(contracts) || contracts.some(c=>!c || typeof c.id !== 'string' || typeof c.title !== 'string')) {
        throw new Error('Catalogo de contratos invalido');
      }
      const select = node('task-contract');
      const selected = select.value;
      const options = '<option value="">-- Seleccionar contrato --</option>' +
        contracts.map(c=>`<option value="${escape(c.id)}">${escape(c.title)}</option>`).join('');
      if (select.innerHTML !== options) {
        select.innerHTML = options;
        select.value = contracts.some(c=>c.id === selected) ? selected : '';
      }
    }
    return config;
  }

  function createInput(input) {
    return {task_id:node('task-id').value.trim(),title:input.title,description:input.description,
      contract:input.contractId,depends_on:node('task-dependencies').value.split(',').map(s=>s.trim()).filter(Boolean)};
  }

  function actionFields(task) {
    const options = edges[task.status] || [];
    if (!options.length) return '<p>La tarea esta cerrada. Su evidencia permanece en Git.</p>';
    const needsApproval = task.status === 'backlog';
    const needsOwner = task.status === 'ready';
    const needsReason = ['in_progress','needs_human_input'].includes(task.status);
    return `<form id="git-transition-form">
      <label for="git-next-status">Siguiente estado</label>
      <select id="git-next-status">${options.map(s=>`<option value="${s}">${labels[s]}</option>`).join('')}</select>
      ${needsApproval ? '<label for="git-approved-ref">SHA aprobado del contrato (40 o 64 caracteres)</label><input id="git-approved-ref" required pattern="(?:[a-f0-9]{40}|[a-f0-9]{64})" autocomplete="off" />' : ''}
      ${needsOwner ? `<label for="git-assignee">Propietario</label><input id="git-assignee" required value="${escape(task.assignee)}" />` : ''}
      ${needsReason ? '<div id="git-reason-field"><label for="git-reason">Motivo publico (sin secretos)</label><input id="git-reason" /></div>' : ''}
      <p id="git-finish-note" hidden>El cierre exige la rama integrada en main y ejecuta los tests del contrato; puede tardar hasta 120 segundos.</p>
      <button class="btn btn-primary" id="git-submit" type="submit">Registrar commit</button>
    </form>`;
  }

  function journalHtml(task) {
    return (task.journal || []).map(h=>`<li><code>${escape(h.commit)}</code> ${escape(h.status)}: ${escape(h.reason)}</li>`).join('');
  }

  function updateFields(task) {
    if (task.status !== 'in_progress') return;
    const finish = node('git-next-status').value === 'done';
    node('git-reason-field').hidden = finish;
    node('git-reason').required = !finish;
    node('git-finish-note').hidden = !finish;
  }

  async function submit(event,task,api,refresh) {
    event.preventDefault();
    if (pending) return;
    const status = node('git-next-status').value;
    const payload = {status};
    if (task.status === 'backlog') payload.approved_ref = node('git-approved-ref').value.trim();
    if (status === 'in_progress') payload.assignee = node('git-assignee').value.trim();
    if (status === 'needs_human_input' || task.status === 'needs_human_input') payload.reason = node('git-reason').value.trim();
    pending = true;
    node('git-submit').disabled = true;
    node('git-action-result').textContent = 'Registrando transicion...';
    try {
      const result = await api(`/api/tasks/${encodeURIComponent(task.id)}/status`,{
        method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      if (!/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(result.commit)) throw new Error('Respuesta sin commit confirmado; refresca main.');
      node('git-action-result').textContent = `Commit confirmado: ${result.commit}`;
      pending = false;
      selectedId = undefined;
      await refresh();
    } catch (error) {
      node('git-action-result').textContent = error.message;
    } finally {pending=false;node('git-submit').disabled=false;}
  }

  function taskHtml(detail) {
    return `<section class="git-task">
        <button type="button" class="btn" id="git-back">Volver al tablero</button>
        <h2>${escape(detail.id)}: ${escape(detail.title)}</h2><p>${escape(detail.description)}</p>
        <dl><dt>Estado en main</dt><dd>${escape(detail.status)}</dd>
        <dt>Rama</dt><dd><code>${escape(detail.branch)}</code></dd>
        <dt>Contrato</dt><dd><code>${escape(detail.contract)}</code></dd>
        <dt>Propietario</dt><dd>${escape(detail.assignee || 'Sin asignar')}</dd>
        <dt>Dependencias</dt><dd>${escape((detail.depends_on || []).join(', ') || 'Ninguna')}</dd>
        <dt>SHA aprobado</dt><dd><code>${escape(detail.approved_ref || 'Pendiente')}</code></dd>
        <dt>Commit verificado</dt><dd><code>${escape(detail.verified_ref || 'Pendiente')}</code></dd>
        <dt>Evidencia</dt><dd><code>${escape(detail.evidence || 'Pendiente')}</code></dd></dl>
        ${actionFields(detail)}<p id="git-action-result" role="status" aria-live="polite"></p>
        <h3>Historial de commits</h3><ol>${journalHtml(detail)}</ol></section>`;
  }

  async function render(task,api,refresh) {
    const fields = ['git-approved-ref','git-assignee','git-reason','git-next-status'];
    if (selectedId === task.id && (pending || fields.some(id=>node(id) === document.activeElement))) return;
    selectedId = task.id;
    try {
      const detail = task.journal ? task : await api(`/api/tasks/${encodeURIComponent(task.id)}`);
      if (selectedId !== task.id) return;
      // A read already in flight must not replace a field focused while it awaited Git.
      if (pending || fields.some(id=>node(id) === document.activeElement)) return;
      node('workspace-container').innerHTML = taskHtml(detail);
      node('git-back').onclick = () => window.switchView('board');
      if ((edges[detail.status] || []).length) {
        node('git-transition-form').onsubmit = event => submit(event,detail,api,refresh);
        node('git-next-status').onchange = () => updateFields(detail);
        updateFields(detail);
        if (detail.status === 'needs_human_input') node('git-reason').required = true;
      }
    } catch (error) {
      node('workspace-container').textContent = error.message;
    }
  }
  window.KddGitBoard = {configure,createInput,render,get mode(){return mode;}};
}
