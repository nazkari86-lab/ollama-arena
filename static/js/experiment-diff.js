// ═══════════════════════════════════════════════════════════════
// EXPERIMENT DIFF — Phoenix-inspired run comparison. Renders the
// existing /api/sim/compare report as a metric × run grid with the
// best run per metric highlighted. No new backend route needed.
// ═══════════════════════════════════════════════════════════════
function renderExperimentDiff(containerId, report) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!report.run_ids.length) {
    el.innerHTML = '<div class="sim-field-help">No matching runs found.</div>';
    return;
  }
  if (!report.metric_names.length) {
    el.innerHTML = '<div class="sim-field-help">No metrics recorded for the selected run(s) yet.</div>';
    return;
  }
  const headCells = report.run_ids.map(id => `<th title="${escText(id)}"><code>${escText(id.slice(0, 10))}…</code></th>`).join('');
  const bodyRows = report.metric_names.map(name => {
    const best = report.best_run_by_metric[name];
    const cells = report.run_ids.map(id => {
      const v = report.metrics_by_run[id]?.[name];
      const isBest = id === best && v != null;
      return `<td class="${isBest ? 'diff-best' : ''}">${v != null ? Number(v).toFixed(3) : '—'}</td>`;
    }).join('');
    return `<tr><td><b>${escText(name)}</b></td>${cells}</tr>`;
  }).join('');
  el.innerHTML = `<div style="overflow-x:auto;"><table class="evals-table"><thead><tr><th>Metric</th>${headCells}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
}

async function compareSelectedSimRuns() {
  const ids = [...document.querySelectorAll('.sim-diff-checkbox:checked')].map(cb => cb.value);
  if (!ids.length) { toast('Select at least one run to compare', 'warn'); return; }
  try {
    const report = await api(`/api/sim/compare?run_ids=${ids.map(encodeURIComponent).join(',')}`);
    renderExperimentDiff('sim-diff-panel', report);
  } catch (e) {
    toast(`Compare failed: ${escText(e.message)}`, 'error');
  }
}
