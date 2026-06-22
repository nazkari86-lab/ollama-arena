// ═══════════════════════════════════════════════════════════════
// MEMORY STRATEGY PREVIEW — calls /api/strategy whenever model_a
// or model_b changes, then renders the badge / gauge in the
// "🧠 Memory Strategy" card on the Battle tab.
// ═══════════════════════════════════════════════════════════════
const _STRATEGY_VIS = {
  CONCURRENT:   { icon: '⚡', label: 'CONCURRENT',   color: 'var(--accent-green)' },
  HOT_SWAP:     { icon: '↔️', label: 'HOT SWAP',     color: 'var(--accent-blue)' },
  PIPELINE:     { icon: '🔁', label: 'PIPELINE',     color: '#f59e0b' },
  INSUFFICIENT: { icon: '⛔', label: 'INSUFFICIENT', color: 'var(--accent-red)' },
};
let _strategyDebounce = null;
async function previewStrategy() {
  const a = document.getElementById('model-a')?.value;
  const b = document.getElementById('model-b')?.value;
  const badge  = document.getElementById('strategy-badge');
  const reason = document.getElementById('strategy-reason');
  if (!a || !b || a === b) {
    if (badge)  badge.textContent = '—';
    if (reason) reason.textContent = a === b ? 'Pick two different models.' : 'Pick two models to preview.';
    return;
  }
  try {
    const d = await api('/api/strategy', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model_a: a, model_b: b}),
    });
    const v = _STRATEGY_VIS[d.strategy] || _STRATEGY_VIS.CONCURRENT;
    badge.textContent = `${v.icon} ${v.label}`;
    badge.style.background = `${v.color}26`;
    badge.style.borderColor = v.color;
    badge.style.color = v.color;
    reason.textContent = d.reason;
    document.getElementById('strategy-a-size').textContent = (d.model_a_gb || 0).toFixed(1);
    document.getElementById('strategy-b-size').textContent = (d.model_b_gb || 0).toFixed(1);
    document.getElementById('strategy-usable').textContent = (d.usable_ram_gb || 0).toFixed(1);
    document.getElementById('strategy-total').textContent  = (d.total_ram_gb  || 0).toFixed(1);
    const used  = (d.model_a_gb || 0) + (d.model_b_gb || 0);
    const pct   = d.usable_ram_gb ? Math.min(100, (used / d.usable_ram_gb) * 100) : 0;
    const fill  = document.getElementById('strategy-gauge-fill');
    if (fill) {
      fill.style.width = pct + '%';
      fill.style.background = (pct > 100) ? 'var(--accent-red)' : `linear-gradient(90deg, ${v.color}, var(--accent-blue))`;
    }
  } catch(e) {
    badge.textContent = '⚠';
    reason.textContent = `Strategy preview unavailable: ${escText(e.message)}`;
  }
}
function schedulePreviewStrategy() {
  clearTimeout(_strategyDebounce);
  _strategyDebounce = setTimeout(previewStrategy, 250);
}

let _modelRefreshTimer = null;
let _modelRetryCount = 0;

function _showOllamaWarning(show) {
  let banner = document.getElementById('ollama-offline-banner');
  if (show) {
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'ollama-offline-banner';
      banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#f85149;color:#fff;padding:10px 20px;text-align:center;font-size:14px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:12px;';
      banner.innerHTML = '⚠️ Ollama is offline — run <code style="background:rgba(0,0,0,0.25);padding:2px 6px;border-radius:4px;">ollama serve</code> in terminal, then click &nbsp;<button id="ollama-refresh-models-btn" style="background:#fff;color:#c0392b;border:none;border-radius:4px;padding:4px 12px;cursor:pointer;font-weight:700;">🔄 Refresh Models</button>';
      document.body.prepend(banner);
      // CSP's script-src has no 'unsafe-inline', which blocks onclick="..."
      // attributes entirely (nonces/hashes never apply to event-handler
      // attributes) -- wire this button via addEventListener instead.
      banner.querySelector('#ollama-refresh-models-btn').addEventListener('click', () => loadModels(true));
    }
    banner.style.display = 'flex';
  } else if (banner) {
    banner.style.display = 'none';
  }
}

