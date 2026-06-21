// ═══════════════════════════════════════════════════════════════
// Speculative Decoding UI (v2 — streaming, vs-base, bench-all)
// ═══════════════════════════════════════════════════════════════
let _specSparklines = {};  // name → [tps history]

document.getElementById('spec-servers-grid')?.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const name = btn.dataset.name;
  if (btn.dataset.action === 'spec-start') specStart(name, btn);
  else if (btn.dataset.action === 'spec-stop') specStop(name, btn);
  else if (btn.dataset.action === 'spec-try') specQuickTry(name);
});

async function loadSpec() {
  const grid = document.getElementById('spec-servers-grid');
  const sel  = document.getElementById('spec-model-select');
  const vsSel = document.getElementById('vs-model-select');
  try {
    const servers = await api('/api/spec/servers');
    const opts = servers.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
    if (sel) sel.innerHTML = opts;
    if (vsSel) vsSel.innerHTML = opts;

    grid.innerHTML = servers.map(s => {
      const running = s.running;
      const color   = running ? 'var(--accent-green)' : 'var(--text-muted)';
      const dot     = running ? '●' : '○';
      const btnStart = `<button class="btn" data-action="spec-start" data-name="${escText(s.name)}" style="width:auto;padding:6px 12px;font-size:11px;" ${running ? 'disabled' : ''}>▶ START</button>`;
      const btnStop  = `<button class="btn" data-action="spec-stop" data-name="${escText(s.name)}" style="width:auto;padding:6px 12px;font-size:11px;background:rgba(248,81,73,0.15);border-color:rgba(248,81,73,0.3);color:var(--accent-red);" ${!running ? 'disabled' : ''}>■ STOP</button>`;
      const btnTry   = running ? `<button class="btn" data-action="spec-try" data-name="${escText(s.name)}" style="width:auto;padding:6px 12px;font-size:11px;background:rgba(88,166,255,0.12);border-color:rgba(88,166,255,0.3);color:var(--accent-blue);" data-tip="Quick TPS test">⚡ TRY</button>` : '';
      return `<div class="spec-card ${running ? 'running' : ''}">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px;">
          <span style="font-size:18px; color:${color}; line-height:1">${dot}</span>
          <div style="min-width:0; flex:1;">
            <div style="font-weight:800; color:var(--text-main); font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${s.name}</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">:${s.port}</div>
          </div>
        </div>
        <div style="font-size:11px; color:var(--text-muted); display:grid; grid-template-columns:auto 1fr; gap:4px 10px; line-height:1.7; margin-bottom:12px;">
          <span>Main</span><span style="color:var(--text-main); font-family:'JetBrains Mono',monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${s.main}</span>
          <span>Draft</span><span style="color:var(--accent-blue); font-family:'JetBrains Mono',monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${s.draft}</span>
          <span>Ctx</span><span style="color:var(--text-main);">${(s.ctx/1024).toFixed(0)}k</span>
          ${s.pid ? `<span>PID</span><span style="color:var(--accent-green);">${s.pid}</span>` : ''}
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">${btnStart}${btnStop}${btnTry}</div>
      </div>`;
    }).join('');
  } catch(e) {
    grid.innerHTML = `<div style="color:var(--accent-red); padding:20px;">Error loading spec servers: ${e.message}</div>`;
    toast(`Spec servers: ${e.message}`, 'error');
  }
}

async function specStart(name, btn) {
  btn.disabled = true; btn.textContent = '⏳ Starting…';
  toast(`Starting <b>${name}</b>… (may take 30s)`, 'info', 3000);
  try {
    await api(`/api/spec/start/${encodeURIComponent(name)}`, {method:'POST'});
    toast(`<b>${name}</b> started`, 'success');
    await loadSpec();
  } catch(e) {
    toast(`Failed to start ${name}: ${e.message}`, 'error');
    btn.disabled = false; btn.textContent = '▶ START';
  }
}

async function specStop(name, btn) {
  btn.disabled = true; btn.textContent = '⏳ Stopping…';
  try {
    await api(`/api/spec/stop/${encodeURIComponent(name)}`, {method:'POST'});
    toast(`<b>${name}</b> stopped`, 'success', 2000);
    await loadSpec();
  } catch(e) {
    toast(`Failed to stop ${name}: ${e.message}`, 'error');
    btn.disabled = false; btn.textContent = '■ STOP';
  }
}

async function specStartAll() {
  if (!confirm('Start all 10 spec servers? This will take a few minutes and use significant VRAM.')) return;
  try {
    await api('/api/spec/start_all', {method:'POST'});
    toast('Starting all spec servers in background…', 'info', 5000);
    // Refresh status every 4s while starting
    let n = 0;
    const tick = setInterval(async () => {
      await loadSpec();
      if (++n >= 30) clearInterval(tick);
    }, 4000);
  } catch(e) { toast(`Bulk start failed: ${e.message}`, 'error'); }
}

