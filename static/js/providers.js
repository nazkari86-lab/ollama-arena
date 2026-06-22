// Providers tab: backend preset catalog, free-model registry, and the
// 8-role -> model routing editor (POST /api/role-routing).
let _providersTabWired = false;
let _providersData = [];
let _providersFilter = 'all';
let _roleRoutingRoles = [];
let _roleRoutingModels = {};
let _registryEntries = [];

const ROLE_LABELS = {
  world_step: 'World step', planner: 'Planner', npc_dialogue: 'NPC dialogue',
  narrator: 'Narrator', memory_compressor: 'Memory compressor',
  classifier: 'Classifier', judge: 'Judge', fallback: 'Fallback',
};
const ROLE_HINTS = {
  world_step: 'Drives world-level transitions, if a scenario uses an LLM for them.',
  planner: 'Multi-step planning calls for an agent.',
  npc_dialogue: 'Per-turn action/decision call every LLMSimAgent makes.',
  narrator: 'Summarizes events into prose, if a scenario adds one.',
  memory_compressor: 'Compresses long event history into a shorter summary.',
  classifier: 'Cheap categorization calls.',
  judge: 'Pairwise grading (LLMJudge) for evals and Arena Match scoring.',
  fallback: 'Used when nothing else in the chain is available.',
};

function initProvidersTab() {
  if (!_providersTabWired) {
    _providersTabWired = true;
    document.getElementById('registry-refresh-btn')?.addEventListener('click', loadModelRegistry);
    document.getElementById('role-routing-save-btn')?.addEventListener('click', saveRoleRouting);
    // Delegated -- the grid re-renders on every filter click/refresh, so
    // listeners on individual buttons would leak; one listener on the
    // (static) container handles every Save/Clear button it ever holds.
    document.getElementById('provider-grid')?.addEventListener('click', event => {
      const saveBtn = event.target.closest('.provider-key-save');
      const clearBtn = event.target.closest('.provider-key-clear');
      if (saveBtn) saveProviderKey(saveBtn.dataset.provider);
      else if (clearBtn) clearProviderKey(clearBtn.dataset.provider);
    });
    document.querySelectorAll('.provider-filter').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.provider-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _providersFilter = btn.dataset.kind;
        renderProviderGrid();
      });
    });
  }
  Promise.all([loadProviders(), loadModelRegistry(), loadRoleRouting()]);
}

async function loadProviders() {
  try {
    _providersData = await api('/api/providers');
    document.getElementById('prov-stat-total').textContent = _providersData.length;
    document.getElementById('prov-stat-configured').textContent =
      _providersData.filter(p => p.key_configured).length;
    renderProviderGrid();
  } catch (e) {
    toast(`Failed to load providers: ${escText(e.message)}`, 'error');
  }
}

async function saveProviderKey(provider) {
  const row = document.querySelector(`.provider-key-row[data-provider="${provider}"]`);
  const input = row?.querySelector('.provider-key-input');
  if (!input) return;
  const value = input.value;
  if (!value) { toast('Enter a key first.', 'warn'); return; }
  try {
    await api(`/api/providers/${encodeURIComponent(provider)}/key`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: value }),
    });
    // Clear immediately -- the value never needs to exist in the DOM/JS
    // a moment longer than the request that just sent it.
    input.value = '';
    toast(`Key saved for <b>${escText(provider)}</b>.`, 'success');
    await loadProviders();
  } catch (e) {
    toast(`Failed to save key: ${escText(e.message)}`, 'error');
  }
}

async function clearProviderKey(provider) {
  try {
    await api(`/api/providers/${encodeURIComponent(provider)}/key`, { method: 'DELETE' });
    toast(`Key cleared for <b>${escText(provider)}</b>.`, 'success');
    await loadProviders();
  } catch (e) {
    toast(`Failed to clear key: ${escText(e.message)}`, 'error');
  }
}

