// Simulation observatory: scenario catalog, local model selection, live model
// actions over WebSocket, stored trace inspection, replay, and training tools.
let _simTabWired = false;
let _simWatchedRunId = null;
let _simScenarios = [];
let _simRuns = [];
let _simActionCount = 0;

const SIM_META = {
  educational: { icon: '▤', color: '#58a6ff', label: 'Curriculum' },
  mafia: { icon: '◉', color: '#f85149', label: 'Social deduction' },
  rps: { icon: '✊', color: '#e3b341', label: 'Rock paper scissors' },
  sandbox_universe: { icon: '◇', color: '#39d353', label: 'Resource sandbox' },
  sims_world: { icon: '⌂', color: '#d2a8ff', label: 'Life simulation' },
  tictactoe: { icon: '╳', color: '#2dd4bf', label: 'Tic-tac-toe' },
};

const AGENT_COLORS = ['#58a6ff', '#3fb950', '#e3b341', '#d2a8ff', '#f85149', '#2dd4bf'];

function initSimTab() {
  if (!_simTabWired) {
    _simTabWired = true;
    document.getElementById('sim-run-btn')?.addEventListener('click', startSimRun);
    document.getElementById('sim-refresh-runs-btn')?.addEventListener('click', loadSimRuns);
    document.getElementById('sim-replay-btn')?.addEventListener('click', loadSimReplay);
    document.getElementById('sim-train-btn')?.addEventListener('click', trainSim);
    document.getElementById('sim-compare-btn')?.addEventListener('click', compareSimRuns);
    document.getElementById('sim-scenario')?.addEventListener('change', event => {
      selectSimScenario(event.target.value, false);
    });
  }
  Promise.all([loadSimScenarios(), loadSimModels(), loadSimRuns(), populateSimRouterRoles()]);
}

async function populateSimRouterRoles() {
  const select = document.getElementById('sim-router-role');
  if (!select) return;
  try {
    const data = await api('/api/role-routing');
    const configured = new Set(Object.keys(data.role_models || {}));
    select.innerHTML = '<option value="">Off — use the literal models selected above</option>' +
      data.roles.map(r => `<option value="${escText(r)}">${escText(r)}${configured.has(r) ? ' ✓ configured' : ''}</option>`).join('');
  } catch (e) { /* role routing is optional -- a fetch failure here shouldn't block the sim form */ }
}

function simMeta(name) {
  return SIM_META[name] || { icon: '◎', color: '#58a6ff', label: name };
}

async function loadSimScenarios() {
  const select = document.getElementById('sim-scenario');
  const grid = document.getElementById('sim-scenario-grid');
  if (!select || !grid) return;
  try {
    _simScenarios = await api('/api/sim/scenarios');
    document.getElementById('sim-stat-scenarios').textContent = _simScenarios.length;
    select.innerHTML = _simScenarios.map(s =>
      `<option value="${escText(s.name)}">${escText(simMeta(s.name).label)}</option>`
    ).join('');
    grid.innerHTML = _simScenarios.map(s => {
      const meta = simMeta(s.name);
      return `<button type="button" class="sim-scenario-tile" data-scenario="${escText(s.name)}" style="--sim-accent:${meta.color}">
        <span class="sim-scenario-icon">${meta.icon}</span>
        <span class="sim-scenario-name">${escText(meta.label)}</span>
        <span class="sim-scenario-copy">${escText(s.description)}</span>
      </button>`;
    }).join('');
    grid.querySelectorAll('[data-scenario]').forEach(tile => {
      tile.addEventListener('click', () => selectSimScenario(tile.dataset.scenario, true));
    });
    if (_simScenarios.length) selectSimScenario(select.value || _simScenarios[0].name, true);
  } catch (error) {
    select.innerHTML = '<option value="">Scenarios unavailable</option>';
    grid.innerHTML = `<div class="sim-field-help">${escText(error.message)}</div>`;
  }
}