async function specStopAll() {
  if (!confirm('Stop ALL spec servers?')) return;
  try {
    await api('/api/spec/stop_all', {method:'POST'});
    toast('All spec servers stopped', 'success');
    await loadSpec();
  } catch(e) { toast(`Stop all failed: ${e.message}`, 'error'); }
}

async function specQuickTry(name) {
  const sel = document.getElementById('spec-model-select');
  if (sel) sel.value = name;
  goTab('spec');
  setTimeout(() => specStream(), 300);
}

async function specGenerate() {
  const model  = document.getElementById('spec-model-select').value;
  const prompt = document.getElementById('spec-prompt').value.trim();
  const res    = document.getElementById('spec-result');
  if (!model || !prompt) { toast('Select a model and enter a prompt', 'warn'); return; }
  res.innerHTML = '<div class="status running" style="display:block;text-align:center;">Running…</div>';
  try {
    const data = await api('/api/spec/generate', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model, prompt, max_tokens: 1024})
    });
    const specRate = data.spec_accept_rate ? `${(data.spec_accept_rate * 100).toFixed(1)}%` : '—';
    res.innerHTML = `
      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; font-family:'Inter',sans-serif;">
        <span class="badge badge-green">⚡ ${data.tps.toFixed(1)} t/s</span>
        <span class="badge badge-blue">⏱ ${data.latency_s.toFixed(2)}s</span>
        <span class="badge badge-blue">🎯 ${escText(specRate)}</span>
        <span class="badge badge-blue">↓ ${data.tokens_in} → ↑ ${data.tokens_out}</span>
      </div>${escText(data.text || '')}`;
  } catch(e) {
    res.innerHTML = `<div style="color:var(--accent-red); font-family:'Inter',sans-serif;">Error: ${e.message}</div>`;
    toast(`Bench failed: ${e.message}`, 'error');
  }
}

// ── LIVE STREAMING via SSE ─────────────────────────────────────
let _streamAbortCtl = null;
async function specStream() {
  if (_streamAbortCtl) { _streamAbortCtl.abort(); _streamAbortCtl = null; }
  const model  = document.getElementById('spec-model-select').value;
  const prompt = document.getElementById('spec-prompt').value.trim();
  const res    = document.getElementById('spec-result');
  const stats  = document.getElementById('spec-live-stats');
  if (!model || !prompt) { toast('Select a model and enter a prompt', 'warn'); return; }
  res.textContent = '';
  stats.style.display = 'block';
  ['live-tps','live-elapsed','live-ttft','live-tokens'].forEach(id => document.getElementById(id).textContent = '0');
  document.getElementById('live-gauge-fill').style.width = '0%';

  _streamAbortCtl = new AbortController();
  try {
    const r = await fetch('/api/spec/stream', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({model, prompt, max_tokens: 1024}),
      signal: _streamAbortCtl.signal,
    });
    if (!r.ok) throw new Error(await r.text());
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let maxTps = 1;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      const events = buf.split('\n\n'); buf = events.pop();
      for (const ev of events) {
        if (!ev.startsWith('data:')) continue;
        const j = ev.slice(5).trim();
        if (!j) continue;
        try {
          const d = JSON.parse(j);
          if (d.type === 'token') {
            res.textContent += d.piece;
            res.scrollTop = res.scrollHeight;
            document.getElementById('live-tps').textContent = d.tps;
            document.getElementById('live-elapsed').textContent = d.elapsed;
            document.getElementById('live-ttft').textContent = d.ttft;
            document.getElementById('live-tokens').textContent = d.tokens_out;
            if (d.tps > maxTps) maxTps = d.tps;
            const pct = Math.min(100, (d.tps / Math.max(maxTps, 20)) * 100);
            document.getElementById('live-gauge-fill').style.width = pct + '%';
          } else if (d.type === 'done') {
            document.getElementById('live-tps').textContent = d.tps;
            toast(`Stream done — <b>${d.tps} t/s</b>, ${d.tokens_out} tokens`, 'success');
          } else if (d.type === 'error') {
            toast(`Stream error: ${d.error}`, 'error');
          }
        } catch(e) {}
      }
    }
  } catch(e) {
    if (e.name !== 'AbortError') toast(`Stream: ${e.message}`, 'error');
  } finally {
    _streamAbortCtl = null;
  }
}

