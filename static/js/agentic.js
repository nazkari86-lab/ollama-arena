// Agentic tab: VM sandbox lifecycle + swarm battle launcher, backed by
// /api/agentic/* (ollama_arena/web_routes/agentic_routes.py).
let _agenticTabWired = false;
let _agenticSandboxes = [];

function initAgenticTab() {
  if (!_agenticTabWired) {
    _agenticTabWired = true;
    document.getElementById('agentic-sandboxes-refresh-btn')?.addEventListener('click', loadAgenticSandboxes);
    document.getElementById('agentic-sandbox-start-btn')?.addEventListener('click', startAgenticSandbox);
    document.getElementById('agentic-exec-btn')?.addEventListener('click', execAgenticSandboxTask);
    document.getElementById('agentic-swarm-start-btn')?.addEventListener('click', startAgenticSwarm);
    // Delegated -- the table re-renders on every refresh/start/stop/cleanup.
    document.getElementById('agentic-sandboxes-table')?.addEventListener('click', (e) => {
      const stopBtn = e.target.closest('[data-act="stop"]');
      const cleanupBtn = e.target.closest('[data-act="cleanup"]');
      if (stopBtn) stopAgenticSandbox(stopBtn.dataset.id);
      else if (cleanupBtn) cleanupAgenticSandbox(cleanupBtn.dataset.id);
    });
  }
  loadAgenticSandboxes();
}

async function loadAgenticSandboxes() {
  try {
    _agenticSandboxes = await api('/api/agentic/sandboxes');
    document.getElementById('agentic-stat-sandboxes').textContent = _agenticSandboxes.length;
    document.getElementById('agentic-stat-running').textContent =
      _agenticSandboxes.filter(s => s.status === 'running').length;
    renderAgenticSandboxesTable();
  } catch (e) {
    toast(`Failed to load sandboxes: ${escText(e.message)}`, 'error');
  }
}

