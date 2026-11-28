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
  let reviewState = {};
  let evidenceState = {};
  let acceptanceState = {};

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

  function reviewEntry(entry) {
    const labels = {missing:'Pendiente de revisión',blocked:'Revisión con hallazgos',ready:'Revisión lista'};
    return `<p><strong>${escape(labels[entry.review_status])}</strong></p>
      <dl><dt>Candidato</dt><dd><code>${escape(entry.candidate_commit)}</code></dd>
      <dt>Base</dt><dd><code>${escape(entry.base_commit)}</code></dd>
      <dt>Árbol</dt><dd><code>${escape(entry.candidate_tree)}</code></dd>
      <dt>Huella del v1</dt><dd><code>${escape(entry.review_sha256 || 'Pendiente')}</code></dd></dl>
      ${entry.finding_codes.length ? `<p>${escape(entry.finding_codes.join(', '))}</p>` : ''}`;
  }

  function reviewHtml(review) {
    if (!review.current) return '<p>La tarea aún no tiene candidato seleccionado.</p>';
    const action = review.current.review_status === 'ready' &&
      review.approved_ref !== review.current.candidate_commit ?
      '<p>Pendiente de aprobación humana del candidato.</p>' : '';
    const previous = review.previous.map(entry => `<li>${reviewEntry(entry)}</li>`).join('');
    return reviewEntry(review.current) + action +
      (previous ? `<h4>Candidatos anteriores</h4><ol>${previous}</ol>` : '');
  }

  function paintReview() {
    const result = node('git-review-result');
    if (!result) return;
    node('git-review-load').disabled = Boolean(reviewState.loading);
    if (reviewState.result) result.innerHTML = reviewHtml(reviewState.result);
    else result.textContent = reviewState.error || (reviewState.loading ? 'Consultando revisión…' : '');
  }

  async function loadReview(id, api) {
    const state = reviewState;
    if (state.loading) return;
    Object.assign(state, {loading:true,result:null,error:''});
    paintReview();
    try {
      state.result = await api(`/api/tasks/${encodeURIComponent(id)}/review-handoff`);
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      if (state === reviewState) paintReview();
    }
  }

  function evidenceHtml(data) {
    if (data.status === 'pending') return '<p>La tarea todavía carece de un cierre verificado.</p>';
    const {artifact, receipt} = data;
    const total = receipt.total === 1 ? '1 caso' : escape(receipt.total) + ' casos';
    const files = receipt.granularity === 'file' ? '<h4>Archivos del oráculo</h4><ul>' +
      receipt.files.map(file => `<li><code>${escape(file.path)}</code> · ${escape(file.executed)} ejecutados · ${escape(file.skipped)} omitidos</li>`).join('') + '</ul>' : '';
    return `<dl>
      <dt>Commit consultado de main</dt><dd><code>${escape(data.observed_commit)}</code></dd>
      <dt>Commit probado</dt><dd><code>${escape(data.tested_commit)}</code></dd>
      <dt>SHA aprobado</dt><dd><code>${escape(data.approved_ref)}</code></dd>
      <dt>Recibo Git</dt><dd><code>${escape(artifact.path)}</code></dd>
      <dt>Huella del recibo</dt><dd><code>${escape(artifact.sha256)}</code></dd>
      <dt>Ejecutor</dt><dd>${escape(receipt.runner)}</dd>
      <dt>Casos del oráculo</dt><dd>${total}</dd>
      ${data.acceptance ? `<dt>Pasadas de aceptación</dt><dd>${escape(data.acceptance.passes)}</dd>
      <dt>Obligaciones de aceptación</dt><dd>${escape(data.acceptance.checks)}</dd>` : ''}
    </dl>${files}<p>Detalle por caso no registrado</p>`;
  }

  function paintEvidence() {
    const result = node('git-evidence-result');
    if (!result) return;
    node('git-evidence-load').disabled = Boolean(evidenceState.loading);
    if (evidenceState.result) result.innerHTML = evidenceHtml(evidenceState.result);
    else result.textContent = evidenceState.error || (evidenceState.loading ? 'Consultando evidencia…' : '');
  }

  async function loadEvidence(id, api) {
    const state = evidenceState;
    if (state.loading) return;
    Object.assign(state,{loading:true,result:null,error:''});
    paintEvidence();
    try {
      state.result = await api('/api/tasks/' + encodeURIComponent(id) + '/evidence');
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      if (state === evidenceState) paintEvidence();
    }
  }

  function acceptanceHtml(task) {
    if (task.status !== 'in_progress' && task.status !== 'done') return '';
    return `<section id="git-acceptance" aria-labelledby="git-acceptance-heading" hidden>
      <h3 id="git-acceptance-heading">Aceptación de la entrega</h3>
      <p id="git-acceptance-commit"></p>
      <p id="git-acceptance-result" role="status" aria-live="polite"></p>
      <button type="button" class="btn btn-primary" id="git-acceptance-start" hidden>Verificar aceptación y cerrar</button>
      <button type="button" class="btn" id="git-acceptance-check">Consultar estado</button>
    </section>`;
  }

  function acceptanceMessage(result) {
    if (!result) return '';
    if (result.state === 'running') return 'Verificando la aceptación.';
    if (result.state === 'failed') return `Aceptación fallida para ${result.tested_commit}. ${result.error_code}`;
    if (result.state === 'done') return `Cierre confirmado en Git. ${result.closed_commit}`;
    return 'Pendiente de ejecutar la aceptación.';
  }

  function paintAcceptance(task) {
    const section = node('git-acceptance');
    if (!section || !['in_progress','done'].includes(task.status)) return;
    const {result, loading, error} = acceptanceState;
    section.hidden = !result?.requires_acceptance && !error;
    const start = node('git-acceptance-start');
    start.hidden = !result?.requires_acceptance || task.status !== 'in_progress' ||
      result.state === 'running' || result.state === 'done';
    start.disabled = Boolean(loading || error);
    node('git-acceptance-check').disabled = Boolean(loading);
    const tested = result && (start.hidden ? result.tested_commit : result.observed_commit);
    node('git-acceptance-commit').textContent = tested ? `Commit de aceptación: ${tested}` : '';
    node('git-acceptance-result').textContent = error || acceptanceMessage(result);

    const select = node('git-next-status');
    const legacyFinish = select?.querySelector?.('option[value="done"]');
    if (legacyFinish && result?.requires_acceptance) {
      legacyFinish.disabled = true;
      if (select.value === 'done') {
        select.value = 'needs_human_input';
        updateFields(task);
      }
    }
  }

  async function loadAcceptance(task,api,refresh,start=false) {
    const state = acceptanceState;
    if (state.loading) return;
    state.loading = true;
    state.requestedStatus = task.status;
    state.error = '';
    paintAcceptance(task);
    const url = '/api/tasks/' + encodeURIComponent(task.id) + '/acceptance';
    try {
      const previous = state.result;
      const result = start ? await api(url,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({tested_commit:previous.observed_commit,
          ...(previous.state === 'failed' && previous.tested_commit === previous.observed_commit ? {retry:true} : {})}),
      }) : await api(url);
      state.result = result;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      if (state === acceptanceState) paintAcceptance(task);
    }
    if (state === acceptanceState && task.status !== 'done' && state.result?.state === 'done') await refresh();
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
        ${acceptanceHtml(detail)}
        <section aria-labelledby="git-review-heading">
          <h3 id="git-review-heading">Revisión del candidato</h3>
          <button type="button" class="btn" id="git-review-load">Consultar revisión</button>
          <div id="git-review-result" aria-live="polite"></div>
        </section>
        <section aria-labelledby="git-evidence-heading">
          <h3 id="git-evidence-heading">Evidencia de la tarea</h3>
          <button type="button" class="btn" id="git-evidence-load">Consultar evidencia</button>
          <div id="git-evidence-result" aria-live="polite"></div>
        </section>
        <h3>Historial de commits</h3><ol>${journalHtml(detail)}</ol></section>`;
  }

  async function render(task,api,refresh) {
    const fields = ['git-approved-ref','git-assignee','git-reason','git-next-status'];
    if (selectedId === task.id && (pending || fields.some(id=>node(id) === document.activeElement))) return;
    const opening = node('view-task-detail')?.classList?.contains?.('hidden');
    if (selectedId !== task.id) {
      reviewState = {};
      evidenceState = {};
      acceptanceState = {};
    }
    selectedId = task.id;
    try {
      const detail = task.journal ? task : await api(`/api/tasks/${encodeURIComponent(task.id)}`);
      if (selectedId !== task.id) return;
      // A read already in flight must not replace a field focused while it awaited Git.
      if (pending || fields.some(id=>node(id) === document.activeElement)) return;
      node('workspace-container').innerHTML = taskHtml(detail);
      node('git-back').onclick = () => window.switchView('board');
      node('git-review-load').onclick = () => loadReview(task.id, api);
      paintReview();
      const evidenceButton = node('git-evidence-load');
      if (evidenceButton) evidenceButton.onclick = () => loadEvidence(task.id, api);
      paintEvidence();
      if (['in_progress','done'].includes(detail.status)) {
        node('git-acceptance-start').onclick = () => loadAcceptance(detail,api,refresh,true);
        node('git-acceptance-check').onclick = () => loadAcceptance(detail,api,refresh);
        paintAcceptance(detail);
        if (opening || acceptanceState.requestedStatus !== detail.status) {
          void loadAcceptance(detail,api,refresh);
        }
      }
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