async function loadModels(manual = false) {
  let models = [];
  try {
    models = await api('/api/models');
  } catch(e) {
    models = [];
  }

  const opts = models.map(m => `<option value="${m}">${m}</option>`).join('');
  ['model-a','model-b', 'play-model-a', 'play-model-b', 'report-model',
   'tourney-models', 'royale-models', 'spec-model-select', 'vs-model-select'].forEach(id => {
    const s = document.getElementById(id);
    if (s) s.innerHTML = opts || '<option value="" disabled>No models — start Ollama</option>';
  });

  // Hook strategy preview into model A / B changes
  ['model-a','model-b'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.dataset.stratHooked) {
      el.addEventListener('change', schedulePreviewStrategy);
      el.dataset.stratHooked = '1';
    }
  });

  if (models.length === 0) {
    _showOllamaWarning(true);
    // Auto-retry with backoff (up to 5 attempts, max 30s interval)
    if (!manual) {
      _modelRetryCount++;
      const delay = Math.min(5000 * _modelRetryCount, 30000);
      clearTimeout(_modelRefreshTimer);
      _modelRefreshTimer = setTimeout(() => loadModels(), delay);
    }
    return;
  }

  // Models loaded successfully
  _showOllamaWarning(false);
  _modelRetryCount = 0;
  clearTimeout(_modelRefreshTimer);

  if (manual) toast(`✅ Loaded <b>${models.length}</b> models from Ollama`, 'success', 3000);

  if (models.length >= 2) {
    const setDiff = (idA, idB) => {
      const a = document.getElementById(idA);
      const b = document.getElementById(idB);
      if (a && b) { a.selectedIndex = 0; b.selectedIndex = 1; }
    };
    setDiff('model-a', 'model-b');
    setDiff('play-model-a', 'play-model-b');

    const tModels = document.getElementById('tourney-models');
    if (tModels && models.length >= 3) {
      for(let i=0; i<Math.min(models.length, 4); i++) tModels.options[i].selected = true;
    }
    const rModels = document.getElementById('royale-models');
    if (rModels && models.length >= 3) {
      for(let i=0; i<Math.min(models.length, 3); i++) rModels.options[i].selected = true;
    }
    schedulePreviewStrategy();
    // Upgrade the naive "first two models" default above to a
    // hardware-aware pick, once per page load. Best-effort and silent:
    // if it fails or the API is slow, the naive default above already
    // stands, so there's no broken/empty state either way.
    autoPickBestModelsOnce();
  }
}

let _autoPickDone = false;
async function autoPickBestModelsOnce() {
  if (_autoPickDone) return;
  _autoPickDone = true;
  try {
    const data = await api('/api/hardware/scan');
    applyBestTwoModels(data.best_two, { silent: true });
  } catch(e) { /* naive default from loadModels() above already applied */ }
}

async function loadLeaderboard() {
  const board = await api('/api/leaderboard');
  const hist = await api('/api/history?limit=1000');
  animateNumber(document.getElementById('stat-models'), board.length);
  animateNumber(document.getElementById('stat-matches'), hist.length);
  const lbHtml = await html('/charts/leaderboard');
  // Wrap with search-filter capability
  document.getElementById('leaderboard-table').innerHTML = `
    <div class="search-wrap"><input id="lb-search" type="text" placeholder="Search models…" autocomplete="off"></div>
    <div id="lb-content">${lbHtml}</div>`;
  const lb2 = document.getElementById('leaderboard-table-2');
  if (lb2) lb2.innerHTML = `
    <div class="search-wrap"><input id="lb-search-2" type="text" placeholder="Search models…" autocomplete="off"></div>
    <div id="lb-content-2">${lbHtml}</div>`;
  wireLeaderboardSearch('lb-search', 'lb-content');
  wireLeaderboardSearch('lb-search-2', 'lb-content-2');
  wireSortableColumns('lb-content');
  wireSortableColumns('lb-content-2');
}

