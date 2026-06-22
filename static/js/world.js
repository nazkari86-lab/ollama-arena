// World tab: thin iframe shell pointing at the Godot L3 world renderer's
// Web export, parameterized by the simulation run id.
let _worldPendingRunId = null;

function initWorldTab() {
  if (_worldPendingRunId) {
    showWorldRun(_worldPendingRunId);
    _worldPendingRunId = null;
  }
}

function showWorldRun(runId) {
  const emptyState = document.getElementById('world-empty-state');
  const wrap = document.getElementById('world-iframe-wrap');
  const iframe = document.getElementById('world-iframe');
  if (!emptyState || !wrap || !iframe) {
    _worldPendingRunId = runId;
    return;
  }
  iframe.src = `/static/godot/index.html?run_id=${encodeURIComponent(runId)}`;
  emptyState.style.display = 'none';
  wrap.style.display = 'block';
}

function viewSimRunInWorld(runId) {
  document.querySelector('.tab[data-tab="world"]').click();
  showWorldRun(runId);
}