function renderProviderGrid() {
  const grid = document.getElementById('provider-grid');
  if (!grid) return;
  const kindBadge = { local: 'badge-gray', free: 'badge-green', paid: 'badge-purple' };
  const list = _providersFilter === 'all'
    ? _providersData
    : _providersData.filter(p => p.kind === _providersFilter);
  grid.innerHTML = list.map(p => `
    <div class="provider-card">
      <div class="provider-card-head">
        <span class="provider-card-name">${escText(p.name)}</span>
        <span class="badge ${kindBadge[p.kind] || 'badge-gray'}">${escText(p.kind)}</span>
      </div>
      <div class="provider-card-url">${escText(p.base_url)}</div>
      <div class="provider-card-env">
        ${p.env_key
          ? `<span class="key-dot${p.key_configured ? ' set' : ''}" data-tip="${p.key_configured ? 'Key configured' : 'Not set'}"></span>
             <code>${escText(p.env_key)}</code>`
          : `<span class="key-dot set" data-tip="No key needed"></span> local runtime`}
      </div>
      ${p.env_key ? `
        <div class="provider-key-row" data-provider="${escText(p.name)}">
          <input type="password" class="provider-key-input" autocomplete="new-password" spellcheck="false"
                 placeholder="${p.key_configured ? 'Replace stored key…' : 'Paste API key…'}">
          <button type="button" class="btn provider-key-save" data-provider="${escText(p.name)}">Save</button>
          ${p.key_configured ? `<button type="button" class="btn provider-key-clear" data-provider="${escText(p.name)}">Clear</button>` : ''}
        </div>
      ` : ''}
    </div>
  `).join('') || '<div style="color:var(--text-muted); font-size:13px;">No providers match this filter.</div>';
}

async function loadModelRegistry() {
  try {
    _registryEntries = await api('/api/model-registry');
    document.getElementById('prov-stat-free').textContent =
      _registryEntries.filter(e => e.free).length;
    renderRegistryTable();
    renderRoleRoutingModelOptions();
  } catch (e) {
    toast(`Failed to load model registry: ${escText(e.message)}`, 'error');
  }
}

function renderRegistryTable() {
  const tbody = document.getElementById('registry-tbody');
  if (!tbody) return;
  tbody.innerHTML = _registryEntries.map(e => `
    <tr>
      <td><code class="kbd-tag">${escText(e.id)}</code></td>
      <td><span class="badge badge-green">${escText(e.source)}</span></td>
      <td>${e.supports_tools ? '✓' : '—'}</td>
      <td>${e.supports_json ? '✓' : '—'}</td>
      <td>${e.max_context.toLocaleString()}</td>
      <td>${escText(e.cost_tier)}</td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="color:var(--text-muted);">No registry entries.</td></tr>';
}

async function loadRoleRouting() {
  try {
    const data = await api('/api/role-routing');
    _roleRoutingRoles = data.roles;
    _roleRoutingModels = data.role_models || {};
    renderRoleRoutingRows();
  } catch (e) {
    toast(`Failed to load role routing: ${escText(e.message)}`, 'error');
  }
}

function renderRoleRoutingRows() {
  const container = document.getElementById('role-routing-rows');
  if (!container || !_roleRoutingRoles.length) return;
  container.innerHTML = _roleRoutingRoles.map(role => `
    <div class="role-routing-row" data-role="${escText(role)}">
      <div class="role-routing-role">${escText(ROLE_LABELS[role] || role)}
        <span>${escText(ROLE_HINTS[role] || '')}</span>
      </div>
      <select class="role-routing-select" data-role="${escText(role)}"></select>
    </div>
  `).join('');
  renderRoleRoutingModelOptions();
}

function renderRoleRoutingModelOptions() {
  document.querySelectorAll('.role-routing-select').forEach(sel => {
    const role = sel.dataset.role;
    const current = _roleRoutingModels[role] || '';
    const options = [`<option value="">Default (use the model picked in Simulations)</option>`];
    _registryEntries.forEach(e => {
      options.push(`<option value="${escText(e.id)}">${escText(e.id)} (${escText(e.source)})</option>`);
    });
    if (current && !_registryEntries.some(e => e.id === current)) {
      options.push(`<option value="${escText(current)}">${escText(current)} (custom)</option>`);
    }
    sel.innerHTML = options.join('');
    sel.value = current;
  });
}

async function saveRoleRouting() {
  const status = document.getElementById('role-routing-status');
  const btn = document.getElementById('role-routing-save-btn');
  btn.disabled = true;
  status.className = 'status running';
  status.textContent = 'Saving…';
  status.style.display = 'block';
  try {
    const rows = Array.from(document.querySelectorAll('.role-routing-select'));
    for (const sel of rows) {
      await api('/api/role-routing', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: sel.dataset.role, model: sel.value || null }),
      });
    }
    status.className = 'status done';
    status.textContent = 'Saved — takes effect on the next sim run.';
    toast('Role routing saved', 'success');
    await loadRoleRouting();
  } catch (e) {
    status.className = 'status';
    status.style.display = 'block';
    toast(`Failed to save role routing: ${escText(e.message)}`, 'error');
  } finally {
    btn.disabled = false;
  }
}