function wireLeaderboardSearch(inputId, contentId) {
  const inp = document.getElementById(inputId);
  const root = document.getElementById(contentId);
  if (!inp || !root) return;
  inp.addEventListener('input', () => {
    const q = inp.value.toLowerCase().trim();
    root.querySelectorAll('tr').forEach((tr, i) => {
      if (i === 0) return;  // header
      tr.style.display = !q || tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

function wireSortableColumns(contentId) {
  const root = document.getElementById(contentId);
  if (!root) return;
  const headers = root.querySelectorAll('th');
  headers.forEach((th, idx) => {
    th.style.cursor = 'pointer';
    th.setAttribute('data-tip', 'Click to sort');
    let asc = false;
    th.addEventListener('click', () => {
      const table = th.closest('table');
      if (!table) return;
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      asc = !asc;
      rows.sort((a, b) => {
        const av = a.children[idx]?.textContent.trim() || '';
        const bv = b.children[idx]?.textContent.trim() || '';
        const an = parseFloat(av.replace(/[^\d.-]/g, ''));
        const bn = parseFloat(bv.replace(/[^\d.-]/g, ''));
        if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

async function runMatch() {
  const ma = document.getElementById('model-a').value;
  const mb = document.getElementById('model-b').value;
  const cat = document.getElementById('category').value;
  const n = parseInt(document.getElementById('n-tasks').value);
  const concurrency = parseInt(document.getElementById('concurrency').value);
  if (!ma || !mb) return toast('No models loaded — start Ollama and click 🔄 Refresh Models', 'error');
  if (ma === mb) return alert('Neural models must be distinct entities');

  // Blind Arena bookkeeping — captured here so WS events know how to mask
  _blindModeActive = !!document.getElementById('battle-blind-mode')?.checked;
  _blindMapping = { a: ma, b: mb };
  if (_blindModeActive) {
    toast('🎭 <b>Blind Mode</b> — names hidden until match completes.', 'info', 3500);
  }

  document.getElementById('battle-leaderboard-card').style.display = 'none';
  document.getElementById('battle-arena-card').style.display = 'block';
  
  // Wait for the DOM layout to update the container dimensions
  setTimeout(async () => {
    if(window.arenaVisualizer) window.arenaVisualizer.destroy();
    window.arenaVisualizer = new ThreeJSArena('arena-3d-container', ma, mb, n);

    const btn = document.getElementById('run-btn');
    btn.disabled = true; btn.textContent = 'Synchronizing...';
    document.getElementById('match-log').innerHTML = '';
    const s = document.getElementById('match-status');
    s.className = 'status running'; s.textContent = 'Awaiting neural response stream...';

    const data = await api('/api/match', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({model_a: ma, model_b: mb, category: cat, n, concurrency})
    });
    currentJobId = data.job_id;
  }, 100);
}

async function runRoyale() {
  const s = document.getElementById('royale-models');
  const models = Array.from(s.selectedOptions).map(opt => opt.value).filter(v => !!v);
  if (models.length === 0) return toast('No models loaded — start Ollama and click 🔄 Refresh Models', 'error');
  if (models.length < 3) return alert("Battle Royale requires at least 3 contenders.");
  const cat = document.getElementById('royale-category').value;
  const n = parseInt(document.getElementById('royale-n').value);

  const btn = document.getElementById('royale-run-btn');
  btn.disabled = true; btn.textContent = 'Initiating...';
  document.getElementById('royale-log').innerHTML = '';
  document.getElementById('royale-log').style.display = 'block';
  document.getElementById('royale-rankings').style.display = 'none';
  const prog = document.getElementById('royale-progress');
  prog.innerHTML = `<div style="font-size:24px; font-weight:800; color:var(--accent-blue)">Awaiting battleground initialization...</div>`;

  try {
    const data = await api('/api/royale', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({models, category: cat, n})
    });
    currentJobId = data.job_id;
  } catch(e) { 
    alert(e.message); 
    btn.disabled = false; 
    btn.textContent = 'Initiate Royale'; 
  }
}

async function runTournament() {
  const s = document.getElementById('tourney-models');
  const models = Array.from(s.selectedOptions).map(opt => opt.value).filter(v => !!v);
  if (models.length === 0) return toast('No models loaded — start Ollama and click 🔄 Refresh Models', 'error');
  if (models.length < 2) return alert("Select at least 2 models for the tournament.");
  const cat = document.getElementById('tourney-category').value;
  const n = parseInt(document.getElementById('tourney-n').value);
  const concurrency = parseInt(document.getElementById('tourney-concurrency').value);

  const btn = document.getElementById('tourney-run-btn');
  btn.disabled = true; btn.textContent = 'Initializing...';
  document.getElementById('tournament-log').innerHTML = '';
  document.getElementById('tournament-log').style.display = 'none';
  const prog = document.getElementById('tournament-progress');
  prog.innerHTML = `<div style="font-size:18px; color:var(--accent-blue)">Awaiting matchmaking server...</div>`;
  
  try {
    const data = await api('/api/tournament', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({models, category: cat, n, concurrency})
    });
    currentJobId = data.job_id;
  } catch(e) { alert(e.message); btn.disabled = false; btn.textContent = 'Commence Tournament'; }
}

// ═══════════════════════════════════════════════════════════════
// AGENT TRACE RENDERER — reusable for Playground + Inspect
// ═══════════════════════════════════════════════════════════════
function renderAgentTrace(trace, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!trace || !Array.isArray(trace) || trace.length === 0) {
    el.innerHTML = '';
    return;
  }

  const toolCount = trace.reduce((n, s) => n + (s.tool_calls ? s.tool_calls.length : 0), 0);
  const hasErrors = trace.some(s => s.error);

  let h = `<div class="agent-trace" id="${containerId}-trace">
    <div class="agent-trace-header">
      <div class="trace-title">
        🔗 Agent Trace
        <span class="badge badge-blue" style="font-size:10px; padding:2px 8px;">${trace.length} step${trace.length > 1 ? 's' : ''}</span>
        ${toolCount > 0 ? `<span class="badge badge-green" style="font-size:10px; padding:2px 8px;">${toolCount} tool call${toolCount > 1 ? 's' : ''}</span>` : ''}
        ${hasErrors ? `<span class="badge" style="font-size:10px; padding:2px 8px; background:rgba(248,81,73,0.15); color:var(--accent-red); border:1px solid rgba(248,81,73,0.3);">ERROR</span>` : ''}
      </div>
      <div class="trace-meta">
        <button class="trace-expand-btn" aria-label="Toggle trace">▼</button>
      </div>
    </div>
    <div class="agent-trace-body">
      <div class="agent-trace-body-inner">`;

  trace.forEach((step, idx) => {
    const hasError = !!step.error;
    h += `<div class="trace-step ${hasError ? 'has-error' : ''}">
      <div class="trace-step-num">${step.step || idx + 1}</div>`;

    if (step.content) {
      h += `<div class="trace-step-label">🧠 Model Reasoning</div>
        <div class="trace-content">${escText(step.content)}</div>`;
    }

    if (step.tool_calls && step.tool_calls.length > 0) {
      step.tool_calls.forEach((tc, tcIdx) => {
        const fn = tc.function || tc;
        const name = fn.name || 'unknown';
        const args = fn.arguments || '';
        let argsDisplay = args;
        if (typeof args === 'string') {
          try { argsDisplay = JSON.stringify(JSON.parse(args), null, 2); } catch(_) { argsDisplay = args; }
        } else if (typeof args === 'object') {
          argsDisplay = JSON.stringify(args, null, 2);
        }
        h += `<div class="trace-tool-call">
          <div class="tool-name">⚡ ${escText(name)}</div>
          <div class="tool-args">${escText(argsDisplay)}</div>
        </div>`;

        if (step.tool_results && step.tool_results[tcIdx]) {
          const tr = step.tool_results[tcIdx];
          let resultStr = tr.result;
          if (typeof resultStr === 'object') resultStr = JSON.stringify(resultStr, null, 2);
          h += `<div class="trace-tool-result">
            <div class="result-label">📋 Result from ${escText(tr.name || name)}</div>
            <div class="result-data">${escText(String(resultStr || ''))}</div>
          </div>`;
        }
      });
    }

    if (step.error) {
      h += `<div class="trace-error">❌ ${escText(step.error)}</div>`;
    }

    h += `</div>`;
  });

  h += `</div></div></div>`;
  el.innerHTML = h;
  const header = el.querySelector('.agent-trace-header');
  if (header) header.addEventListener('click', () => header.parentElement.classList.toggle('expanded'));
}

// Convert ```fenced``` blocks to <pre><code> but escape every other character.
// The result is then sanitized by safeHTML() before reaching the DOM.
function formatCodeBlocks(text) {
  if (!text) return "";
  const escaped = String(text).replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
  const withCode = escaped.replace(/```(?:[a-z]+)?\n([\s\S]*?)```/g,
    (m, code) => `<pre><code class="hljs">${code}</code></pre>`);
  return safeHTML(withCode);
}

async function generatePlayground() {
  const ma = document.getElementById('play-model-a').value;
  const mb = document.getElementById('play-model-b').value;
  const prompt = document.getElementById('play-prompt').value.trim();
  if (!ma || !mb) return toast('No models loaded — start Ollama and click 🔄 Refresh Models', 'error');
  if (ma === mb || !prompt) return alert('Setup conflict or missing instruction');

  const btn = document.getElementById('play-gen-btn');
  btn.disabled = true; btn.textContent = 'Generating...';
  
  document.getElementById('play-battlefield').style.display = 'block';
  document.getElementById('play-vote-controls').style.display = 'none';
  document.getElementById('play-status').style.display = 'none';
  document.getElementById('play-model-x-reveal').style.display = 'none';
  document.getElementById('play-model-y-reveal').style.display = 'none';

  // Spinner UI
  const loaderHtml = `<div style="text-align:center; padding:40px; color:var(--accent-blue);">
    <div style="animation:pulse 1s infinite">🧠 Processing prompt...</div>
  </div>`;
  document.getElementById('play-resp-x').innerHTML = loaderHtml;
  document.getElementById('play-resp-y').innerHTML = loaderHtml;

  // Decide blind swap
  const swap = Math.random() > 0.5;
  const modelX = swap ? mb : ma;
  const modelY = swap ? ma : mb;

  currentPlayData = {
    model_a_name: ma,
    model_b_name: mb,
    prompt: prompt,
    model_x: swap ? 'model_b' : 'model_a',
    model_y: swap ? 'model_a' : 'model_b',
    response_x: '', response_y: '',
    tps_x: 0, tps_y: 0,
    latency_x: 0, latency_y: 0,
    agent_trace_x: null, agent_trace_y: null
  };

  const enableTools = document.getElementById('play-enable-tools').checked;
  document.getElementById('play-trace-x').innerHTML = '';
  document.getElementById('play-trace-y').innerHTML = '';

  let completedCount = 0;
  const checkCompletion = () => {
    completedCount++;
    if (completedCount === 2) {
      btn.disabled = false;
      btn.textContent = 'Execute Generation';
      document.getElementById('play-vote-controls').style.display = 'flex';
      if (!document.getElementById('play-blind-test').checked) revealPlayground();
    }
  };

  // Fire Request X
  const payloadX = {model: modelX, prompt};
  if (enableTools) payloadX.enable_tools = true;
  api('/api/playground/generate_single', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payloadX)
  }).then(data => {
    currentPlayData.response_x = data.response;
    currentPlayData.tps_x = data.tps;
    currentPlayData.latency_x = data.latency_s;
    if (data.agent_trace) currentPlayData.agent_trace_x = data.agent_trace;
    
    document.getElementById('play-resp-x').innerHTML = `
      <div style="margin-bottom:15px; display:flex; gap:10px;">
        <span class="badge badge-blue">⏱ ${data.latency_s.toFixed(2)}s</span>
        <span class="badge badge-green">⚡ ${data.tps.toFixed(1)} t/s</span>
        ${data.finish_reason && data.finish_reason !== 'stop' ? `<span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);">${escText(data.finish_reason)}</span>` : ''}
      </div>
      <div>${formatCodeBlocks(data.response)}</div>
    `;
    document.getElementById('play-resp-x').querySelectorAll('pre code').forEach(b => hljs.highlightElement(b));
    if (data.agent_trace) renderAgentTrace(data.agent_trace, 'play-trace-x');
    checkCompletion();
  }).catch(e => {
    document.getElementById('play-resp-x').innerHTML = `<div style="color:var(--accent-red)">Error: ${e.message}</div>`;
    checkCompletion();
  });

  // Fire Request Y
  const payloadY = {model: modelY, prompt};
  if (enableTools) payloadY.enable_tools = true;
  api('/api/playground/generate_single', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payloadY)
  }).then(data => {
    currentPlayData.response_y = data.response;
    currentPlayData.tps_y = data.tps;
    currentPlayData.latency_y = data.latency_s;
    if (data.agent_trace) currentPlayData.agent_trace_y = data.agent_trace;
    
    document.getElementById('play-resp-y').innerHTML = `
      <div style="margin-bottom:15px; display:flex; gap:10px;">
        <span class="badge badge-blue">⏱ ${data.latency_s.toFixed(2)}s</span>
        <span class="badge badge-green">⚡ ${data.tps.toFixed(1)} t/s</span>
        ${data.finish_reason && data.finish_reason !== 'stop' ? `<span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);">${escText(data.finish_reason)}</span>` : ''}
      </div>
      <div>${formatCodeBlocks(data.response)}</div>
    `;
    document.getElementById('play-resp-y').querySelectorAll('pre code').forEach(b => hljs.highlightElement(b));
    if (data.agent_trace) renderAgentTrace(data.agent_trace, 'play-trace-y');
    checkCompletion();
  }).catch(e => {
    document.getElementById('play-resp-y').innerHTML = `<div style="color:var(--accent-red)">Error: ${e.message}</div>`;
    checkCompletion();
  });
}

function revealPlayground() {
  const x = document.getElementById('play-model-x-reveal');
  const y = document.getElementById('play-model-y-reveal');
  const nX = currentPlayData.model_x === 'model_a' ? currentPlayData.model_a_name : currentPlayData.model_b_name;
  const nY = currentPlayData.model_y === 'model_a' ? currentPlayData.model_a_name : currentPlayData.model_b_name;
  x.textContent = `[${nX}] ${currentPlayData.tps_x.toFixed(1)} tps`;
  y.textContent = `[${nY}] ${currentPlayData.tps_y.toFixed(1)} tps`;
  x.style.display = y.style.display = 'inline';
}

async function votePlayground(v) {
  const s = document.getElementById('play-status');
  document.getElementById('play-vote-controls').style.display = 'none';
  s.className = 'status running'; s.textContent = 'Logging preference...'; s.style.display = 'block';
  try {
    const res = await api('/api/playground/vote', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ ...currentPlayData, voted_for: v })
    });
    revealPlayground();
    s.className = 'status done';
    s.innerHTML = `Cognitive Logged. ELO Updated. Winner: <b>${v === 'draw' ? 'Equal' : (v === 'x' ? res.model_x : res.model_y)}</b>`;
    loadAll();
  } catch(e) { alert(e.message); }
}

async function loadCharts() {
  ['elo', 'radar', 'heatmap'].forEach(async (t) => {
    try {
      const h = await html('/charts/' + t);
      const el = document.getElementById('chart-' + t);
      el.innerHTML = h;
      el.querySelectorAll('script').forEach(s => {
        const ns = document.createElement('script');
        // innerHTML-inserted <script> tags never execute on their own, so
        // they're recreated here — but a freshly created element has no
        // nonce, and CSP's script-src requires one for inline scripts.
        // window.__CSP_NONCE__ is set by the page's own nonce'd bootstrap
        // script (see templates/base.html) for exactly this purpose.
        if (window.__CSP_NONCE__) ns.nonce = window.__CSP_NONCE__;
        if (s.src) ns.src = s.src; else ns.textContent = s.textContent;
        s.parentNode.replaceChild(ns, s);
      });
    } catch(e){}
  });
}

async function loadHistory() {
  const q = document.getElementById('history-search')?.value || '';
  const history = q.trim()
    ? await api(`/api/history/search?q=${encodeURIComponent(q)}&limit=100`)
    : await api('/api/history?limit=100');
  renderEvalsTable('history-table', history || []);
}

let _historySearchDebounce = null;
document.getElementById('history-search')?.addEventListener('input', () => {
  clearTimeout(_historySearchDebounce);
  _historySearchDebounce = setTimeout(loadHistory, 250);
});

// Delegated once on the static #history-table container -- survives every
// loadHistory() re-render since only its children (not the container
// itself) get replaced via innerHTML.
document.getElementById('history-table')?.addEventListener('click', (e) => {
  const btn = e.target.closest('.export-match-btn');
  if (btn) exportMatch(Number(btn.dataset.matchId), btn);
});

async function exportMatch(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  try {
    const res = await api(`/api/export_match/${id}`);
    toast(`Report exported to: <b>${res.path}</b>`, 'success', 5000);
  } catch(e) { toast(`Export failed: ${e.message}`, 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = 'Export'; } }
}

async function loadHallucinations() {
  const board = await api('/api/anti-leaderboard');
  if (!board || board.length === 0) {
    document.getElementById('anti-leaderboard-table').innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center">No hallucination data recorded yet. Run matches with <code>--judge</code> enabled.</div>';
    return;
  }
  
  let h = `<table><thead><tr><th>Rank</th><th>Model</th><th>Halluc Rate</th><th>Count</th><th>Checked</th></tr></thead><tbody>`;
  board.forEach(e => {
    const rate = (e.halluc_rate * 100).toFixed(1) + '%';
    const rateColor = e.halluc_rate > 0.2 ? 'var(--accent-red)' : (e.halluc_rate > 0.05 ? '#f59e0b' : 'var(--accent-green)');
    h += `<tr>
      <td style="font-weight:700">#${e.rank}</td>
      <td><strong>${e.model}</strong></td>
      <td style="color:${rateColor}; font-weight:800;">${rate}</td>
      <td>${e.hallucinations}</td>
      <td>${e.total_checked}</td>
    </tr>`;
  });
  h += '</tbody></table>';
  document.getElementById('anti-leaderboard-table').innerHTML = h;
}

async function loadPerf() {
  document.getElementById('chart-perf').innerHTML = await html('/charts/perf');
  const data = await api('/api/perf');
  const stats = data.models || [];
  const rows = stats.map(s => `<tr><td><b>${s.model}</b></td><td>${s.n_samples}</td><td>${s.tps_mean.toFixed(1)}</td><td>${s.latency_mean_s.toFixed(2)}s</td><td>${s.ttft_mean_s.toFixed(2)}s</td></tr>`).join('');
  document.getElementById('perf-table').innerHTML = `<table><thead><tr><th>Model</th><th>Samples</th><th>TPS</th><th>Latency</th><th>TTFT</th></tr></thead><tbody>${rows}</tbody></table>`;
}

async function loadCategories() {
  const d = await api('/api/categories');
  animateNumber(document.getElementById('stat-tasks'), Object.values(d.stats).reduce((a,b)=>a+b, 0));
  animateNumber(document.getElementById('stat-languages'), d.languages.length);
  const opts = Object.keys(d.stats).map(c => `<option value="${c}">${c.toUpperCase()}</option>`).join('');
  document.getElementById('category').innerHTML = opts;
  document.getElementById('tourney-category').innerHTML = opts;
  document.getElementById('royale-category').innerHTML = opts;
}

async function loadDatasets() {
  const ds = await api('/api/datasets');
  document.getElementById('datasets-list').innerHTML = ds.map(d => `<div class="card" style="margin-bottom:0; display:flex; flex-direction:column;">
    <div style="font-weight:800; color:var(--accent-blue); font-size:16px">${d.name}</div>
    <div style="font-size:13px; color:var(--text-muted); margin:12px 0; flex:1; line-height:1.5;">${d.description}</div>
    <div style="display:flex; gap:12px; align-items:center; margin-top:auto; padding-top:16px; border-top:1px solid rgba(255,255,255,0.05);">
      <span class="badge badge-blue">${d.category}</span>
      <span class="badge ${d.cached?'badge-green':'badge-blue'}">${d.cached?'CACHED':'REMOTE'}</span>
      <button class="btn pull-dataset-btn" data-dataset-name="${escText(d.name)}" style="width:auto; padding:6px 20px; font-size:11px; margin-left:auto;">PULL</button>
    </div>
  </div>`).join('');
}

document.getElementById('datasets-list')?.addEventListener('click', (e) => {
  const btn = e.target.closest('.pull-dataset-btn');
  if (btn) pullDataset(btn.dataset.datasetName);
});

async function pullDataset(n) {
  await api('/api/pull_dataset', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: n, limit: 50}) });
  alert(`Dataset ${n} pull initiated.`);
}

// ═══════════════════════════════════════════════════════════════
// 3.1 — Visual Diff Viewer (jsdiff line-level)
// 3.2 — Retry Task (per-task rerun via /api/retry_task)
// ═══════════════════════════════════════════════════════════════
function _renderDiff(a, b) {
  // Falls back to "diff unavailable" if the CDN is blocked
  if (!window.Diff || !window.Diff.diffLines) return null;
  const parts = window.Diff.diffLines(String(a || ''), String(b || ''));
  let out = '';
  for (const p of parts) {
    const lines = String(p.value).split('\n').filter(l => l !== '');
    for (const line of lines) {
      const safe = escText(line);
      if (p.added) {
        out += `<div style="background:rgba(63,185,80,0.12); border-left:3px solid var(--accent-green); padding:3px 10px; color:var(--accent-green); font-family:'JetBrains Mono',monospace;">+ ${safe}</div>`;
      } else if (p.removed) {
        out += `<div style="background:rgba(248,81,73,0.12); border-left:3px solid var(--accent-red); padding:3px 10px; color:var(--accent-red); font-family:'JetBrains Mono',monospace;">- ${safe}</div>`;
      } else {
        out += `<div style="padding:3px 10px; color:var(--text-muted); font-family:'JetBrains Mono',monospace;">  ${safe}</div>`;
      }
    }
  }
  return out;
}

document.getElementById('inspect-results')?.addEventListener('click', (e) => {
  const diffBtn = e.target.closest('[data-action="toggle-diff"]');
  if (diffBtn) { toggleDiff(diffBtn, Number(diffBtn.dataset.idx)); return; }
  const retryBtn = e.target.closest('[data-action="retry-task"]');
  if (retryBtn) retryTask(retryBtn.dataset.taskId, retryBtn);
});

function toggleDiff(btn, runIdx) {
  const card = btn.closest('[data-task-id]');
  if (!card) return;
  // Find the i-th pair within the inspect results
  const cards = document.querySelectorAll('#inspect-results [data-task-id]');
  const target = cards[runIdx] || card;
  const aBox = target.querySelector('.resp-a');
  const bBox = target.querySelector('.resp-b');
  if (!aBox || !bBox) return;
  const isOn = target.dataset.diffOn === '1';
  if (isOn) {
    aBox.innerHTML = formatCodeBlocks(aBox.dataset.raw);
    bBox.innerHTML = formatCodeBlocks(bBox.dataset.raw);
    target.dataset.diffOn = '0';
    btn.style.background = 'rgba(88,166,255,0.12)';
    btn.textContent = '↔ Diff';
  } else {
    const d = _renderDiff(aBox.dataset.raw, bBox.dataset.raw);
    if (d == null) { toast('Diff library failed to load', 'warn'); return; }
    // Show the SAME diff in both panes; reading either gives the picture.
    aBox.innerHTML = `<div style="font-size:11px;">${safeHTML(d)}</div>`;
    bBox.innerHTML = `<div style="font-size:11px;">${safeHTML(d)}</div>`;
    target.dataset.diffOn = '1';
    btn.style.background = 'rgba(88,166,255,0.25)';
    btn.textContent = '↔ Diff ON';
  }
}
async function retryTask(taskId, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '↻ Running…'; }
  try {
    const d = await api(`/api/retry_task/${encodeURIComponent(taskId)}`, {method:'POST'});
    const winner = d.outcome === 'a_wins' ? d.model_a
                 : d.outcome === 'b_wins' ? d.model_b
                 : 'Tie';
    let msg = `Retry done — Winner: <b>${escText(winner)}</b> (A: ${(d.score_a*100).toFixed(0)}% vs B: ${(d.score_b*100).toFixed(0)}%)`;
    if (d.explanation_a || d.explanation_b) {
      msg += `<div style="margin-top:6px; font-size:11px; color:var(--text-muted)">`
           + (d.explanation_a ? `A: ${escText(d.explanation_a)}<br>` : '')
           + (d.explanation_b ? `B: ${escText(d.explanation_b)}` : '')
           + `</div>`;
    }
    toast(msg, 'success', 7000);
    // Refresh the inspect view so the new run shows up at the top
    document.getElementById('inspect-task-id').value = taskId;
    await loadInspect();
  } catch(e) {
    toast(`Retry failed: ${escText(e.message)}`, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '↻ Retry'; }
  }
}

async function loadInspect() {
  const tid = document.getElementById('inspect-task-id').value.trim();
  if(!tid) return;
  const res = document.getElementById('inspect-results');
  res.innerHTML = '<div class="status running" style="display:block;">Decrypting deep neural traces...</div>';
  try {
    const data = await api(`/api/task/${encodeURIComponent(tid)}`);
    if(!data.runs || !data.runs.length) return res.innerHTML = '<div class="status done" style="color:var(--accent-red); border-color:var(--accent-red);">No traces found for this ID.</div>';
    
    const info = data.runs[0];
    let h = `<div class="card" style="border-color:var(--accent-blue)">
      <div style="font-weight:800; color:var(--text-main); font-size:18px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center;">
        <span style="color:var(--accent-blue)">INSTRUCTION TRACE: <span style="color:var(--text-main); font-weight:600;">${escText(info.task_id)}</span></span>
        <span class="badge badge-blue">${escText(info.category)}</span>
      </div>
      <div style="font-size:14px; background:rgba(1,4,9,0.8); padding:20px; border-radius:var(--radius-inner); border:1px solid rgba(255,255,255,0.05); font-family:'JetBrains Mono', monospace; line-height:1.6">${escText(info.instruction)}</div>
    </div>`;

    data.runs.forEach((r, i) => {
      const isAWinner = r.outcome === 'a_wins';
      const isBWinner = r.outcome === 'b_wins';
      
      const formatCode = (text) => {
        const escaped = String(text ?? '').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
        const withCode = escaped.replace(/```(?:[a-z]+)?\n([\s\S]*?)```/g, (m, code) => `<pre style="margin-top:12px; margin-bottom:12px; border-radius:8px;"><code class="hljs">${code}</code></pre>`);
        return safeHTML(withCode);
      };

      const traceIdA = `inspect-trace-a-${i}`;
      const traceIdB = `inspect-trace-b-${i}`;

      h += `<div class="card" style="margin-bottom: 32px;" data-task-id="${escText(info.task_id)}">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; gap:12px; flex-wrap:wrap;">
          <h3 style="font-weight:800; color:var(--text-main); font-size:15px; text-transform:uppercase; letter-spacing:1px;">Simulation Run #${i+1}</h3>
          <div style="display:flex; gap:8px; align-items:center;">
            <button class="btn" data-action="toggle-diff" data-idx="${i}" data-tip="Toggle line-level diff between the two responses" style="width:auto; padding:5px 12px; font-size:11px; background:rgba(88,166,255,0.12); border-color:rgba(88,166,255,0.3); color:var(--accent-blue);">↔ Diff</button>
            <button class="btn" data-action="retry-task" data-task-id="${escText(info.task_id)}" data-tip="Re-run this single task — useful after a Docker/network blip" style="width:auto; padding:5px 12px; font-size:11px; background:rgba(245,158,11,0.12); border-color:rgba(245,158,11,0.3); color:#f59e0b;">↻ Retry</button>
            <span class="badge ${r.outcome === 'draw' ? 'badge-blue' : 'badge-green'}" style="font-size:12px; padding:6px 16px;">${r.outcome.replace('_', ' ').toUpperCase()}</span>
          </div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:24px">

          <div style="border: 1px solid ${isAWinner ? 'var(--accent-green)' : 'rgba(255,255,255,0.08)'}; border-radius: var(--radius-inner); overflow: hidden; background: rgba(1,4,9,0.6); box-shadow: ${isAWinner ? '0 0 20px rgba(63, 185, 80, 0.15)' : 'none'}; transition: transform 0.2s;">
            <div style="background: rgba(255,255,255,0.03); padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05);">
              <strong style="color:var(--accent-blue); font-size:14px;">${escText(r.model_a)}</strong>
              <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Score: <b style="color:${isAWinner?'var(--accent-green)':'var(--text-main)'}; font-size:14px;">${(r.score_a*100).toFixed(1)}%</b></div>
            </div>
            <div class="resp-a" data-raw="${escText(r.response_a)}" style="padding: 20px; font-size:13px; line-height:1.7; max-height: 500px; overflow-y: auto;">
              ${formatCode(r.response_a)}
            </div>
            <div id="${traceIdA}"></div>
          </div>

          <div style="border: 1px solid ${isBWinner ? 'var(--accent-green)' : 'rgba(255,255,255,0.08)'}; border-radius: var(--radius-inner); overflow: hidden; background: rgba(1,4,9,0.6); box-shadow: ${isBWinner ? '0 0 20px rgba(63, 185, 80, 0.15)' : 'none'}; transition: transform 0.2s;">
            <div style="background: rgba(255,255,255,0.03); padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05);">
              <strong style="color:var(--accent-blue); font-size:14px;">${escText(r.model_b)}</strong>
              <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Score: <b style="color:${isBWinner?'var(--accent-green)':'var(--text-main)'}; font-size:14px;">${(r.score_b*100).toFixed(1)}%</b></div>
            </div>
            <div class="resp-b" data-raw="${escText(r.response_b)}" style="padding: 20px; font-size:13px; line-height:1.7; max-height: 500px; overflow-y: auto;">
              ${formatCode(r.response_b)}
            </div>
            <div id="${traceIdB}"></div>
          </div>

        </div>
      </div>`;
    });
    
    res.innerHTML = h;
    
    res.querySelectorAll('pre code').forEach((block) => {
      hljs.highlightElement(block);
    });

    data.runs.forEach((r, i) => {
      if (r.tool_call_a) renderAgentTrace(r.tool_call_a, `inspect-trace-a-${i}`);
      if (r.tool_call_b) renderAgentTrace(r.tool_call_b, `inspect-trace-b-${i}`);
    });

  } catch(e){ 
    res.innerHTML = `<div class="status done" style="color:var(--accent-red); border-color:var(--accent-red); display:block;">Error: ${e.message}</div>`; 
  }
}

async function loadReport() {
  const m = document.getElementById('report-model').value;
  const res = document.getElementById('report-results');
  res.innerHTML = '<div class="status running" style="display:block;">Synthesizing data...</div>';
  try {
    const data = await api(`/api/report/${encodeURIComponent(m)}`);
    let h = `<table><thead><tr><th>Category</th><th>Win Rate</th><th>Total Configured</th></tr></thead><tbody>`;
    data.stats.forEach(s => {
      h += `<tr><td><span style="font-weight:600; color:var(--text-main);">${s.category.toUpperCase()}</span></td><td><b style="color:var(--accent-blue); font-size:16px;">${(s.win_rate*100).toFixed(1)}%</b></td><td>${s.total}</td></tr>`;
    });
    h += '</tbody></table>';
    res.innerHTML = h;
  } catch(e){ alert(e.message); }
}

async function loadAll() {
  await loadLeaderboard();
  loadCharts();
}
