// ═══════════════════════════════════════════════════════════════
// EVALS TABLE — sortable, searchable match-history table with
// win/loss color coding and click-to-expand row detail.
// Backed entirely by /api/history, /api/history/search,
// /api/export_match/{id} -- no new backend route needed.
// ═══════════════════════════════════════════════════════════════
const EVALS_TABLE_COLUMNS = [
  { key: 'id',       label: 'ID',          sortable: true,  numeric: true },
  { key: 'matchup',  label: 'Contenders',  sortable: false, numeric: false },
  { key: 'category', label: 'Category',    sortable: true,  numeric: false },
  { key: 'margin',   label: 'Score',       sortable: true,  numeric: true },
  { key: 'ts',       label: 'Date',        sortable: true,  numeric: true },
];

function _evalsTableState(containerId) {
  if (!window.__evalsTableState) window.__evalsTableState = {};
  if (!window.__evalsTableState[containerId]) {
    window.__evalsTableState[containerId] = { sortKey: 'ts', sortDir: -1, expanded: null, rows: [] };
  }
  return window.__evalsTableState[containerId];
}

function _evalsRowValue(row, key) {
  if (key === 'margin') return row.score_a - row.score_b;
  return row[key];
}

function renderEvalsTable(containerId, rows) {
  const state = _evalsTableState(containerId);
  state.rows = rows;
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!rows.length) {
    el.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center">No matches recorded yet.</div>';
    return;
  }

  const sorted = [...rows].sort((a, b) => {
    const av = _evalsRowValue(a, state.sortKey);
    const bv = _evalsRowValue(b, state.sortKey);
    if (av < bv) return -1 * state.sortDir;
    if (av > bv) return 1 * state.sortDir;
    return 0;
  });

  const headHtml = EVALS_TABLE_COLUMNS.map(c => {
    const active = state.sortKey === c.key;
    const arrow = active ? (state.sortDir === 1 ? ' ▲' : ' ▼') : '';
    return `<th ${c.sortable ? `class="evals-th-sortable" data-sort-key="${c.key}"` : ''}>${c.label}${arrow}</th>`;
  }).join('') + '<th>Action</th>';

  const bodyHtml = sorted.map(m => {
    const date = new Date(m.ts * 1000).toLocaleString();
    const margin = m.score_a - m.score_b;
    const marginColor = margin > 0 ? 'var(--accent-green)' : (margin < 0 ? 'var(--accent-red)' : 'var(--text-muted)');
    const expanded = state.expanded === m.id;
    return `
      <tr class="evals-row" data-match-id="${m.id}">
        <td style="color:var(--accent-blue); font-weight:700">#${m.id}</td>
        <td>
          <strong style="${margin > 0 ? 'color:var(--accent-green)' : ''}">${escText(m.model_a)}</strong>
          <span style="color:var(--text-muted)">vs</span>
          <strong style="${margin < 0 ? 'color:var(--accent-green)' : ''}">${escText(m.model_b)}</strong>
        </td>
        <td><span class="badge badge-blue">${escText(m.category)}</span></td>
        <td style="color:${marginColor}; font-weight:800">${m.score_a} - ${m.score_b}</td>
        <td style="font-size:11px; color:var(--text-muted)">${date}</td>
        <td><button class="btn export-match-btn" data-match-id="${m.id}" style="width:auto; padding:4px 12px; font-size:10px;">Export</button></td>
      </tr>
      ${expanded ? `
      <tr class="evals-row-detail">
        <td colspan="6">
          <div class="evals-detail-panel">
            <div><b>Match #${m.id}</b> — ${escText(m.category)}</div>
            <div>${escText(m.model_a)}: <b>${m.score_a}</b> &nbsp;|&nbsp; ${escText(m.model_b)}: <b>${m.score_b}</b></div>
            <div style="color:var(--text-muted); font-size:11px">${date}</div>
          </div>
        </td>
      </tr>` : ''}
    `;
  }).join('');

  el.innerHTML = `<table class="evals-table"><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;

  el.querySelectorAll('.evals-th-sortable').forEach(th => {
    th.onclick = () => {
      const key = th.dataset.sortKey;
      if (state.sortKey === key) state.sortDir *= -1;
      else { state.sortKey = key; state.sortDir = 1; }
      renderEvalsTable(containerId, state.rows);
    };
  });
  el.querySelectorAll('.evals-row').forEach(tr => {
    tr.onclick = (e) => {
      if (e.target.closest('.export-match-btn')) return;
      const id = Number(tr.dataset.matchId);
      state.expanded = state.expanded === id ? null : id;
      renderEvalsTable(containerId, state.rows);
    };
  });
}
