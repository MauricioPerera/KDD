// KDD-Board Client Application

let currentTasks = [];
let selectedTaskId = null;
let activeView = 'board';

// DOM Elements
const cols = {
  backlog: document.getElementById('col-backlog'),
  ready: document.getElementById('col-ready'),
  in_progress: document.getElementById('col-in_progress'),
  needs_human_input: document.getElementById('col-needs_human_input'),
  done: document.getElementById('col-done'),
};

const counts = {
  backlog: document.getElementById('count-backlog'),
  ready: document.getElementById('count-ready'),
  in_progress: document.getElementById('count-in_progress'),
  needs_human_input: document.getElementById('count-needs_human_input'),
  done: document.getElementById('count-done'),
};

// Modals
const modalNewTask = document.getElementById('modal-new-task');
const modalVault = document.getElementById('modal-vault');
const modalAgentTools = document.getElementById('modal-agent-tools');

// Header Buttons
document.getElementById('btn-new-task').addEventListener('click', () => openModal(modalNewTask));
document.getElementById('btn-open-vault').addEventListener('click', () => {
  openModal(modalVault);
  loadVault();
});
document.getElementById('btn-agent-tools').addEventListener('click', () => {
  openModal(modalAgentTools);
  loadTools();
});

// View Navigation Tabs
document.getElementById('tab-board').addEventListener('click', () => switchView('board'));
document.getElementById('tab-dashboard').addEventListener('click', () => switchView('dashboard'));
document.getElementById('tab-docs').addEventListener('click', () => switchView('docs'));
document.getElementById('tab-task').addEventListener('click', () => {
  if (selectedTaskId) switchView('task');
});

window.switchView = function (viewName) {
  activeView = viewName;
  document.getElementById('tab-board').classList.toggle('active', viewName === 'board');
  document.getElementById('tab-dashboard').classList.toggle('active', viewName === 'dashboard');
  document.getElementById('tab-docs').classList.toggle('active', viewName === 'docs');
  const tabTask = document.getElementById('tab-task');
  tabTask.classList.toggle('active', viewName === 'task');
  tabTask.classList.toggle('hidden', viewName !== 'task' && !selectedTaskId);

  document.getElementById('view-board').classList.toggle('hidden', viewName !== 'board');
  document.getElementById('view-dashboard').classList.toggle('hidden', viewName !== 'dashboard');
  document.getElementById('view-task-detail').classList.toggle('hidden', viewName !== 'task');
  document.getElementById('view-docs').classList.toggle('hidden', viewName !== 'docs');

  if (viewName === 'dashboard') {
    renderDashboard();
  }
  if (viewName === 'docs') {
    initDocsView();
  }
};

// Close buttons
document.querySelectorAll('[data-close]').forEach((btn) => {
  btn.addEventListener('click', () => {
    closeAllModals();
  });
});

function openModal(modal) {
  modal.classList.remove('hidden');
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach((m) => m.classList.add('hidden'));
}

// 1. Fetch & Render Tasks
async function loadTasks() {
  try {
    const res = await fetch('/api/tasks');
    currentTasks = await res.json();
    renderBoard();
    if (activeView === 'dashboard') {
      renderDashboard();
    }
    if (activeView === 'task' && selectedTaskId) {
      renderTaskWorkspace(selectedTaskId);
    }
  } catch (err) {
    console.error('Error cargando tareas:', err);
  }
}

function renderBoard() {
  Object.values(cols).forEach((el) => (el.innerHTML = ''));
  const tally = { backlog: 0, ready: 0, in_progress: 0, needs_human_input: 0, done: 0 };

  for (const task of currentTasks) {
    tally[task.status] = (tally[task.status] || 0) + 1;
    const card = document.createElement('div');
    card.className = 'task-card';
    card.onclick = () => openTaskDetail(task.id);

    const pendingReqs = task.requirements?.filter((r) => !r.isSatisfied) || [];

    card.innerHTML = `
      <div class="card-header-row">
        <span class="task-title">${escapeHtml(task.title)}</span>
        <span class="priority-tag priority-${task.priority}">${task.priority}</span>
      </div>
      <p class="task-desc">${escapeHtml(task.description || 'Sin descripción.')}</p>
      ${
        pendingReqs.length > 0
          ? `<div class="req-pill">🛑 Requiere: ${escapeHtml(pendingReqs[0].label)}</div>`
          : ''
      }
      ${
        task.contractId
          ? `<div class="contract-pill" onclick="event.stopPropagation(); window.goToContract('${escapeHtml(task.contractId)}')">📜 ${escapeHtml(task.contractId.replace(/^app-|^core-|^spec-/, ''))}</div>`
          : ''
      }
      <div class="card-footer">
        <span class="assignee-badge assignee-${task.assignee}">
          ${task.assignee === 'agent' ? '🤖 Agente' : task.assignee === 'human' ? '👤 Humano' : '⚪ Libre'}
        </span>
        <span style="color:var(--text-dim); font-family:var(--font-mono); font-size:0.7rem;">
          ${new Date(task.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    `;

    if (cols[task.status]) {
      cols[task.status].appendChild(card);
    }
  }

  Object.keys(counts).forEach((st) => {
    counts[st].textContent = tally[st] || 0;
  });
}