function renderAgenticSandboxesTable() {
  const el = document.getElementById('agentic-sandboxes-table');
  if (!el) return;
  if (!_agenticSandboxes.length) {
    el.innerHTML = '<div class="sim-field-help">No sandboxes yet. Start one above.</div>';
  } else {
    const rows = _agenticSandboxes.map(s => `
      <tr>
        <td><code>${escText(s.sandbox_id)}</code></td>
        <td>${escText(s.status)}</td>
        <td class="sim-run-actions">
          <button class="btn" data-act="stop" data-id="${escText(s.sandbox_id)}" style="width:auto; padding:4px 12px; font-size:10px;">Stop</button>
          <button class="btn" data-act="cleanup" data-id="${escText(s.sandbox_id)}" style="width:auto; padding:4px 12px; font-size:10px;">Cleanup</button>
        </td>
      </tr>`).join('');
    el.innerHTML = `<div class="sim-table-wrap"><table><thead><tr><th>Sandbox ID</th><th>Status</th><th>Controls</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  const select = document.getElementById('agentic-exec-sandbox');
  if (select) {
    const current = select.value;
    select.innerHTML = _agenticSandboxes.map(s => `<option value="${escText(s.sandbox_id)}">${escText(s.sandbox_id)}</option>`).join('')
      || '<option value="">No sandboxes</option>';
    if (_agenticSandboxes.some(s => s.sandbox_id === current)) select.value = current;
  }
}

async function startAgenticSandbox() {
  const input = document.getElementById('agentic-sandbox-id');
  const sandboxId = input.value.trim();
  if (!sandboxId) { toast('Enter a sandbox id first.', 'warn'); return; }
  try {
    const r = await api('/api/agentic/sandbox/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sandbox_id: sandboxId }),
    });
    toast(`Sandbox <b>${escText(r.sandbox_id)}</b>: ${escText(r.status)} (${escText(r.backend)})`,
      r.status === 'running' ? 'success' : 'warn');
    input.value = '';
    await loadAgenticSandboxes();
  } catch (e) {
    toast(`Failed to start sandbox: ${escText(e.message)}`, 'error');
  }
}

async function stopAgenticSandbox(sandboxId) {
  try {
    await api(`/api/agentic/sandbox/${encodeURIComponent(sandboxId)}/stop`, { method: 'POST' });
    toast(`Stopped <b>${escText(sandboxId)}</b>`, 'success', 2000);
    await loadAgenticSandboxes();
  } catch (e) {
    toast(`Failed to stop sandbox: ${escText(e.message)}`, 'error');
  }
}

async function cleanupAgenticSandbox(sandboxId) {
  try {
    await api(`/api/agentic/sandbox/${encodeURIComponent(sandboxId)}/cleanup`, { method: 'POST' });
    toast(`Cleaned up <b>${escText(sandboxId)}</b>`, 'success', 2000);
    await loadAgenticSandboxes();
  } catch (e) {
    toast(`Failed to clean up sandbox: ${escText(e.message)}`, 'error');
  }
}

async function execAgenticSandboxTask() {
  const sandboxId = document.getElementById('agentic-exec-sandbox').value;
  const taskInput = document.getElementById('agentic-exec-task');
  const task = taskInput.value.trim();
  const log = document.getElementById('agentic-exec-log');
  if (!sandboxId) { toast('Start a sandbox first.', 'warn'); return; }
  if (!task) { toast('Enter a task to run.', 'warn'); return; }
  try {
    const r = await api(`/api/agentic/sandbox/${encodeURIComponent(sandboxId)}/execute`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task }),
    });
    const cls = r.success ? 'log-win' : 'log-loss';
    log.insertAdjacentHTML('afterbegin', `<div class="${cls}">[${escText(sandboxId)}] ${escText(task)}\n${escText(r.output || r.error || '')}</div>`);
    taskInput.value = '';
  } catch (e) {
    toast(`Execution failed: ${escText(e.message)}`, 'error');
  }
}

async function startAgenticSwarm() {
  const mode = document.getElementById('agentic-swarm-mode').value;
  const rounds = Number(document.getElementById('agentic-swarm-rounds').value) || 3;
  const maxSteps = Number(document.getElementById('agentic-swarm-max-steps').value) || 5;
  const task = document.getElementById('agentic-swarm-task').value.trim();
  const status = document.getElementById('agentic-swarm-status');
  const btn = document.getElementById('agentic-swarm-start-btn');
  if (!task) { toast('Enter a task for the swarm to work on.', 'warn'); return; }
  btn.disabled = true;
  status.className = 'status running';
  status.style.display = 'block';
  status.textContent = 'Launching battle…';
  document.getElementById('agentic-swarm-result').innerHTML = '';
  try {
    const r = await api('/api/agentic/swarm/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, task, rounds, max_steps: maxSteps }),
    });
    _agenticSwarmJobId = r.job_id;
    status.textContent = `Battle running (job ${r.job_id})…`;
    _pollAgenticSwarmJob(r.job_id);
  } catch (e) {
    status.className = 'status';
    toast(`Failed to start swarm battle: ${escText(e.message)}`, 'error');
    btn.disabled = false;
  }
}

let _agenticSwarmJobId = null;

// Swarm battles can run for multiple LLM round-trips -- the WS broadcast
// (swarm_battle_done) is the primary completion signal, but polling here
// is the fallback in case the WS message is missed (tab not focused when
// it arrived, reconnect gap, etc.).
function _pollAgenticSwarmJob(jobId) {
  const status = document.getElementById('agentic-swarm-status');
  const poll = async () => {
    if (jobId !== _agenticSwarmJobId) return; // a newer battle superseded this poll
    try {
      const job = await api(`/api/agentic/swarm/${encodeURIComponent(jobId)}`);
      if (job.status === 'running') {
        setTimeout(poll, 3000);
        return;
      }
      _renderAgenticSwarmResult(job);
    } catch (e) {
      status.className = 'status';
      status.textContent = `Lost track of job: ${escText(e.message)}`;
    }
  };
  setTimeout(poll, 3000);
}

function handleAgenticWSEvent(d) {
  if (d.type !== 'swarm_battle_done' || d.job_id !== _agenticSwarmJobId) return;
  api(`/api/agentic/swarm/${encodeURIComponent(d.job_id)}`).then(_renderAgenticSwarmResult).catch(() => {});
}

function _renderAgenticSwarmResult(job) {
  const status = document.getElementById('agentic-swarm-status');
  const result = document.getElementById('agentic-swarm-result');
  const btn = document.getElementById('agentic-swarm-start-btn');
  btn.disabled = false;
  if (job.status === 'error') {
    status.className = 'status';
    status.textContent = `Battle failed: ${job.error}`;
    toast(`Swarm battle failed: ${escText(job.error)}`, 'error');
    return;
  }
  status.className = 'status done';
  status.textContent = `Done — winner: ${job.winner}`;
  result.innerHTML = `
    <div class="${job.winner === 'Team A' ? 'log-win' : 'log-loss'}">Winner: <b>${escText(job.winner)}</b></div>
    <div>Team A score: <b>${job.team_a_score}</b> · Team B score: <b>${job.team_b_score}</b></div>
    <div style="color:var(--text-muted); font-size:11px;">${job.rounds_completed} round(s) · ${job.duration_s.toFixed(1)}s</div>
  `;
}
