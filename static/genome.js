let simulation, svg, g;
let selectedNodeId = null;

async function loadTree(filter) {
  const url = filter
    ? `/api/genome/tree?model=${encodeURIComponent(filter)}`
    : '/api/genome/tree';
  const data = await fetch(url).then(r => r.json());
  renderGraph(data);
}

async function showModelDetail(node) {
  const name = node.id || node.name;
  const el = document.getElementById('model-detail');
  if (!el) return;
  el.style.display = 'block';
  el.innerHTML = '<em>Loading…</em>';
  try {
    const data = await fetch(`/api/genome/model/${encodeURIComponent(name)}`).then(r => r.json());
    const c = data.canonical;
    const local = data.local;
    el.innerHTML = `
      <h3>${c?.name || node.name || name}</h3>
      ${c ? `<p>Family: ${c.family || '?'} | Org: ${c.org || '?'}</p>
             <p>Params: ${c.architecture?.params_b || '?'}B</p>` : ''}
      ${local ? `<p>Local: ${local.confidence} | ${local.quant || '?'} | ${local.size_gb || '?'} GB</p>` : ''}
      ${c?.source_url ? `<p><a href="${c.source_url}" target="_blank">Source</a></p>` : ''}
    `;
  } catch (e) {
    el.innerHTML = `<p>Could not load model details.</p>`;
  }
}