function selectSimScenario(name, applyDefaults) {
  const scenario = _simScenarios.find(item => item.name === name);
  if (!scenario) return;
  const select = document.getElementById('sim-scenario');
  if (select) select.value = name;
  document.getElementById('sim-scenario-desc').textContent = scenario.description;
  document.querySelectorAll('.sim-scenario-tile').forEach(tile => {
    tile.classList.toggle('active', tile.dataset.scenario === name);
    tile.setAttribute('aria-pressed', tile.dataset.scenario === name ? 'true' : 'false');
  });
  if (applyDefaults) {
    document.getElementById('sim-config').value = JSON.stringify(scenario.default_config || {}, null, 2);
  }
  if (!_simWatchedRunId) {
    renderSimWorld(name, [], 0, 'Ready');
    renderSimAgents([]);
  }
}

async function loadSimModels() {
  const select = document.getElementById('sim-agents');
  if (!select) return;
  try {
    const rawModels = await api('/api/models');
    const models = rawModels.map(model => typeof model === 'string' ? model : model.name).filter(Boolean);
    const preferred = ['llama3.2:1b', 'gemma2:2b'];
    const defaults = preferred.filter(model => models.includes(model));
    if (defaults.length < 2) {
      models.filter(model => !/(embed|bge|nomic)/i.test(model)).slice(0, 2).forEach(model => {
        if (!defaults.includes(model)) defaults.push(model);
      });
    }
    select.innerHTML = models.map(model =>
      `<option value="${escText(model)}" ${defaults.includes(model) ? 'selected' : ''}>${escText(model)}</option>`
    ).join('') || '<option value="" disabled>No local models found</option>';
  } catch (error) {
    select.innerHTML = '<option value="" disabled>Unable to load Ollama models</option>';
  }
}

function selectedSimModels() {
  const select = document.getElementById('sim-agents');
  return Array.from(select?.selectedOptions || []).map(option => option.value).filter(Boolean);
}

function resetSimLive(runId, scenario, models) {
  _simWatchedRunId = runId;
  _simActionCount = 0;
  document.getElementById('sim-action-count').textContent = '0 actions';
  document.getElementById('sim-live-log').innerHTML = '';
  document.getElementById('sim-live-summary').innerHTML =
    `Run <b>${escText(runId)}</b> · ${escText(simMeta(scenario).label)}`;
  document.getElementById('sim-live-tick').textContent = 'Tick 0';
  document.getElementById('sim-live-phase').textContent = 'Starting';
  document.getElementById('sim-progress-fill').style.width = '0%';
  renderSimAgents(models.map((model, index) => ({
    agent_id: model,
    model,
    action: { kind: 'waiting', payload: {} },
    reward: 0,
    status: {},
    color: AGENT_COLORS[index % AGENT_COLORS.length],
  })));
  renderSimWorld(scenario, [], 0, 'Starting');
}

