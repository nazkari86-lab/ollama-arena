function connectWS() {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
  socket = new WebSocket(wsUrl);
  socket.onmessage = (e) => {
    const d = JSON.parse(e.data);
    // Sim events are keyed by run_id, not job_id -- multiple sim runs can
    // be in flight at once (an active-runs table, not a single current
    // job), so they bypass the single-job currentJobId gate below and are
    // routed unconditionally to sim.js's own dispatcher.
    if (typeof d.type === 'string' && d.type.startsWith('sim_') && typeof handleSimWSEvent === 'function') {
      handleSimWSEvent(d);
      return;
    }
    if (d.job_id === currentJobId) handleWSEvent(d);
  };
  socket.onclose = () => setTimeout(connectWS, 2000);
}

// ── Blind Arena: replace model names with X / Y until match completes ──
let _blindModeActive = false;
let _blindMapping = { a: '', b: '' };   // remembered real names for reveal
function _blindize(text) {
  if (!_blindModeActive || !text) return text;
  let out = String(text);
  if (_blindMapping.a) out = out.split(_blindMapping.a).join('Model X');
  if (_blindMapping.b) out = out.split(_blindMapping.b).join('Model Y');
  return out;
}

// ── Synthetic Parallel Replay — Pipeline UI illusion ───────────────────
// In PIPELINE mode, the backend really runs Model A on all tasks first,
// then Model B on all tasks. WS events arrive sequentially. We buffer A's
// progress events and replay them PARALLEL with B's events on the UI, so
// the user perceives a normal head-to-head battle.
const _replay = {
  active: false,
  phaseA: [],   // timeline of A's progress events
  phaseB: [],   // timeline of B's progress events
  phase: 0,     // 1 = recording A, 2 = recording B + replaying A in parallel
};