// 2. Create Task
document.getElementById('form-new-task').addEventListener('submit', async (e) => {
  e.preventDefault();
  const title = document.getElementById('task-title').value.trim();
  const description = document.getElementById('task-desc').value.trim();
  const assignee = document.getElementById('task-assignee').value;
  const priority = document.getElementById('task-priority').value;
  const contractId = document.getElementById('task-contract').value || undefined;

  try {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, assignee, priority, contractId }),
    });
    if (!res.ok) throw new Error('Error al crear tarea');
    closeAllModals();
    document.getElementById('form-new-task').reset();
    await loadTasks();
  } catch (err) {
    alert(err.message);
  }
});

// 3. Open Task Detail (Switches to Dedicated Workspace)
window.openTaskDetail = function (taskId) {
  selectedTaskId = taskId;
  renderTaskWorkspace(taskId);
  switchView('task');
};

function renderTaskWorkspace(taskId) {
  const task = currentTasks.find((t) => t.id === taskId);
  if (!task) return;

  const container = document.getElementById('workspace-container');
  const pendingReqs = task.requirements?.filter((r) => !r.isSatisfied) || [];

  container.innerHTML = `
    <!-- Top Bar with Back Link -->
    <div class="workspace-top-row">
      <div style="display:flex; align-items:center; gap:0.75rem;">
        <button type="button" class="btn-back-board" onclick="switchView('board')">
          &larr; Volver al Tablero
        </button>
        <span style="color:var(--text-dim); font-size:0.85rem;">/</span>
        <span style="font-family:var(--font-mono); font-size:0.82rem; color:var(--text-muted);">${task.id}</span>
      </div>
      <div style="display:flex; align-items:center; gap:0.6rem;">
        <span class="priority-tag priority-${task.priority}">${task.priority}</span>
        <span class="assignee-badge assignee-${task.assignee}">
          ${task.assignee === 'agent' ? '🤖 Agente' : task.assignee === 'human' ? '👤 Humano' : '⚪ Libre'}
        </span>
      </div>
    </div>

    <!-- Workspace 2-Column Grid -->
    <div class="workspace-grid">
      <!-- Main Content Area -->
      <div class="workspace-main">
        <!-- Title & Description Box -->
        <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:8px; padding:1.4rem;">
          <h2 style="font-size:1.4rem; font-weight:700; margin-bottom:0.6rem; color:var(--text-main);">${escapeHtml(task.title)}</h2>
          <p style="color:var(--text-muted); font-size:0.95rem; line-height:1.6;">${escapeHtml(task.description || 'Sin descripción.')}</p>
        </div>

        <!-- Contrato KDD Vinculado Banner -->
        ${
          task.contractId
            ? `
            <div style="background:rgba(95,179,172,0.1); border:1px solid rgba(95,179,172,0.35); border-radius:8px; padding:0.9rem 1.25rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem;">
              <div style="display:flex; align-items:center; gap:0.6rem;">
                <span style="font-size:1.25rem;">📜</span>
                <div>
                  <span style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-dim); text-transform:uppercase; letter-spacing:0.05em;">Contrato KDD Vinculado</span>
                  <div style="font-size:0.95rem; font-weight:600; color:var(--accent-cyan); font-family:var(--font-mono); margin-top:0.1rem;">
                    ${escapeHtml(task.contractId)}
                  </div>
                </div>
              </div>
              <button type="button" class="btn" style="color:var(--accent-cyan); border-color:rgba(95,179,172,0.5); font-size:0.82rem; padding:0.35rem 0.8rem;" onclick="window.goToContract('${escapeHtml(task.contractId)}')">
                👁️ Ver Contrato KDD en 1 Clic &rarr;
              </button>
            </div>
          `
            : `
            <div style="background:rgba(255,255,255,0.02); border:1px dashed var(--border-subtle); border-radius:8px; padding:0.75rem 1.25rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem;">
              <span style="font-size:0.84rem; color:var(--text-muted);">Sin contrato KDD vinculado a esta tarea</span>
              <div style="display:flex; gap:0.5rem; align-items:center;">
                <select id="workspace-link-contract-select" style="font-size:0.8rem; padding:0.3rem 0.6rem;">
                  <option value="">-- Seleccionar contrato KDD --</option>
                  ${docsCatalog
                    .filter((d) => d.isContract)
                    .map((d) => `<option value="${d.id}">${escapeHtml(d.title)}</option>`)
                    .join('')}
                </select>
                <button type="button" class="btn btn-primary" style="font-size:0.8rem; padding:0.3rem 0.75rem;" onclick="window.linkTaskContract('${task.id}')">
                  Vincular Contrato
                </button>
              </div>
            </div>
          `
        }

        <!-- Pending Requirements & Blind Vault Section -->
        ${
          pendingReqs.length > 0
            ? `
            <div style="background:rgba(244, 63, 94, 0.08); border:1px solid rgba(244, 63, 94, 0.35); border-radius:8px; padding:1.25rem;">
              <div style="display:flex; align-items:center; gap:0.5rem; color:var(--accent-rose); font-weight:600; font-size:0.98rem; margin-bottom:0.75rem;">
                🛑 Requerimientos Solicitados por el Agente:
              </div>
              ${pendingReqs
                .map(
                  (r) => `
                <div style="background:var(--bg-column); border:1px solid var(--border-subtle); border-radius:6px; padding:1rem; margin-top:0.75rem;">
                  <p style="font-size:0.92rem; font-weight:600; color:var(--text-main);">${escapeHtml(r.label)} (<code>${escapeHtml(r.fieldKey)}</code>)</p>
                  <p style="font-size:0.84rem; color:var(--text-muted); margin:0.3rem 0 0.75rem;">${escapeHtml(r.description)}</p>
                  <div style="display:flex; gap:0.75rem; flex-wrap:wrap;">
                    <input
                      type="${r.isSecret ? 'password' : 'text'}"
                      id="workspace-input-req-${r.fieldKey}"
                      placeholder="${r.isSecret ? 'Escribe el valor secreto (Blind Vault)...' : 'Escribe el valor solicitado...'}"
                      style="flex:1; min-width:240px;"
                    />
                    <button type="button" class="btn btn-primary" onclick="fulfillRequirement('${task.id}', '${r.fieldKey}', ${r.isSecret})">
                      ${r.isSecret ? '🔒 Guardar Secreto Ciego' : 'Enviar Respuesta'}
                    </button>
                  </div>
                  ${
                    r.isSecret
                      ? `<p style="font-size:0.75rem; color:var(--accent-cyan); margin-top:0.5rem;">
                          🔒 <strong>Blind Security:</strong> El valor se guardará en <code>.env.local</code>. El agente sabrá que existe pero nunca podrá leerlo en texto claro.
                        </p>`
                      : ''
                  }
                </div>
              `
                )
                .join('')}
            </div>
          `
            : ''
        }

        <!-- KDD Verification & Test Battery Section -->
        <div class="report-section">
          <div class="report-header-row">
            <div>
              <span style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-dim); text-transform:uppercase; letter-spacing:0.06em;">Verificación KDD</span>
              <h4 style="font-size:1.05rem; font-weight:600; color:var(--text-main); margin-top:0.1rem;">Batería de Pruebas &amp; Métricas</h4>
            </div>
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
              <button type="button" class="btn-run-tests" id="btn-run-task-tests" onclick="runTaskTests('${task.id}')">
                ▶ Ejecutar Tests de Tarea
              </button>
              <button type="button" class="btn" id="btn-generate-kdd-report" style="border-color:var(--accent-cyan); color:var(--accent-cyan); font-size:0.8rem; padding:0.45rem 0.85rem;" onclick="generateTaskKddReport('${task.id}')">
                📝 Generar Reporte KDD (.agents/logs)
              </button>
            </div>
          </div>

          <!-- KPI Metrics Cards -->
          <div class="metrics-kpi-grid">
            <div class="kpi-card">
              <span class="kpi-label">Estado</span>
              <span class="kpi-val ${task.testReport ? (task.testReport.success ? 'success' : 'failed') : ''}">
                ${task.testReport ? (task.testReport.success ? 'PASÓ ✓' : 'FALLÓ ✖') : 'SIN CORRER'}
              </span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Tests Pasados</span>
              <span class="kpi-val success">${task.testReport ? task.testReport.passedTests : '-'}</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Tests Fallados</span>
              <span class="kpi-val ${task.testReport?.failedTests ? 'failed' : ''}">${task.testReport ? task.testReport.failedTests : '-'}</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Duración</span>
              <span class="kpi-val">${task.testReport ? task.testReport.durationMs.toFixed(1) + 'ms' : '-'}</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Requerimientos</span>
              <span class="kpi-val">${task.requirements?.filter((r) => r.isSatisfied).length || 0}/${task.requirements?.length || 0}</span>
            </div>
          </div>

          <!-- Test Output Terminal -->
          <div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;">
              <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted);">Comando: <code>${escapeHtml(task.testCommand || 'npm test')}</code></span>
              ${task.testReport ? `<span style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-dim);">Última corrida: ${new Date(task.testReport.lastRun).toLocaleTimeString()}</span>` : ''}
            </div>
            <pre class="test-terminal">${task.testReport ? escapeHtml(task.testReport.output) : 'No se ha ejecutado la batería de pruebas para esta tarea aún.\nHaz clic en "▶ Ejecutar Tests de Tarea" para correr los tests reales y generar el reporte.'}</pre>
            ${
              task.testReport?.reportPath
                ? `
              <div style="margin-top:0.75rem; background:rgba(95,179,172,0.1); border:1px solid rgba(95,179,172,0.28); border-radius:6px; padding:0.6rem 0.9rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <span style="font-size:0.8rem; color:var(--accent-cyan);">
                  📄 <strong>Reporte KDD Verificado:</strong> <code style="color:var(--text-main); font-family:var(--font-mono);">${escapeHtml(task.testReport.reportPath)}</code>
                </span>
                <span class="status-badge" style="background:rgba(16,185,129,0.15); color:var(--accent-emerald); border:1px solid rgba(16,185,129,0.3); font-size:0.72rem; padding:0.15rem 0.5rem; border-radius:4px; font-family:var(--font-mono);">
                  CICLO KDD: VERIFIED ✓
                </span>
              </div>
            `
                : ''
            }
          </div>
        </div>
      </div>

      <!-- Right Column: Meta & Audit -->
      <div class="workspace-sidebar">
        <!-- Controls Box -->
        <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:8px; padding:1.1rem; display:flex; flex-direction:column; gap:0.9rem;">
          <div>
            <label style="font-size:0.78rem; color:var(--text-muted); font-weight:600; text-transform:uppercase;">Estado en Tablero:</label>
            <select id="workspace-select-status" style="width:100%; margin-top:0.35rem;">
              <option value="backlog" ${task.status === 'backlog' ? 'selected' : ''}>📋 Backlog</option>
              <option value="ready" ${task.status === 'ready' ? 'selected' : ''}>⚡ Ready for Agent</option>
              <option value="in_progress" ${task.status === 'in_progress' ? 'selected' : ''}>🔄 In Progress</option>
              <option value="needs_human_input" ${task.status === 'needs_human_input' ? 'selected' : ''}>🛑 Needs Human Input</option>
              <option value="done" ${task.status === 'done' ? 'selected' : ''}>✅ Done</option>
            </select>
          </div>
          <div>
            <label style="font-size:0.78rem; color:var(--text-muted); font-weight:600; text-transform:uppercase;">Asignado a:</label>
            <select id="workspace-select-assignee" style="width:100%; margin-top:0.35rem;">
              <option value="unassigned" ${task.assignee === 'unassigned' ? 'selected' : ''}>⚪ Sin asignar</option>
              <option value="agent" ${task.assignee === 'agent' ? 'selected' : ''}>🤖 Agente (AI)</option>
              <option value="human" ${task.assignee === 'human' ? 'selected' : ''}>👤 Humano</option>
            </select>
          </div>
        </div>

        <!-- Audit & Comments Trail -->
        <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:8px; padding:1.1rem; display:flex; flex-direction:column; gap:0.75rem;">
          <label style="font-size:0.78rem; color:var(--text-muted); font-weight:600; text-transform:uppercase;">Historial de Auditoría:</label>
          <div style="max-height:360px; overflow-y:auto; display:flex; flex-direction:column; gap:0.5rem; padding-right:0.3rem;">
            ${(task.comments || [])
              .map(
                (c) => `
              <div style="background:var(--bg-column); padding:0.55rem 0.75rem; border-radius:5px; font-size:0.8rem; border-left:3px solid ${c.author === 'agent' ? 'var(--accent-purple)' : c.author === 'human' ? 'var(--accent-orange)' : 'var(--text-dim)'};">
                <div style="display:flex; justify-content:space-between; margin-bottom:0.2rem;">
                  <strong style="color:${c.author === 'agent' ? 'var(--accent-purple)' : c.author === 'human' ? 'var(--accent-orange)' : 'var(--text-muted)'}; font-family:var(--font-mono); font-size:0.72rem;">${c.author.toUpperCase()}</strong>
                  <span style="color:var(--text-dim); font-size:0.68rem;">${new Date(c.timestamp).toLocaleTimeString()}</span>
                </div>
                <p style="margin:0; color:var(--text-main); font-size:0.8rem; line-height:1.4;">${escapeHtml(c.text)}</p>
              </div>
            `
              )
              .join('')}
          </div>
        </div>
      </div>
    </div>
  `;

  document.getElementById('workspace-select-status').onchange = async (e) => {
    await updateStatus(task.id, e.target.value);
  };
  document.getElementById('workspace-select-assignee').onchange = async (e) => {
    await updateAssignee(task.id, e.target.value);
  };
}

// 4. Update Status & Assignee
async function updateStatus(taskId, status) {
  try {
    const res = await fetch(`/api/tasks/${taskId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, comment: { author: 'human', text: `Estado actualizado a ${status}` } }),
    });
    if (!res.ok) throw new Error('Error al actualizar estado');
    await loadTasks();
  } catch (err) {
    alert(err.message);
  }
}