async function startSimRun() {
  const scenario = document.getElementById('sim-scenario').value;
  const agents = selectedSimModels();
  const seedRaw = document.getElementById('sim-seed').value;
  const ticksRaw = document.getElementById('sim-ticks').value;
  const configRaw = document.getElementById('sim-config').value.trim();
  if (!scenario) { toast('Pick a scenario first.', 'warn'); return; }
  if (!agents.length) { toast('Select at least one local model.', 'warn'); return; }
  if (['rps', 'tictactoe'].includes(scenario) && agents.length !== 2) {
    toast('This scenario requires exactly two models.', 'warn');
    return;
  }

  let config = {};
  if (configRaw) {
    try { config = JSON.parse(configRaw); }
    catch (error) { toast(`Config is not valid JSON: ${escText(error.message)}`, 'error'); return; }
  }

  const body = { scenario, agents, config, ticks: ticksRaw ? parseInt(ticksRaw, 10) : 200 };
  if (seedRaw !== '') body.seed = parseInt(seedRaw, 10);
  const routerRole = document.getElementById('sim-router-role')?.value;
  if (routerRole) body.router_role = routerRole;
  const status = document.getElementById('sim-run-status');
  const button = document.getElementById('sim-run-btn');
  button.disabled = true;
  button.textContent = 'Starting...';
  try {
    const response = await api('/api/sim/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    resetSimLive(response.run_id, scenario, agents);
    status.className = 'status running';
    status.textContent = `Run ${response.run_id} started.`;
    document.getElementById('sim-replay-run-id').value = response.run_id;
    document.getElementById('sim-train-run-id').value = response.run_id;
    toast(`Simulation <b>${escText(response.run_id)}</b> started.`, 'success', 3000);
    loadSimRuns();
  } catch (error) {
    status.className = 'status';
    toast(`Failed to start run: ${escText(error.message)}`, 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Start Run';
  }
}

function simStatusBadge(status) {
  if (status === 'completed') return `<span class="badge badge-green">${escText(status)}</span>`;
  if (status === 'failed') return `<span class="badge sim-badge-failed">${escText(status)}</span>`;
  return `<span class="badge badge-blue">${escText(status)}</span>`;
}

async function loadSimRuns() {
  const container = document.getElementById('sim-runs-table');
  if (!container) return;
  try {
    _simRuns = await api('/api/sim/runs');
    document.getElementById('sim-stat-runs').textContent = _simRuns.length;
    document.getElementById('sim-stat-active').textContent =
      _simRuns.filter(run => ['in_progress', 'paused'].includes(run.status)).length;
    if (!_simRuns.length) {
      container.innerHTML = '<div class="sim-field-help">No runs yet. Start one above.</div>';
      return;
    }
    const rows = _simRuns.map(run => {
      const agents = (run.agents || []).map(agent => agent.model).join(', ');
      return `<tr class="${run.run_id === _simWatchedRunId ? 'sim-run-selected' : ''}">
        <td title="${escText(run.run_id)}"><code>${escText(run.run_id)}</code></td>
        <td>${escText(simMeta(run.scenario).label)}</td>
        <td>${simStatusBadge(run.status)}</td>
        <td class="sim-model-list">${escText(agents)}</td>
        <td class="sim-run-actions">
          <button class="btn" data-act="watch" data-run="${escText(run.run_id)}">Watch</button>
          ${run.status === 'in_progress' ? `<button class="btn" data-act="pause" data-run="${escText(run.run_id)}">Pause</button>` : ''}
          ${run.status === 'paused' ? `<button class="btn" data-act="resume" data-run="${escText(run.run_id)}">Resume</button>` : ''}
          ${run.status === 'completed' && (run.scenario === 'sims_world' || run.scenario === 'mafia') ? `<button class="btn" data-act="world" data-run="${escText(run.run_id)}">▶ View in 3D world</button>` : ''}
        </td>
      </tr>`;
    }).join('');
    container.innerHTML = `<div class="sim-table-wrap"><table><thead><tr><th>Run ID</th><th>World</th><th>Status</th><th>Models</th><th>Controls</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    container.querySelectorAll('button[data-act]').forEach(button => {
      button.addEventListener('click', () => {
        const runId = button.dataset.run;
        if (button.dataset.act === 'watch') watchSimRun(runId);
        else if (button.dataset.act === 'pause') pauseSimRun(runId);
        else if (button.dataset.act === 'resume') resumeSimRun(runId);
        else if (button.dataset.act === 'world') viewSimRunInWorld(runId);
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="sim-field-help" style="color:var(--accent-red)">${escText(error.message)}</div>`;
  }
}

async function watchSimRun(runId) {
  try {
    const trace = await api(`/api/sim/run/${encodeURIComponent(runId)}/trace?limit=300`);
    const run = trace.run;
    _simWatchedRunId = runId;
    _simActionCount = trace.transitions.length;
    document.getElementById('sim-replay-run-id').value = runId;
    document.getElementById('sim-train-run-id').value = runId;
    document.getElementById('sim-live-summary').innerHTML =
      `Run <b>${escText(runId)}</b> · ${escText(simMeta(run.scenario).label)} · ${escText(run.status)}`;
    const modelByAgent = Object.fromEntries((run.agents || []).map(agent => [agent.agent_id, agent.model]));
    const latestByAgent = {};
    trace.transitions.forEach(transition => { latestByAgent[transition.agent_id] = transition; });
    const latest = Object.values(latestByAgent).map(transition => ({
      agent_id: transition.agent_id,
      model: modelByAgent[transition.agent_id] || transition.agent_id,
      action: transition.action,
      reward: transition.reward,
      status: transition.obs?.status || {},
    }));
    const maxTick = Math.max(0, ...trace.transitions.map(transition => transition.tick));
    renderSimTick({
      run_id: runId,
      tick: maxTick,
      phase: run.status,
      progress: run.status === 'completed' ? 1 : 0,
      agents: latest,
      events: trace.events.slice(-20),
    }, run.scenario, false);
    renderStoredStream(trace.transitions, trace.events);
    loadSimRuns();
  } catch (error) {
    toast(`Unable to load trace: ${escText(error.message)}`, 'error');
  }
}

function renderStoredStream(transitions, events) {
  const stream = document.getElementById('sim-live-log');
  const items = [
    ...transitions.map(item => ({ tick: item.tick, type: 'action', actor: item.agent_id, kind: item.action.kind, payload: item.action.payload })),
    ...events.map(item => ({ tick: item.tick, type: 'event', actor: item.actor_id || 'world', kind: item.kind, payload: item.payload, visibility: item.visibility })),
  ].sort((a, b) => a.tick - b.tick).slice(-80);
  stream.innerHTML = items.map(renderSimStreamItem).join('');
  stream.scrollTop = stream.scrollHeight;
  document.getElementById('sim-action-count').textContent = `${transitions.length} actions`;
}

function renderSimTick(data, scenarioName = null, appendStream = true) {
  const run = _simRuns.find(item => item.run_id === data.run_id);
  const scenario = scenarioName || run?.scenario || document.getElementById('sim-scenario')?.value || 'idle';
  document.getElementById('sim-live-tick').textContent = `Tick ${data.tick ?? 0}`;
  document.getElementById('sim-live-phase').textContent = data.phase || 'Running';
  document.getElementById('sim-progress-fill').style.width = `${Math.max(0, Math.min(100, (data.progress || 0) * 100))}%`;
  renderSimAgents(data.agents || []);
  renderSimWorld(scenario, data.agents || [], data.tick || 0, data.phase || '');
  if (appendStream) appendSimStream(data);
}

function renderSimAgents(agents) {
  const grid = document.getElementById('sim-agent-grid');
  if (!agents.length) {
    grid.innerHTML = '<div class="sim-empty-state" style="min-height:260px"><strong>Waiting for agents</strong></div>';
    return;
  }
  grid.innerHTML = agents.map((agent, index) => {
    const color = agent.color || AGENT_COLORS[index % AGENT_COLORS.length];
    const action = agent.action || { kind: 'waiting', payload: {} };
    return `<div class="sim-agent-row" style="--agent-accent:${color}">
      <div>
        <div class="sim-agent-name">${escText(agent.model || agent.agent_id)}</div>
        <div class="sim-agent-id">${escText(agent.agent_id)}</div>
        <span class="sim-reward">reward ${formatSimNumber(agent.reward)}</span>
      </div>
      <div>
        <div class="sim-agent-action">${escText(action.kind || 'waiting')}</div>
        <div class="sim-agent-payload">${escText(formatSimObject(action.payload || {}))}</div>
        <div class="sim-agent-state">${escText(formatSimStatus(agent.status || {}))}</div>
      </div>
    </div>`;
  }).join('');
}

function renderSimWorld(scenario, agents, tick, phase) {
  const root = document.getElementById('sim-world-viz');
  const meta = simMeta(scenario);
  document.getElementById('sim-stage').dataset.scenario = scenario;
  const states = agents.map(agent => agent.status || {}).filter(Boolean);
  if (scenario === 'tictactoe') {
    const board = states.find(state => Array.isArray(state.board))?.board || Array(9).fill('');
    root.innerHTML = `<div class="sim-board" aria-label="Tic-tac-toe board">${board.map(cell =>
      `<div class="sim-board-cell">${escText(cell || '')}</div>`
    ).join('')}</div>`;
    return;
  }
  let symbol = meta.icon;
  let title = meta.label;
  let detail = `tick ${tick} · ${phase || 'ready'}`;
  if (scenario === 'rps') {
    const choices = agents.map(agent => agent.action?.payload?.choice).filter(Boolean);
    const choiceIcons = { rock: '✊', paper: '▤', scissors: '✂' };
    symbol = choices.map(choice => choiceIcons[choice] || '?').join('  ') || '✊';
    detail = states.map((state, i) => `A${i + 1}: ${state.score ?? 0}`).join(' · ') || detail;
  } else if (scenario === 'mafia') {
    const alive = states.filter(state => state.alive !== false).length;
    detail = `round ${states[0]?.round ?? tick} · ${alive}/${states.length || agents.length} alive · ${phase || 'setup'}`;
  } else if (scenario === 'sims_world') {
    const avgEnergy = average(states.map(state => state.needs?.energy));
    const avgMoney = average(states.map(state => state.money));
    detail = `day ${states[0]?.day ?? tick} · energy ${formatSimNumber(avgEnergy)} · money ${formatSimNumber(avgMoney)}`;
  } else if (scenario === 'sandbox_universe') {
    const resources = {};
    states.forEach(state => Object.entries(state.resources || {}).forEach(([name, value]) => {
      resources[name] = (resources[name] || 0) + Number(value || 0);
    }));
    detail = Object.entries(resources).map(([name, value]) => `${name} ${formatSimNumber(value)}`).join(' · ') || detail;
  } else if (scenario === 'educational') {
    const progress = states.reduce((sum, state) => sum + Number(state.progress || 0), 0);
    const total = states.reduce((sum, state) => sum + Number(state.total_tasks || 0), 0);
    detail = `${progress}/${total || '?'} tasks completed`;
  }
  root.innerHTML = `<div class="sim-world-core">
    <div class="sim-world-symbol" style="color:${meta.color}; border-color:${meta.color}66; background:${meta.color}12">${symbol}</div>
    <div class="sim-world-title">${escText(title)}</div>
    <div class="sim-world-detail">${escText(detail)}</div>
  </div>`;
}

function appendSimStream(data) {
  const stream = document.getElementById('sim-live-log');
  const actionItems = (data.agents || []).map(agent => ({
    tick: data.tick, type: 'action', actor: agent.model || agent.agent_id,
    kind: agent.action?.kind || 'wait', payload: agent.action?.payload || {},
  }));
  const eventItems = (data.events || []).map(event => ({
    tick: data.tick, type: 'event', actor: event.actor_id || 'world',
    kind: event.kind, payload: event.payload, visibility: event.visibility,
  }));
  _simActionCount += actionItems.length;
  document.getElementById('sim-action-count').textContent = `${_simActionCount} actions`;
  stream.insertAdjacentHTML('beforeend', [...actionItems, ...eventItems].map(renderSimStreamItem).join(''));
  while (stream.children.length > 80) stream.firstElementChild.remove();
  stream.scrollTop = stream.scrollHeight;
}

function renderSimStreamItem(item) {
  const classes = ['sim-action-item', item.type === 'event' ? 'event' : '', item.visibility === 'private' ? 'private' : ''].filter(Boolean).join(' ');
  return `<div class="${classes}">
    <time>T${escText(item.tick)}</time>
    <strong>${escText(item.actor)}</strong>
    <span>${escText(item.kind)} · ${escText(formatSimObject(item.payload || {}))}</span>
  </div>`;
}

function formatSimObject(value) {
  const text = JSON.stringify(value);
  return text.length > 150 ? `${text.slice(0, 147)}...` : text;
}

function formatSimStatus(status) {
  const preferred = ['alive', 'role', 'round', 'day', 'progress', 'total_tasks', 'money', 'job', 'needs', 'resources', 'your_turn'];
  const compact = {};
  preferred.forEach(key => { if (status[key] !== undefined) compact[key] = status[key]; });
  if (!Object.keys(compact).length) Object.assign(compact, status);
  return formatSimObject(compact);
}

function formatSimNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '0';
  return Number.isInteger(number) ? String(number) : number.toFixed(2);
}

function average(values) {
  const numbers = values.map(Number).filter(Number.isFinite);
  return numbers.length ? numbers.reduce((sum, value) => sum + value, 0) / numbers.length : 0;
}

async function pauseSimRun(runId) {
  try {
    await api(`/api/sim/run/${encodeURIComponent(runId)}/pause`, { method: 'POST' });
    toast(`Run ${escText(runId)} pause requested.`, 'info', 2500);
    loadSimRuns();
  } catch (error) { toast(`Pause failed: ${escText(error.message)}`, 'error'); }
}

async function resumeSimRun(runId) {
  try {
    await api(`/api/sim/run/${encodeURIComponent(runId)}/resume`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    _simWatchedRunId = runId;
    toast(`Run ${escText(runId)} resuming.`, 'info', 2500);
    loadSimRuns();
  } catch (error) { toast(`Resume failed: ${escText(error.message)}`, 'error'); }
}

async function loadSimReplay() {
  const runId = document.getElementById('sim-replay-run-id').value.trim();
  const tickRaw = document.getElementById('sim-replay-tick').value;
  const container = document.getElementById('sim-replay-log');
  if (!runId) { toast('Enter a run id to replay.', 'warn'); return; }
  let url = `/api/sim/run/${encodeURIComponent(runId)}/replay`;
  if (tickRaw !== '') url += `?tick=${encodeURIComponent(tickRaw)}`;
  try {
    const events = await api(url);
    container.innerHTML = events.length ? events.map(event =>
      `<div style="margin-bottom:6px"><span style="color:var(--text-muted)">[${event.tick}]</span> <span style="color:var(--accent-blue)">${escText(event.kind)}</span> ${escText(formatSimObject(event.payload))}</div>`
    ).join('') : '<div style="color:var(--text-muted)">No events found for this run.</div>';
    container.scrollTop = container.scrollHeight;
  } catch (error) {
    container.innerHTML = `<div style="color:var(--accent-red)">${escText(error.message)}</div>`;
  }
}

async function trainSim() {
  const runId = document.getElementById('sim-train-run-id').value.trim();
  const epochs = parseInt(document.getElementById('sim-train-epochs').value || '5', 10);
  const status = document.getElementById('sim-train-status');
  if (!runId) { toast('Enter a run id to train on.', 'warn'); return; }
  try {
    const response = await api('/api/sim/train', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: runId, epochs }),
    });
    status.textContent = `Training job ${response.job_id} started.`;
  } catch (error) { status.textContent = `Failed: ${error.message}`; }
}