function handleWSEvent(d) {
  const log = document.getElementById('match-log');
  const status = document.getElementById('match-status');

  // ── Strategy events (PIPELINE, HOT_SWAP, etc) ───────────────────────
  if (d.type === 'strategy_event') {
    if (d.type === 'strategy_event' && d.strategy) {
      // Initial strategy announcement
      const v = (_STRATEGY_VIS && _STRATEGY_VIS[d.strategy]) || null;
      log.innerHTML += `<div style="border-left:3px solid ${v?v.color:'var(--accent-blue)'};
                                    padding:8px 12px; margin-bottom:8px;
                                    background:${v?v.color+'14':'rgba(88,166,255,0.06)'};
                                    color:var(--text-main); border-radius:0 6px 6px 0;">
        <b>${escText(v ? v.icon+' '+v.label : d.strategy)}</b><br>
        <small style="color:var(--text-muted);">${escText(d.reason || '')}</small>
      </div>`;
      log.scrollTop = log.scrollHeight;
      if (d.strategy === 'PIPELINE') {
        _replay.active = true; _replay.phaseA = []; _replay.phaseB = []; _replay.phase = 0;
        toast(`🔁 <b>PIPELINE</b> mode — sequencing under the hood, UI will replay as parallel.`, 'info', 5000);
      } else if (d.strategy === 'HOT_SWAP') {
        toast(`↔️ <b>HOT SWAP</b> mode — models will alternate per task.`, 'info', 4000);
      }
    } else if (d.type === 'strategy_event' && d.phase) {
      // phase_start / phase_progress
      const which = d.phase === 1 ? 'A' : 'B';
      if (d.type === 'strategy_event' && d.model) {
        // phase_start carries .model and .total — mask in blind mode
        const shown = _blindModeActive ? `Model ${which}` : d.model;
        log.innerHTML += `<div style="color:var(--accent-blue); margin:8px 0; padding-left:8px;">
          ▶ Phase ${d.phase}/2 — running <b>${escText(shown)}</b> on ${d.total} tasks…
        </div>`;
        if (d.phase === 1) _replay.phase = 1;
        else if (d.phase === 2) _replay.phase = 2;
      } else {
        // phase_progress
        log.innerHTML += `<div style="color:var(--text-muted); padding-left:24px; font-size:12px;">
          ${escText(which)}: ${d.i}/${d.total} — ${escText(d.task_id)}
        </div>`;
      }
      log.scrollTop = log.scrollHeight;
    }
    return;
  }

  if (d.type === 'task_done') {
    const cls = d.outcome === 'a_wins' ? 'log-win' : d.outcome === 'b_wins' ? 'log-loss' : 'log-win'; // Draw visually similar to win locally for now
    log.innerHTML += `<div class="${cls}" style="animation:subtleEnter 0.3s ease-out"><b>[${escText(d.task_id)}]</b> Score: ${d.score_a.toFixed(2)} vs ${d.score_b.toFixed(2)}</div>`;
    log.scrollTop = log.scrollHeight;
    if (window.arenaVisualizer) window.arenaVisualizer.triggerRound(d.outcome, d.score_a, d.score_b, d.task_id);
  } else if (d.type === 'job_done') {
    const r = d.result;
    status.className = 'status done';
    const sv = (_STRATEGY_VIS && _STRATEGY_VIS[r.strategy]) || null;
    const stratPill = sv ? `<span class="badge" style="background:${sv.color}26;border-color:${sv.color};color:${sv.color};">${sv.icon} ${sv.label}</span>` : '';
    status.innerHTML = `${stratPill} &nbsp; Battle Concluded. Dur: <b>${r.duration_s}s</b> &nbsp;|&nbsp; ELO: <b>${r.elo_a_after.toFixed(0)}</b> / <b>${r.elo_b_after.toFixed(0)}</b>`;
    const btn = document.getElementById('run-btn');
    btn.disabled = false;
    btn.textContent = 'Engage Combat';
    if (r.strategy === 'PIPELINE') {
      fireConfetti(60);
      toast(`🔁 PIPELINE match complete — ran two big models on tight RAM without OOM.`, 'success', 6000);
    }
    _replay.active = false;
    // Blind Arena reveal — names appear only after match completes
    if (_blindModeActive) {
      const winner = r.a_wins > r.b_wins ? _blindMapping.a
                   : r.b_wins > r.a_wins ? _blindMapping.b
                   : 'Tie';
      toast(`🎭 <b>Reveal</b> — Model X was <b>${escText(_blindMapping.a)}</b>, Model Y was <b>${escText(_blindMapping.b)}</b>. Winner: <b>${escText(winner)}</b>`, 'success', 8000);
      _blindModeActive = false;
    }
    loadAll();
    setTimeout(() => {
      document.getElementById('battle-arena-card').style.display = 'none';
      document.getElementById('battle-leaderboard-card').style.display = 'block';
    }, 10000);
  } else if (d.type === 'tournament_start') {
    const prog = document.getElementById('tournament-progress');
    const tLog = document.getElementById('tournament-log');
    tLog.style.display = 'block';
    tLog.innerHTML = `<div style="color:var(--accent-blue); margin-bottom:12px; font-weight:800;">🏆 GRAND TOURNAMENT INITIATED: ${d.total_matches} matches scheduled.</div>`;
    prog.innerHTML = `<div style="font-size:28px; font-weight:800; color:var(--text-main); font-variant-numeric:tabular-nums; letter-spacing:-1px;">MATCH 0 / ${d.total_matches}</div>`;
  } else if (d.type === 'tournament_match_start') {
    const prog = document.getElementById('tournament-progress');
    const tLog = document.getElementById('tournament-log');
    prog.innerHTML = `<div style="font-size:28px; font-weight:800; color:var(--accent-blue); font-variant-numeric:tabular-nums; letter-spacing:-1px;">MATCH ${d.match_num} / ${d.total_matches}</div><div style="margin-top:16px; color:var(--text-main); font-size:16px; font-weight:600;">${escText(d.model_a)} &nbsp;⚔️&nbsp; ${escText(d.model_b)}</div>`;
    tLog.innerHTML += `<div style="color:var(--text-muted); margin-bottom:4px;">[Match ${d.match_num}] Initiating: ${escText(d.model_a)} vs ${escText(d.model_b)}...</div>`;
    tLog.scrollTop = tLog.scrollHeight;
  } else if (d.type === 'tournament_match_done') {
    const tLog = document.getElementById('tournament-log');
    let wText = d.a_wins > d.b_wins ? `${escText(d.model_a)} wins` : d.b_wins > d.a_wins ? `${escText(d.model_b)} wins` : `Draw`;
    let color = d.a_wins > d.b_wins || d.b_wins > d.a_wins ? 'var(--accent-green)' : 'var(--text-muted)';
    tLog.innerHTML += `<div style="color:${color}; border-left: 2px solid ${color}; padding-left: 12px; margin: 8px 0; background:rgba(255,255,255,0.02); padding-top:6px; padding-bottom:6px; border-radius:0 6px 6px 0;">[Match ${d.match_num} Result] <b>${wText}</b> (Score: ${d.a_wins}-${d.b_wins}, Draws: ${d.draws})</div>`;
    tLog.scrollTop = tLog.scrollHeight;
  } else if (d.type === 'tournament_done') {
    const prog = document.getElementById('tournament-progress');
    const btn = document.getElementById('tourney-run-btn');
    prog.innerHTML = `<div style="font-size:28px; font-weight:800; color:var(--accent-green); letter-spacing:-1px;">TOURNAMENT COMPLETE</div>`;
    btn.disabled = false;
    btn.textContent = 'Commence Tournament';
    loadAll();
    fireConfetti(120);
    toast('Tournament complete! 🏆', 'success', 5000);
  } else if (d.type === 'job_error') {
    const tbtn = document.getElementById('tourney-run-btn');
    if (btn && btn.disabled) {
      btn.disabled = false;
      btn.textContent = 'Commence Tournament';
      document.getElementById('tournament-log').innerHTML += `<div style="color:var(--accent-red); margin-top:8px;">Error: ${escText(d.error)}</div>`;
    }
    const rbtn = document.getElementById('royale-run-btn');
    if (rbtn && rbtn.disabled) {
      rbtn.disabled = false;
      rbtn.textContent = 'Initiate Royale';
      document.getElementById('royale-log').innerHTML += `<div style="color:var(--accent-red); margin-top:8px;">Error: ${escText(d.error)}</div>`;
    }
  } else if (d.type === 'royale_task_done') {
    const log = document.getElementById('royale-log');
    log.innerHTML += `<div style="color:var(--text-muted); margin-bottom:4px;">Task <b>[${escText(d.task_id)}]</b> concluded for all contenders.</div>`;
    log.scrollTop = log.scrollHeight;
  } else if (d.type === 'royale_done') {
    const prog = document.getElementById('royale-progress');
    const rRank = document.getElementById('royale-rankings');
    const btn = document.getElementById('royale-run-btn');
    
    prog.innerHTML = `<div style="font-size:24px; font-weight:800; color:var(--accent-green)">BATTLE CONCLUDED</div>`;
    btn.disabled = false;
    btn.textContent = 'Initiate Royale';
    
    let rankHtml = `<h2 style="color:var(--accent-blue)">👑 Final Standings</h2><table><thead><tr><th>Rank</th><th>Model</th><th>Score</th><th>ELO</th></tr></thead><tbody>`;
    d.result.rankings.forEach(r => {
      rankHtml += `<tr>
        <td style="font-weight:700; color:var(--accent-blue)">#${r.rank}</td>
        <td><strong>${escText(r.model)}</strong></td>
        <td>${r.total_score.toFixed(2)}</td>
        <td style="color:var(--accent-green); font-weight:700;">${r.elo_after.toFixed(0)}</td>
      </tr>`;
    });
    rankHtml += `</tbody></table>`;
    rankHtml += `<div style="margin-top:16px; font-size:12px; color:var(--text-muted);">Winner: 🏆 <b>${escText(d.result.winner)}</b> | Duration: ${d.result.duration_s}s | Royale #${d.result.royale_id}</div>`;
    
    rRank.innerHTML = rankHtml;
    rRank.style.display = 'block';
    
    loadAll();
    fireConfetti(100);
    toast(`Royale concluded — <b>${escText(d.result.winner)}</b> is the champion!`, 'success', 6000);
  }
}


document.querySelectorAll('.tab').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => {
      t.classList.remove('active');
      t.setAttribute('tabindex', '-1');
      t.setAttribute('aria-selected', 'false');
    });
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    
    el.classList.add('active');
    el.setAttribute('tabindex', '0');
    el.setAttribute('aria-selected', 'true');
    document.getElementById('tab-' + el.dataset.tab).classList.add('active');
    
    savePref('lastTab', el.dataset.tab);
    const m = { dashboard: loadCharts, datasets: loadDatasets, performance: loadPerf, hallucinations: loadHallucinations, spec: loadSpec, genome: initGenomeTab, sim: initSimTab, world: initWorldTab, tournament: () => {}, royale: () => {}, history: loadHistory };
    if (m[el.dataset.tab]) m[el.dataset.tab]();
  });
  
  el.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      el.click();
    }
  });
});