async function updateAssignee(taskId, assignee) {
  try {
    const res = await fetch(`/api/tasks/${taskId}/assign`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assignee }),
    });
    if (!res.ok) throw new Error('Error al asignar tarea');
    await loadTasks();
  } catch (err) {
    alert(err.message);
  }
}

// 5. Fulfill Requirement (Blind Secret)
window.fulfillRequirement = async function (taskId, fieldKey, isSecret) {
  const inputEl = document.getElementById(`workspace-input-req-${fieldKey}`) || document.getElementById(`input-req-${fieldKey}`);
  const val = inputEl?.value?.trim();
  if (!val) {
    alert('Por favor introduce un valor antes de enviar.');
    return;
  }

  try {
    const payload = isSecret
      ? { fieldKey, secretValue: val }
      : { fieldKey, value: val };

    const res = await fetch(`/api/tasks/${taskId}/fulfill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Error al guardar requerimiento');
    alert(isSecret ? '¡Credencial guardada de forma segura en .env.local! La tarea fue reasignada al Agente.' : '¡Respuesta guardada!');
    await loadTasks();
  } catch (err) {
    alert(err.message);
  }
};

// 6. Run Task Tests & Generate KDD Report
window.runTaskTests = async function (taskId) {
  const btn = document.getElementById('btn-run-task-tests');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Ejecutando tests...';
  }

  try {
    const res = await fetch(`/api/tasks/${taskId}/run-tests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Error al ejecutar tests');
    }
    await loadTasks();
  } catch (err) {
    alert('Error ejecutando tests: ' + err.message);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '▶ Ejecutar Tests de Tarea';
    }
  }
};