function renderGraph(data) {
  const el = document.getElementById('graph');
  el.innerHTML = '';
  const W = el.clientWidth || window.innerWidth;
  const H = el.clientHeight || window.innerHeight - 140;

  svg = d3.select('#graph').append('svg')
    .attr('width', W).attr('height', H);

  svg.append('defs').selectAll('marker')
    .data(['fine_tuned_from', 'distilled_from', 'merged_from', 'trained_from'])
    .join('marker')
      .attr('id', d => `arrow-${d}`)
      .attr('viewBox', '0 -5 10 10').attr('refX', 22).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
    .append('path').attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', d => ({
        fine_tuned_from: '#58a6ff', distilled_from: '#3fb950',
        merged_from: '#f85149', trained_from: '#e3b341'
      })[d] || '#888');

  g = svg.append('g');

  svg.call(d3.zoom().scaleExtent([0.1, 4])
    .on('zoom', e => g.attr('transform', e.transform)));

  const link = g.append('g').selectAll('line')
    .data(data.links).join('line')
      .attr('stroke', d => d.color || '#888')
      .attr('stroke-width', 1.5).attr('stroke-opacity', 0.7)
      .attr('marker-end', d => `url(#arrow-${d.relation})`);

  const nodeGroup = g.append('g').selectAll('g')
    .data(data.nodes).join('g').attr('class', 'node')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  const familyColors = {
    'Llama 3': '#58a6ff', 'Llama 3.2': '#79c0ff',
    'Qwen 2.5': '#3fb950', 'Qwen 3': '#56d364',
    'Mistral': '#e3b341', 'Mixtral': '#d29922',
    'Gemma 2': '#bc8cff', 'Gemma 3': '#a371f7',
    'Phi': '#ff7b72', 'DeepSeek R1': '#ffa657',
    'Code Llama': '#79c0ff', 'Hermes': '#58a6ff',
  };

  nodeGroup.append('circle')
    .attr('r', d => Math.max(8, Math.min(24, ((d.params_b || 1) * 0.8))))
    .attr('fill', d => d.type === 'local' ? '#f85149' : '#21262d')
    .attr('stroke', d => familyColors[d.family] || '#888')
    .attr('stroke-width', d => (d.id === selectedNodeId ? 4 : 2));

  nodeGroup.append('text')
    .attr('dy', d => -Math.max(8, Math.min(24, ((d.params_b || 1) * 0.8))) - 4)
    .attr('text-anchor', 'middle')
    .attr('font-size', '11px').attr('fill', '#e6edf3')
    .text(d => d.name.length > 22 ? d.name.slice(0, 20) + '…' : d.name);

  const tooltip = document.getElementById('tooltip');
  nodeGroup.on('mouseover', (e, d) => {
    const pb = d.params_b || 0;
    tooltip.innerHTML = `
      <strong>${d.name}</strong><br>
      Family: ${d.family || '?'} | Org: ${d.org || '?'}<br>
      ${pb ? `Params: ${pb}B<br>` : ''}
      ${d.type === 'local' ? `<span style="color:#f85149">📦 Local | ${d.confidence || '?'}</span>` : ''}
      <br><em>Click for details</em>
    `;
    tooltip.style.opacity = '1';
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
  }).on('mousemove', e => {
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
  }).on('mouseout', () => { tooltip.style.opacity = '0'; })
    .on('click', (e, d) => {
      selectedNodeId = d.id;
      nodeGroup.selectAll('circle')
        .attr('stroke-width', n => (n.id === selectedNodeId ? 4 : 2));
      showModelDetail(d);
    });

  if (simulation) simulation.stop();
  simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.links).id(d => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide(30))
    .on('tick', () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

async function pollScanProgress() {
  const status = document.getElementById('status');
  for (let i = 0; i < 120; i++) {
    const p = await fetch('/api/genome/scan/progress').then(r => r.json());
    if (p.running) {
      status.textContent = `Scanning ${p.current}/${p.total}: ${p.model || '…'}`;
    }
    if (p.done) {
      status.textContent = `Done — ${p.total} models`;
      loadTree(null);
      return;
    }
    await new Promise(r => setTimeout(r, 500));
  }
}

async function scanModels() {
  document.getElementById('status').textContent = 'Scanning...';
  await fetch('/api/genome/scan', {method: 'POST'});
  pollScanProgress();
}

// ═══════════════════════════════════════════════════════════════
// GENOME TAB — lazy init (dashboard tab dispatch calls this every
// click; the d3 graph can't size itself correctly while its
// tab-content is display:none, so loadTree() must only run once the
// tab is actually visible, not on page load).
// ═══════════════════════════════════════════════════════════════
let _genomeTabWired = false;
function initGenomeTab() {
  if (!_genomeTabWired) {
    _genomeTabWired = true;
    document.getElementById('genome-scan-btn')?.addEventListener('click', scanModels);
    document.getElementById('genome-show-all-btn')?.addEventListener('click', () => loadTree(null));
    document.getElementById('hw-scan-btn')?.addEventListener('click', scanHardware);
    document.getElementById('search')?.addEventListener('input', e => {
      const q = e.target.value.trim();
      if (q.length >= 2) loadTree(q);
      else if (q.length === 0) loadTree(null);
    });
  }
  loadTree(null);
}

// ═══════════════════════════════════════════════════════════════
// HARDWARE FIT SCANNER — scores every installed (non-embedding) model
// by how well it fits in usable RAM (0-100%) plus an estimated
// tokens/sec, via GET /api/hardware/scan (ollama_arena/hardware_fit.py).
// ═══════════════════════════════════════════════════════════════
function _hasOption(sel, value) {
  return !!sel && [...sel.options].some(o => o.value === value);
}

function applyBestTwoModels(bestTwo, { silent = false } = {}) {
  if (!bestTwo || bestTwo.length < 2) return false;
  const a = document.getElementById('model-a');
  const b = document.getElementById('model-b');
  if (!_hasOption(a, bestTwo[0]) || !_hasOption(b, bestTwo[1])) return false;
  a.value = bestTwo[0];
  b.value = bestTwo[1];
  if (typeof schedulePreviewStrategy === 'function') schedulePreviewStrategy();
  if (!silent) {
    toast(`Auto-selected best hardware fit: <b>${escText(bestTwo[0])}</b> vs <b>${escText(bestTwo[1])}</b>`, 'success', 4000);
  }
  return true;
}

async function scanHardware() {
  const btn = document.getElementById('hw-scan-btn');
  const summaryEl = document.getElementById('hw-summary');
  const tableEl = document.getElementById('hw-fit-table');
  btn.disabled = true; btn.textContent = 'Scanning…';
  tableEl.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Scanning hardware and scoring models…</div>';
  try {
    const data = await api('/api/hardware/scan');
    const hw = data.hardware;
    summaryEl.style.display = 'flex';
    summaryEl.innerHTML = `
      <span class="badge badge-blue">🖥️ ${escText(hw.platform)} (${escText(hw.machine)})</span>
      <span class="badge badge-blue">${hw.cpu_count} CPU cores</span>
      <span class="badge badge-green">${hw.usable_ram_gb} GB usable / ${hw.total_ram_gb} GB total RAM</span>
    `;
    if (!data.models.length) {
      tableEl.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">No local generative models found.</div>';
      return;
    }
    const rows = data.models.map((m, i) => {
      const barColor = m.fit_pct >= 75 ? 'var(--accent-green)' : m.fit_pct >= 40 ? '#f59e0b' : 'var(--accent-red)';
      const tps = m.tps != null ? `${m.tps} t/s${m.tps_kind === 'estimated' ? ' (est.)' : ''}` : 'unknown';
      const pick = i < 2 ? '<span class="badge badge-green" style="margin-left:8px; font-size:10px;">★ Auto-pick</span>' : '';
      return `<tr>
        <td><strong>${escText(m.model)}</strong>${pick}</td>
        <td>${m.effective_size_gb} GB</td>
        <td style="min-width:140px;">
          <div class="tps-gauge" style="margin-top:0;"><div class="fill" style="width:${m.fit_pct}%; background:${barColor};"></div></div>
          <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${m.fit_pct}%</div>
        </td>
        <td>${escText(tps)}</td>
      </tr>`;
    }).join('');
    tableEl.innerHTML = `<table><thead><tr><th>Model</th><th>Effective Size</th><th>Fit Score</th><th>Est. Speed</th></tr></thead><tbody>${rows}</tbody></table>`;
    applyBestTwoModels(data.best_two);
  } catch(e) {
    tableEl.innerHTML = `<div style="color:var(--accent-red); padding:20px;">Error: ${escText(e.message)}</div>`;
    toast(`Hardware scan failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Scan My Hardware';
  }
}