// ── Spec vs Base ────────────────────────────────────────────────
async function specVsBase() {
  const model  = document.getElementById('vs-model-select').value;
  const prompt = document.getElementById('vs-prompt').value.trim();
  const res    = document.getElementById('vs-result');
  if (!model || !prompt) { toast('Select model + prompt', 'warn'); return; }
  res.innerHTML = '<div class="status running" style="display:block;text-align:center;">Running both backends…</div>';
  try {
    const d = await api('/api/spec/vs_base', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model, prompt, max_tokens: 512})
    });
    const speedupColor = d.speedup >= 1.5 ? 'var(--accent-green)' : d.speedup >= 1 ? 'var(--accent-blue)' : 'var(--accent-red)';
    const maxTps = Math.max(d.spec.tps, d.base.tps, 1);
    res.innerHTML = `
      <div style="display:flex; gap:32px; align-items:center; padding:24px; background:rgba(1,4,9,0.5); border-radius:var(--radius-inner); border:1px solid var(--border-color); flex-wrap:wrap;">
        <div style="text-align:center; min-width:120px;">
          <div style="font-size:48px; font-weight:800; color:${speedupColor}; line-height:1; letter-spacing:-1px;">${d.speedup.toFixed(2)}×</div>
          <div style="font-size:11px; color:var(--text-muted); font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-top:6px;">Speedup</div>
        </div>
        <div style="flex:1; min-width:260px;">
          <div style="margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:6px;">
              <span style="font-weight:600;">🚀 ${d.spec.model}</span>
              <span><b style="color:var(--accent-green);">${d.spec.tps.toFixed(1)}</b> t/s · ${d.spec.latency_s.toFixed(2)}s</span>
            </div>
            <div class="tps-gauge"><div class="fill" style="width:${(d.spec.tps/maxTps)*100}%; background:linear-gradient(90deg, var(--accent-green), var(--accent-blue));"></div></div>
          </div>
          <div>
            <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:6px;">
              <span style="font-weight:600;">⚙️ ${d.base.model} (base)</span>
              <span><b style="color:var(--text-muted);">${d.base.tps.toFixed(1)}</b> t/s · ${d.base.latency_s.toFixed(2)}s</span>
            </div>
            <div class="tps-gauge"><div class="fill" style="width:${(d.base.tps/maxTps)*100}%; background:linear-gradient(90deg, var(--text-muted), rgba(139,148,158,0.5));"></div></div>
          </div>
        </div>
      </div>`;
    if (d.speedup >= 2.0) { fireConfetti(40); toast(`<b>${d.speedup.toFixed(2)}×</b> speedup achieved! 🎉`, 'success', 4000); }
  } catch(e) {
    res.innerHTML = `<div style="color:var(--accent-red)">Error: ${e.message}</div>`;
    toast(`Compare failed: ${e.message}`, 'error');
  }
}

// ── Bench all running servers ───────────────────────────────────
async function specBenchAll() {
  const res = document.getElementById('bench-all-result');
  res.innerHTML = '<div class="status running" style="display:block; text-align:center;">Benchmarking all running servers in parallel…</div>';
  try {
    const d = await api('/api/spec/bench_all', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt: 'Write quicksort in Python.', max_tokens: 384})
    });
    if (!d.results.length) { res.innerHTML = `<div style="color:var(--text-muted);">${d.message || 'No running servers.'}</div>`; return; }
    const maxTps = Math.max(...d.results.map(r => r.tps || 0), 1);
    res.innerHTML = `<table>
      <thead><tr><th>Rank</th><th>Model</th><th>TPS</th><th>Latency</th><th>Tokens</th><th>Bar</th></tr></thead>
      <tbody>${d.results.map((r, i) => {
        const tpsBar = (r.tps / maxTps) * 100;
        const okIcon = r.ok ? '✓' : '✕';
        const okColor = r.ok ? 'var(--accent-green)' : 'var(--accent-red)';
        return `<tr>
          <td><b style="color:${i === 0 ? 'var(--accent-green)' : 'var(--text-main)'};">#${i+1}</b></td>
          <td><span style="color:${okColor}; font-weight:800;">${okIcon}</span> <b>${r.name}</b></td>
          <td><b style="color:var(--accent-blue);">${r.tps.toFixed(1)}</b> t/s</td>
          <td>${r.latency_s ? r.latency_s.toFixed(2) + 's' : '—'}</td>
          <td>${r.tokens_out || 0}</td>
          <td><div class="tps-gauge" style="margin-top:0; width:120px;"><div class="fill" style="width:${tpsBar}%;"></div></div></td>
        </tr>`;
      }).join('')}</tbody>
    </table>`;
    toast(`Benched <b>${d.results.length}</b> servers — fastest: <b>${d.results[0].name}</b> @ ${d.results[0].tps.toFixed(1)} t/s`, 'success', 5000);
  } catch(e) {
    res.innerHTML = `<div style="color:var(--accent-red)">Error: ${e.message}</div>`;
    toast(`Bench all: ${e.message}`, 'error');
  }
}