window.generateTaskKddReport = async function (taskId) {
  const btn = document.getElementById('btn-generate-kdd-report');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Generando reporte...';
  }

  try {
    const res = await fetch(`/api/tasks/${taskId}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al generar reporte KDD');
    await loadTasks();
    renderTaskWorkspace(taskId);
    alert(`✓ Reporte KDD generado exitosamente en:\n${data.relativePath}\n\nLa tarea ha alcanzado el estado VERIFIED.`);
  } catch (err) {
    alert('Error generando reporte KDD: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '📝 Generar Reporte KDD (.agents/logs)';
    }
  }
};

// 7. Render Project Dashboard
async function renderDashboard() {
  const total = currentTasks.length;
  const doneCount = currentTasks.filter((t) => t.status === 'done').length;
  const readyCount = currentTasks.filter((t) => t.status === 'ready').length;

  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;
  document.getElementById('dash-pct-text').textContent = `${pct}%`;
  document.getElementById('dash-progress-bar').style.width = `${pct}%`;
  document.getElementById('dash-progress-summary').textContent = `${doneCount} de ${total} tareas completadas`;
  document.getElementById('dash-ready-summary').textContent = `${readyCount} listas para agente`;

  document.getElementById('dash-kpi-total').textContent = total;
  document.getElementById('dash-kpi-total-sub').textContent = `${doneCount} terminadas, ${total - doneCount} activas`;

  const agentTasks = currentTasks.filter((t) => t.assignee === 'agent').length;
  const humanTasks = currentTasks.filter((t) => t.assignee === 'human').length;
  document.getElementById('dash-kpi-workload').textContent = `${agentTasks} / ${humanTasks}`;

  const testedTasks = currentTasks.filter((t) => t.testReport?.success === true).length;
  const testPct = total > 0 ? Math.round((testedTasks / total) * 100) : 0;
  document.getElementById('dash-kpi-tests').textContent = `${testPct}%`;
  document.getElementById('dash-kpi-tests-sub').textContent = `${testedTasks} de ${total} verificadas`;

  try {
    const vaultRes = await fetch('/api/vault');
    const vaultData = await vaultRes.json();
    document.getElementById('dash-kpi-vault').textContent = vaultData.length;
  } catch {
    document.getElementById('dash-kpi-vault').textContent = '-';
  }

  // Column breakdown
  const statusLabels = {
    backlog: { name: '📋 Backlog', color: 'var(--text-muted)' },
    ready: { name: '⚡ Ready for Agent', color: 'var(--accent-purple)' },
    in_progress: { name: '🔄 In Progress', color: 'var(--accent-cyan)' },
    needs_human_input: { name: '🛑 Needs Human Input', color: 'var(--accent-rose)' },
    done: { name: '✅ Done', color: 'var(--accent-emerald)' },
  };
  const breakdownContainer = document.getElementById('dash-status-breakdown');
  breakdownContainer.innerHTML = Object.entries(statusLabels)
    .map(([st, info]) => {
      const count = currentTasks.filter((t) => t.status === st).length;
      const barPct = total > 0 ? (count / total) * 100 : 0;
      return `
      <div>
        <div style="display:flex; justify-content:space-between; font-size:0.82rem; margin-bottom:0.25rem;">
          <span style="color:${info.color}; font-weight:600;">${info.name}</span>
          <span style="font-family:var(--font-mono);">${count} (${Math.round(barPct)}%)</span>
        </div>
        <div style="background:rgba(0,0,0,0.3); height:6px; border-radius:3px; overflow:hidden;">
          <div style="background:${info.color}; height:100%; width:${barPct}%;"></div>
        </div>
      </div>
    `;
    })
    .join('');

  // Blocked / Urgent tasks
  const blockedList = currentTasks.filter((t) => t.status === 'needs_human_input' || t.priority === 'urgent');
  const blockedContainer = document.getElementById('dash-blocked-list');
  if (blockedList.length === 0) {
    blockedContainer.innerHTML =
      '<span style="color:var(--text-dim); font-size:0.85rem; font-style:italic;">No hay tareas bloqueadas actualmente. ¡Flujo KDD despejado!</span>';
  } else {
    blockedContainer.innerHTML = blockedList
      .map(
        (t) => `
      <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:6px; padding:0.65rem 0.85rem; display:flex; justify-content:space-between; align-items:center; cursor:pointer;" onclick="openTaskDetail('${t.id}')">
        <div>
          <strong style="font-size:0.86rem; color:var(--text-main); display:block;">${escapeHtml(t.title)}</strong>
          <span style="font-size:0.75rem; color:var(--accent-rose);">${t.status === 'needs_human_input' ? '🛑 Requiere entrada humana' : '🔥 Prioridad Urgente'}</span>
        </div>
        <span class="btn" style="font-size:0.75rem; padding:0.25rem 0.55rem;">Ver Tarea →</span>
      </div>
    `
      )
      .join('');
  }
}

// 8. Blind Vault View & Management
let isEditingVaultKey = null;

async function loadVault() {
  const container = document.getElementById('vault-list-container');
  try {
    const res = await fetch('/api/vault');
    const secrets = await res.json();
    if (secrets.length === 0) {
      container.innerHTML =
        '<span style="color:var(--text-dim); font-size:0.85rem; font-style:italic;">No hay credenciales configuradas en .env.local todavía.</span>';
      return;
    }
    container.innerHTML = secrets
      .map(
        (s) => `
        <div class="vault-item-row" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
          <div style="display:flex; align-items:center; gap:0.75rem;">
            <span class="vault-item-key">${escapeHtml(s.key)}</span>
            <span class="vault-item-masked">${escapeHtml(s.maskedValue)}</span>
            <span style="color:var(--accent-emerald); font-size:0.72rem; font-family:var(--font-mono);">✓ is_set</span>
          </div>
          <div style="display:flex; gap:0.4rem;">
            <button type="button" class="btn" style="font-size:0.72rem; padding:0.2rem 0.5rem;" onclick="window.editVaultSecret('${escapeHtml(s.key)}')">
              ✏️ Modificar
            </button>
            <button type="button" class="btn" style="font-size:0.72rem; padding:0.2rem 0.5rem; color:var(--accent-rose); border-color:rgba(244,63,94,0.3);" onclick="window.deleteVaultSecret('${escapeHtml(s.key)}')">
              🗑️ Eliminar
            </button>
          </div>
        </div>
      `
      )
      .join('');
  } catch (err) {
    container.innerHTML = `<span style="color:var(--accent-rose);">Error cargando vault: ${err.message}</span>`;
  }
}

// Vault Form Submission
const formVaultSave = document.getElementById('form-vault-save');
if (formVaultSave) {
  formVaultSave.addEventListener('submit', async (e) => {
    e.preventDefault();
    const key = document.getElementById('vault-key').value.trim().toUpperCase();
    const value = document.getElementById('vault-val').value.trim();
    if (!key || !value) return;

    try {
      const res = await fetch('/api/vault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      });
      if (!res.ok) throw new Error('Error al guardar credencial en Vault');
      
      resetVaultForm();
      await loadVault();
      await loadTasks();
      alert(`¡Credencial "${key}" guardada correctamente en .env.local!`);
    } catch (err) {
      alert(err.message);
    }
  });
}

window.editVaultSecret = function (key) {
  isEditingVaultKey = key;
  const keyInput = document.getElementById('vault-key');
  const valInput = document.getElementById('vault-val');
  const titleEl = document.getElementById('vault-form-title');
  const cancelBtn = document.getElementById('btn-vault-cancel-edit');
  const submitBtn = document.getElementById('btn-vault-submit');

  keyInput.value = key;
  keyInput.readOnly = true;
  valInput.value = '';
  valInput.placeholder = 'Escribe el nuevo valor secreto...';
  titleEl.textContent = `✏️ Modificar Credencial: ${key}`;
  cancelBtn.style.display = 'inline-block';
  submitBtn.textContent = '💾 Actualizar Secreto';
  valInput.focus();
};

window.deleteVaultSecret = async function (key) {
  if (!confirm(`¿Estás seguro de que deseas eliminar la credencial "${key}" del Vault (.env.local)?`)) {
    return;
  }
  try {
    const res = await fetch(`/api/vault/${encodeURIComponent(key)}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Error al eliminar credencial');
    await loadVault();
    await loadTasks();
  } catch (err) {
    alert(err.message);
  }
};