async function compareSimRuns() {
  const ids = document.getElementById('sim-compare-run-ids').value.split(',').map(value => value.trim()).filter(Boolean);
  const container = document.getElementById('sim-compare-table');
  if (!ids.length) { toast('Enter at least one run id.', 'warn'); return; }
  try {
    const report = await api(`/api/sim/compare?run_ids=${encodeURIComponent(ids.join(','))}`);
    if (!report.run_ids.length || !report.metric_names.length) {
      container.innerHTML = '<div class="sim-field-help">No comparable metrics found.</div>';
      return;
    }
    const header = `<th>Run ID</th>${report.metric_names.map(name => `<th>${escText(name)}</th>`).join('')}`;
    const rows = report.run_ids.map(runId => {
      const metrics = report.metrics_by_run[runId] || {};
      return `<tr><td><code>${escText(runId)}</code></td>${report.metric_names.map(name => `<td>${name in metrics ? metrics[name].toFixed(3) : '—'}</td>`).join('')}</tr>`;
    }).join('');
    container.innerHTML = `<table><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table>`;
  } catch (error) {
    container.innerHTML = `<div class="sim-field-help" style="color:var(--accent-red)">${escText(error.message)}</div>`;
  }
}

function handleSimWSEvent(data) {
  if (data.type === 'sim_tick') {
    if (data.run_id !== _simWatchedRunId) return;
    document.getElementById('sim-live-summary').innerHTML =
      `Run <b>${escText(data.run_id)}</b> · live model decisions`;
    renderSimTick(data);
  } else if (data.type === 'sim_phase_change') {
    if (data.run_id === _simWatchedRunId) document.getElementById('sim-live-phase').textContent = data.status;
    loadSimRuns();
  } else if (data.type === 'sim_run_done') {
    if (data.run_id === _simWatchedRunId) {
      document.getElementById('sim-live-phase').textContent = data.error ? 'Failed' : 'Completed';
      if (!data.error) document.getElementById('sim-progress-fill').style.width = '100%';
      const stream = document.getElementById('sim-live-log');
      stream.insertAdjacentHTML('beforeend', `<div class="sim-action-item event"><time>END</time><strong>world</strong><span>${data.error ? escText(data.error) : escText(formatSimObject(data.outcome || {}))}</span></div>`);
      toast(data.error ? `Run ${escText(data.run_id)} failed.` : `Run ${escText(data.run_id)} finished.`, data.error ? 'error' : 'success', 4000);
    }
    loadSimRuns();
  } else if (data.type === 'sim_training_progress') {
    const status = document.getElementById('sim-train-status');
    if (!status) return;
    if (data.status === 'started') status.textContent = `Training job ${data.job_id} running...`;
    else if (data.status === 'error') status.innerHTML = `<span style="color:var(--accent-red)">Training failed: ${escText(data.error)}</span>`;
    else if (data.status === 'done') status.textContent = `Done · final loss ${data.final_loss.toFixed(4)}`;
  }
}
