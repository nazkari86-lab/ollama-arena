// P2P tab: read-only node status / global leaderboard / reputation,
// backed by /api/p2p/* (ollama_arena/web_routes/p2p_routes.py).
let _p2pTabWired = false;

function initP2PTab() {
  if (!_p2pTabWired) {
    _p2pTabWired = true;
    document.getElementById('p2p-refresh-btn')?.addEventListener('click', loadP2PTab);
  }
  loadP2PTab();
}

async function loadP2PTab() {
  await Promise.all([loadP2PStatus(), loadP2PLeaderboard(), loadP2PReputation()]);
}

async function loadP2PStatus() {
  try {
    const s = await api('/api/p2p/status');
    document.getElementById('p2p-stat-peers').textContent = s.peer_count;
    document.getElementById('p2p-status-panel').innerHTML = `
      <div class="sim-overview-stats" style="margin:0;">
        <div><strong>${escText(s.node_id.slice(0, 12))}…</strong><span>Node ID</span></div>
        <div><strong>${s.is_running ? 'Yes' : 'No'}</strong><span>Networking active</span></div>
        <div><strong>${s.messages_sent}</strong><span>Messages sent</span></div>
        <div><strong>${s.messages_received}</strong><span>Messages received</span></div>
        <div><strong>${s.tasks_completed}</strong><span>Tasks completed</span></div>
        <div><strong>${s.tasks_failed}</strong><span>Tasks failed</span></div>
      </div>`;
  } catch (e) {
    toast(`Failed to load P2P status: ${escText(e.message)}`, 'error');
  }
}

async function loadP2PLeaderboard() {
  try {
    const r = await api('/api/p2p/leaderboard');
    document.getElementById('p2p-stat-entries').textContent = r.stats.total_entries;
    const el = document.getElementById('p2p-leaderboard-table');
    if (!r.entries.length) {
      el.innerHTML = '<div class="sim-field-help">No verified leaderboard entries yet.</div>';
      return;
    }
    const rows = r.entries.map(e => `
      <tr>
        <td><code>${escText(e.model_name)}</code></td>
        <td>${escText(e.category)}</td>
        <td>${Number(e.score).toFixed(3)}</td>
      </tr>`).join('');
    el.innerHTML = `<div class="sim-table-wrap"><table><thead><tr><th>Model</th><th>Category</th><th>Score</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  } catch (e) {
    toast(`Failed to load P2P leaderboard: ${escText(e.message)}`, 'error');
  }
}

async function loadP2PReputation() {
  try {
    const r = await api('/api/p2p/reputation');
    const el = document.getElementById('p2p-reputation-table');
    if (!r.nodes.length) {
      el.innerHTML = '<div class="sim-field-help">No node reputation data yet.</div>';
      return;
    }
    const rows = r.nodes.map(n => `
      <tr>
        <td><code>${escText(n.node_id)}</code></td>
        <td>${Number(n.trust_score).toFixed(3)}</td>
      </tr>`).join('');
    el.innerHTML = `<div class="sim-table-wrap"><table><thead><tr><th>Node ID</th><th>Trust score</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  } catch (e) {
    toast(`Failed to load node reputation: ${escText(e.message)}`, 'error');
  }
}