const btnVaultCancel = document.getElementById('btn-vault-cancel-edit');
if (btnVaultCancel) {
  btnVaultCancel.addEventListener('click', resetVaultForm);
}

function resetVaultForm() {
  isEditingVaultKey = null;
  const form = document.getElementById('form-vault-save');
  if (form) form.reset();
  const keyInput = document.getElementById('vault-key');
  if (keyInput) keyInput.readOnly = false;
  const titleEl = document.getElementById('vault-form-title');
  if (titleEl) titleEl.textContent = '+ Agregar o Modificar Credencial';
  const cancelBtn = document.getElementById('btn-vault-cancel-edit');
  if (cancelBtn) cancelBtn.style.display = 'none';
  const submitBtn = document.getElementById('btn-vault-submit');
  if (submitBtn) submitBtn.textContent = '🔒 Guardar en Vault';
}

// 9. WebMCP Tools View
async function loadTools() {
  const container = document.getElementById('tools-list-container');
  try {
    const res = await fetch('/api/tools');
    const tools = await res.json();
    container.innerHTML = tools
      .map(
        (t) => `
        <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:6px; padding:0.8rem;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <code style="color:var(--accent-cyan); font-weight:600; font-size:0.9rem;">${escapeHtml(t.name)}()</code>
            <span style="font-size:0.7rem; font-family:var(--font-mono); color:var(--text-dim);">WebMCP Tool</span>
          </div>
          <p style="font-size:0.82rem; color:var(--text-muted); margin:0.35rem 0 0.5rem;">${escapeHtml(t.description)}</p>
        </div>
      `
      )
      .join('');
  } catch (err) {
    container.innerHTML = `<span style="color:var(--accent-rose);">Error cargando tools: ${err.message}</span>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// 10. KDD Documentation & Contracts Explorer
let docsCatalog = [];
let selectedDocId = null;

async function initDocsView() {
  if (docsCatalog.length === 0) {
    try {
      const res = await fetch('/api/docs');
      docsCatalog = await res.json();
    } catch (err) {
      console.error('Error cargando catálogo de documentación:', err);
      return;
    }
  }
  renderDocsNav();

  const searchInput = document.getElementById('docs-search-input');
  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = 'true';
    searchInput.addEventListener('input', (e) => {
      renderDocsNav(e.target.value.toLowerCase().trim());
    });
  }

  const btnVal = document.getElementById('btn-validate-all-contracts');
  if (btnVal && !btnVal.dataset.bound) {
    btnVal.dataset.bound = 'true';
    btnVal.addEventListener('click', runAllContractsValidation);
  }

  if (!selectedDocId && docsCatalog.length > 0) {
    const defaultDoc = docsCatalog.find((d) => d.id === 'project-definition') || docsCatalog[0];
    loadDocItem(defaultDoc.id);
  }
}

function renderDocsNav(filter = '') {
  const container = document.getElementById('docs-nav-tree');
  if (!container) return;

  const categories = [
    { key: 'definition', title: '🎯 Definición (KDD)', badge: 'ORIGEN' },
    { key: 'contracts-app', title: '📜 Contratos KDD (Proyecto)', badge: 'CONTRATOS' },
    { key: 'spec', title: '📘 Especificaciones & OKF', badge: 'SPECS' },
  ];

  let html = '';
  for (const cat of categories) {
    let items = docsCatalog.filter((d) => d.category === cat.key);
    if (filter) {
      items = items.filter((d) => d.title.toLowerCase().includes(filter) || d.filename.toLowerCase().includes(filter));
    }
    if (items.length === 0) continue;

    html += `
      <div>
        <div class="docs-group-header">
          <span>${cat.title}</span>
          <span style="font-family:var(--font-mono); font-size:0.68rem; background:rgba(255,255,255,0.06); padding:0.1rem 0.4rem; border-radius:3px;">${items.length}</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:0.25rem; margin-top:0.25rem;">
          ${items
            .map(
              (item) => `
            <div class="docs-nav-item ${item.id === selectedDocId ? 'active' : ''}" onclick="window.loadDocItem('${item.id}')">
              <span class="docs-nav-title">${escapeHtml(item.title)}</span>
              <span class="docs-nav-sub">${escapeHtml(item.filename)}</span>
            </div>
          `
            )
            .join('')}
        </div>
      </div>
    `;
  }

  container.innerHTML = html || '<span style="color:var(--text-dim); font-size:0.8rem; padding:0.5rem;">No se encontraron documentos.</span>';
}

window.loadDocItem = async function (id) {
  selectedDocId = id;
  renderDocsNav(document.getElementById('docs-search-input')?.value.toLowerCase().trim() || '');

  const pane = document.getElementById('docs-reader-pane');
  pane.innerHTML = '<span style="color:var(--text-muted); font-size:0.9rem;">Cargando documento...</span>';

  try {
    const res = await fetch(`/api/docs/item?id=${encodeURIComponent(id)}`);
    if (!res.ok) throw new Error('Error al cargar documento');
    const data = await res.json();
    const { item, body, frontmatter } = data;

    let metaCardHtml = '';
    if (frontmatter) {
      metaCardHtml = `
        <div class="contract-meta-card">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div>
              <span class="badge-kdd">${escapeHtml(frontmatter.type || 'Contrato KDD')}</span>
              <h3 style="font-size:1.15rem; font-weight:700; color:var(--text-main); margin-top:0.2rem;">${escapeHtml(frontmatter.task || item.title)}</h3>
            </div>
          </div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:0.75rem; font-size:0.82rem; font-family:var(--font-mono);">
            ${frontmatter.target ? `<div><span style="color:var(--text-dim);">Target:</span> <code style="color:var(--accent-orange);">${escapeHtml(frontmatter.target)}</code></div>` : ''}
            ${frontmatter.signature ? `<div><span style="color:var(--text-dim);">Signature:</span> <code style="color:var(--accent-cyan);">${escapeHtml(frontmatter.signature)}</code></div>` : ''}
            ${frontmatter.test_command ? `<div><span style="color:var(--text-dim);">Oracle Test:</span> <code>${escapeHtml(frontmatter.test_command)}</code></div>` : ''}
          </div>
          ${
            frontmatter.budget
              ? `<div style="display:flex; gap:0.6rem; flex-wrap:wrap; font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted); background:rgba(0,0,0,0.25); padding:0.4rem 0.6rem; border-radius:4px;">
                  <span>Budget:</span>
                  ${typeof frontmatter.budget === 'object' ? Object.entries(frontmatter.budget).map(([k, v]) => `<span>${k}: <strong>${v}</strong></span>`).join(' &bull; ') : `<span>${frontmatter.budget}</span>`}
                </div>`
              : ''
          }
        </div>
      `;
    }

    // Associated Kanban Tasks in this Contract
    const linkedTasks = currentTasks.filter((t) => t.contractId === id);
    const linkedTasksHtml = `
      <div class="report-section" style="margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
          <h4 style="font-size:0.95rem; font-weight:600; color:var(--text-main);">📋 Tareas Asociadas en el Tablero (${linkedTasks.length})</h4>
          <button type="button" class="btn btn-primary" style="font-size:0.75rem; padding:0.25rem 0.65rem;" onclick="window.createTaskForContract('${escapeHtml(id)}')">
            + Crear Tarea para este Contrato
          </button>
        </div>
        ${
          linkedTasks.length > 0
            ? `
          <div style="display:flex; flex-direction:column; gap:0.5rem; margin-top:0.6rem;">
            ${linkedTasks
              .map(
                (t) => `
              <div style="background:var(--bg-column); border:1px solid var(--border-subtle); border-radius:6px; padding:0.6rem 0.85rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <div style="display:flex; align-items:center; gap:0.6rem;">
                  <span class="status-badge" style="font-size:0.72rem; padding:0.15rem 0.45rem; border-radius:3px; font-family:var(--font-mono); text-transform:uppercase; background:rgba(255,255,255,0.05);">
                    ${escapeHtml(t.status)}
                  </span>
                  <strong style="font-size:0.86rem; color:var(--text-main);">${escapeHtml(t.title)}</strong>
                </div>
                <button type="button" class="btn" style="font-size:0.75rem; padding:0.25rem 0.65rem; color:var(--accent-orange); border-color:var(--accent-orange);" onclick="window.goToTask('${t.id}')">
                  Ir a la Tarea en 1 Clic &rarr;
                </button>
              </div>
            `
              )
              .join('')}
          </div>
        `
            : `
          <span style="font-size:0.82rem; color:var(--text-dim); margin-top:0.4rem; font-style:italic;">No hay tareas vinculadas a este documento aún. Puedes crear una con el botón superior.</span>
        `
        }
      </div>
    `;

    pane.innerHTML = `
      <div style="margin-bottom:1.5rem; border-bottom:1px solid var(--border-subtle); padding-bottom:1rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.4rem;">
          <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-dim);">${escapeHtml(item.path)}</span>
          <span class="status-badge" style="background:rgba(95,179,172,0.15); color:var(--accent-cyan); border:1px solid rgba(95,179,172,0.3); font-size:0.72rem; padding:0.2rem 0.5rem; border-radius:4px; font-family:var(--font-mono);">
            ${item.isContract ? 'CONTRATO OKF-CCDD' : item.id === 'project-definition' ? '🎯 DEFINICIÓN KDD (PREVIO A PLAN)' : 'ESPECIFICACIÓN KDD'}
          </span>
        </div>
      </div>
      ${metaCardHtml}
      ${item.id !== 'project-definition' ? linkedTasksHtml : ''}
      <article class="markdown-rendered">
        ${renderMarkdown(body)}
      </article>
    `;
  } catch (err) {
    pane.innerHTML = `<span style="color:var(--accent-rose);">Error: ${err.message}</span>`;
  }
};

// 1-Click Navigation Helpers
window.goToContract = function (contractId) {
  switchView('docs');
  loadDocItem(contractId);
};

window.goToTask = function (taskId) {
  openTaskDetail(taskId);
};

window.createTaskForContract = function (contractId) {
  openModal(modalNewTask);
  const sel = document.getElementById('task-contract');
  if (sel) sel.value = contractId;
};

window.linkTaskContract = async function (taskId) {
  const sel = document.getElementById('workspace-link-contract-select');
  const contractId = sel?.value;
  if (!contractId) {
    alert('Por favor selecciona un contrato.');
    return;
  }
  try {
    const res = await fetch(`/api/tasks/${taskId}/contract`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contractId }),
    });
    if (!res.ok) throw new Error('Error al vincular contrato');
    await loadTasks();
    renderTaskWorkspace(taskId);
  } catch (err) {
    alert(err.message);
  }
};

async function runAllContractsValidation() {
  const btn = document.getElementById('btn-validate-all-contracts');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Validando contratos...';
  }

  try {
    const res = await fetch('/api/docs/validate', { method: 'POST' });
    const result = await res.json();
    
    const pane = document.getElementById('docs-reader-pane');
    pane.innerHTML = `
      <div style="margin-bottom:1.5rem;">
        <span class="badge-kdd">Validador Determinista KDD</span>
        <h2 style="font-size:1.6rem; font-weight:700; margin-top:0.4rem; color:${result.success ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
          ${result.success ? '✓ Todos los Contratos son Válidos' : '✖ Se Encontraron Inconsistencias'}
        </h2>
      </div>

      <div class="report-section">
        <h4 style="font-size:1rem; font-weight:600; margin-bottom:0.6rem;">Salida Determinista (scripts/validate_contracts.py)</h4>
        <pre class="test-terminal" style="max-height:450px;">${escapeHtml(result.output)}</pre>
      </div>
    `;
  } catch (err) {
    alert('Error validando contratos: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🧪 Validar Todos los Contratos';
    }
  }
}

function renderMarkdown(md) {
  if (!md) return '';
  let html = escapeHtml(md);

  // Code blocks first (preserve verbatim)
  const codeBlocks = [];
  html = html.replace(/```([a-z0-9_-]*)\n([\s\S]*?)```/gim, (match, lang, code) => {
    const placeholder = `@@@CODE_BLOCK_${codeBlocks.length}@@@`;
    codeBlocks.push(`<pre><code class="language-${lang}">${code.trim()}</code></pre>`);
    return placeholder;
  });

  // Inline code next
  const inlineCodes = [];
  html = html.replace(/`([^`]+)`/gim, (match, code) => {
    const placeholder = `@@@INLINE_CODE_${inlineCodes.length}@@@`;
    inlineCodes.push(`<code>${code}</code>`);
    return placeholder;
  });

  // Markdown Tables
  html = parseMarkdownTables(html);

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Blockquotes
  html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Lists
  html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');

  // Line breaks
  html = html.replace(/\n\n+/gim, '<p></p>');

  // Restore code blocks and inline codes
  inlineCodes.forEach((code, idx) => {
    html = html.replace(`@@@INLINE_CODE_${idx}@@@`, code);
  });
  codeBlocks.forEach((block, idx) => {
    html = html.replace(`@@@CODE_BLOCK_${idx}@@@`, block);
  });

  return html;
}

function parseMarkdownTables(text) {
  const lines = text.split('\n');
  const output = [];
  let inTable = false;
  let tableLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('|') && line.endsWith('|')) {
      inTable = true;
      tableLines.push(line);
    } else {
      if (inTable) {
        output.push(convertTableToHtml(tableLines));
        inTable = false;
        tableLines = [];
      }
      output.push(lines[i]);
    }
  }
  if (inTable) {
    output.push(convertTableToHtml(tableLines));
  }
  return output.join('\n');
}

function convertTableToHtml(lines) {
  if (lines.length < 2) return lines.join('\n');
  const headerCells = lines[0].split('|').slice(1, -1).map((c) => c.trim());
  const rowLines = lines.slice(2);

  let html = '<div class="table-wrapper"><table class="markdown-table"><thead><tr>';
  for (const h of headerCells) {
    html += `<th>${h}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const r of rowLines) {
    const cells = r.split('|').slice(1, -1).map((c) => c.trim());
    html += '<tr>';
    for (const c of cells) {
      html += `<td>${c}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table></div>';
  return html;
}

// Initial Load & Polling
loadTasks();
setInterval(loadTasks, 3000);
