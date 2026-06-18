/**
 * Render an agent trace (list of steps) into a DOM element.
 * @param {Array} trace  - agent_trace array from GenResult
 * @param {HTMLElement} container
 */
function renderAgentTrace(trace, container) {
  if (!trace || !trace.length) {
    container.innerHTML = '<span style="color:#888; font-size:0.8rem;">No tool calls</span>';
    return;
  }
  container.innerHTML = '';
  trace.forEach((step, i) => {
    const el = document.createElement('details');
    el.className = 'agent-trace-step animate__animated animate__fadeInUp';
    el.style.cssText = 'margin: 4px 0; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; animation-delay:' + (i * 80) + 'ms;';

    const summary = document.createElement('summary');
    summary.style.cssText = 'padding: 6px 10px; cursor: pointer; background: #161b22; font-size: 0.8rem; display: flex; align-items: center; gap: 8px;';

    const hasError = step.error;
    const toolCalls = step.tool_calls || [];
    const toolNames = toolCalls.map(tc => tc?.function?.name || '?').join(', ');
    const gateDenied = (step.tool_results || []).some(r =>
      String(r.result || '').toLowerCase().includes('denied'));
    const icon = hasError ? '❌' : gateDenied ? '🛡️' : toolNames ? '🔧' : '💬';

    summary.innerHTML = `
      <span>${icon} Step ${step.step}</span>
      ${toolNames ? `<span style="color:#58a6ff; font-family: monospace;">${toolNames}</span>` : ''}
      ${gateDenied ? `<span style="color:#f59e0b;">gate denied</span>` : ''}
      ${hasError ? `<span style="color:#f85149;">${step.error}</span>` : ''}
    `;
    el.appendChild(summary);

    const body = document.createElement('div');
    body.style.cssText = 'padding: 8px 10px; background: #0d1117; font-size: 0.78rem; font-family: monospace; white-space: pre-wrap; overflow: auto; max-height: 300px;';

    let bodyContent = '';
    if (step.content) {
      bodyContent += `<div style="color:#e6edf3; margin-bottom:6px;">${escapeHtml(step.content.slice(0, 500))}</div>`;
    }
    (step.tool_results || []).forEach(r => {
      const lat = r.latency_s != null ? ` <span style="color:#8b949e;">(${r.latency_s}s)</span>` : '';
      bodyContent += `<div style="color:#3fb950;">→ ${r.name}(${JSON.stringify(r.arguments || {}).slice(0, 100)})${lat}</div>`;
      bodyContent += `<div style="color:#888; margin-left:12px;">${escapeHtml(String(r.result || '').slice(0, 300))}</div>`;
    });
    if (hasError) {
      bodyContent += `<div style="color:#f85149;">Error: ${escapeHtml(step.error)}</div>`;
    }
    body.innerHTML = bodyContent;
    el.appendChild(body);
    container.appendChild(el);
    if (window.anime) {
      anime({ targets: el, opacity: [0, 1], translateY: [8, 0], duration: 400, delay: i * 100, easing: 'easeOutCubic' });
    }
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Load and display agent trace for a match in two panels (A and B).
 */
async function loadMatchTrace(matchId, containerA, containerB) {
  try {
    const data = await fetch(`/api/agent_trace/${matchId}`).then(r => r.json());
    const firstTask = data.tasks[0];
    if (!firstTask) return;
    renderAgentTrace(firstTask.trace_a, containerA);
    renderAgentTrace(firstTask.trace_b, containerB);
  } catch (e) {
    console.warn('Agent trace load failed:', e);
  }
}
