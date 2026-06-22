// ═══════════════════════════════════════════════════════════════
// TRACE TIMELINE — Langfuse-inspired waterfall of per-tool-call
// latency within an agent trace. Pure rendering on top of the
// tool_results[].latency_s data agent_loop.py already records;
// no new instrumentation.
// ═══════════════════════════════════════════════════════════════
function buildTraceTimelineSegments(trace) {
  const segments = [];
  let offset = 0;
  (trace || []).forEach((step, stepIdx) => {
    (step.tool_results || []).forEach(tr => {
      const dur = Number(tr.latency_s) || 0;
      segments.push({ step: step.step || stepIdx + 1, name: tr.name || 'tool', offset, duration: dur });
      offset += dur;
    });
  });
  return { segments, total: offset };
}

function renderTraceTimeline(trace) {
  const { segments, total } = buildTraceTimelineSegments(trace);
  if (!segments.length || total <= 0) return '';
  const rows = segments.map(seg => {
    const leftPct = (seg.offset / total * 100).toFixed(2);
    const widthPct = Math.max(1, seg.duration / total * 100).toFixed(2);
    return `
      <div class="timeline-row">
        <div class="timeline-row-label">Step ${seg.step} · ${escText(seg.name)}</div>
        <div class="timeline-track">
          <div class="timeline-bar" style="left:${leftPct}%; width:${widthPct}%" data-tip="${seg.duration.toFixed(3)}s"></div>
        </div>
        <div class="timeline-row-dur">${seg.duration.toFixed(3)}s</div>
      </div>`;
  }).join('');
  return `<div class="trace-timeline">
    <div class="timeline-header">⏱ Tool-call waterfall <span class="timeline-total">${total.toFixed(3)}s total</span></div>
    ${rows}
  </div>`;
}
