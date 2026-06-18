// ═══════════════════════════════════════════════════════════════
// XSS DEFENSE — sanitize ANY string derived from a model response
// before it touches innerHTML. Configured to strip script/event
// handlers/iframes but allow <pre>/<code>/<b>/<i>/<br>/<span> so
// formatCodeBlocks() still renders highlight.js markup.
// ═══════════════════════════════════════════════════════════════
const _purifyConfig = {
  ALLOWED_TAGS: ['p','br','b','i','em','strong','u','code','pre','span','div',
                 'ul','ol','li','blockquote','h1','h2','h3','h4','table','thead',
                 'tbody','tr','th','td','hr'],
  ALLOWED_ATTR: ['class','style','data-tip'],
  ALLOW_DATA_ATTR: false,
  FORBID_TAGS: ['script','iframe','object','embed','form','input','textarea','meta','link','base','svg','math'],
  FORBID_ATTR: ['onerror','onload','onclick','onmouseover','onfocus','onsubmit','href','src','formaction','action'],
};
// Returns a DOMPurify-cleaned HTML string. Falls back to text-escape if
// DOMPurify failed to load.
function safeHTML(dirty) {
  if (typeof dirty !== 'string') dirty = String(dirty ?? '');
  if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
    return DOMPurify.sanitize(dirty, _purifyConfig);
  }
  return dirty.replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
}
// Plain-text helper — never returns HTML, just escapes.
function escText(s) {
  return String(s ?? '').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
}

const api = async (p, o) => {
  const r = await fetch(p, o);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
};
const html = async (p) => (await fetch(p)).text();

let socket = null;
let currentJobId = null;
let currentPlayData = null;

// ═══════════════════════════════════════════════════════════════
// PERSISTED PREFERENCES (localStorage)
// ═══════════════════════════════════════════════════════════════
const PREFS_KEY = 'arenaPrefs';
const PREFS = (() => {
  try { return JSON.parse(localStorage.getItem(PREFS_KEY)) || {}; }
  catch(e) { return {}; }
})();
function savePref(k, v) {
  PREFS[k] = v;
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(PREFS)); } catch(e) {}
}

// ═══════════════════════════════════════════════════════════════
// TOAST SYSTEM (replaces all alert() calls)
// ═══════════════════════════════════════════════════════════════
const TOAST_ICONS = { info: 'ℹ', success: '✓', error: '✕', warn: '⚠' };
function toast(message, kind = 'info', timeout = 4000) {
  const stack = document.getElementById('toast-stack');
  const el = document.createElement('div');
  el.className = `toast toast-${kind}`;
  el.innerHTML = `
    <span class="icon">${TOAST_ICONS[kind] || 'ℹ'}</span>
    <div class="body">${safeHTML(message)}</div>
    <button class="close" aria-label="Dismiss">×</button>
  `;
  stack.appendChild(el);
  requestAnimationFrame(() => el.classList.add('visible'));
  const dismiss = () => {
    el.classList.remove('visible');
    setTimeout(() => el.remove(), 300);
  };
  el.querySelector('.close').onclick = dismiss;
  if (timeout > 0) setTimeout(dismiss, timeout);
  return dismiss;
}
// Replace alert() globally — keep native available as nativeAlert
window.nativeAlert = window.alert;
window.alert = (msg) => toast(String(msg), 'warn', 5000);

// ═══════════════════════════════════════════════════════════════
// ANIMATED NUMBER COUNTERS
// ═══════════════════════════════════════════════════════════════
function animateNumber(el, target, duration = 800) {
  if (!el) return;
  const start = parseFloat(el.textContent.replace(/[^\d.-]/g, '')) || 0;
  if (start === target) return;
  const t0 = performance.now();
  const ease = t => 1 - Math.pow(1 - t, 3);
  function tick(now) {
    const p = Math.min(1, (now - t0) / duration);
    const v = start + (target - start) * ease(p);
    el.textContent = Number.isInteger(target) ? Math.round(v) : v.toFixed(1);
    if (p < 1) requestAnimationFrame(tick);
    else {
      el.textContent = target;
      el.classList.add('pulse');
      setTimeout(() => el.classList.remove('pulse'), 600);
    }
  }
  requestAnimationFrame(tick);
}

// ═══════════════════════════════════════════════════════════════
// THEME SYSTEM (cycle: default → cyber → forest)
// ═══════════════════════════════════════════════════════════════
const THEMES = ['default', 'cyber', 'forest'];
function applyTheme(name) {
  if (name === 'default') document.body.removeAttribute('data-theme');
  else document.body.setAttribute('data-theme', name);
  savePref('theme', name);
}
function cycleTheme() {
  const cur = PREFS.theme || 'default';
  const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
  applyTheme(next);
  toast(`Theme: <b>${next}</b>`, 'info', 1500);
}
applyTheme(PREFS.theme || 'default');

// ═══════════════════════════════════════════════════════════════
// SYSTEM TELEMETRY POLLING (header pills)
// ═══════════════════════════════════════════════════════════════
async function pollSystem() {
  try {
    const s = await api('/api/system');
    const setPill = (id, value, max = 100) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = value;
      const pill = el.closest('.sys-pill');
      pill.classList.remove('warn', 'crit');
      if (value >= max * 0.9) pill.classList.add('crit');
      else if (value >= max * 0.7) pill.classList.add('warn');
    };
    setPill('sys-cpu', Math.round(s.cpu_pct));
    setPill('sys-ram', Math.round(s.ram_pct));
    document.getElementById('sys-vram').textContent = (s.vram_used_gb || 0).toFixed(1);
  } catch(e) {}
}

// ═══════════════════════════════════════════════════════════════
// COMMAND PALETTE (Cmd+K / Ctrl+K)
// ═══════════════════════════════════════════════════════════════
const PALETTE_COMMANDS = [
  { icon: '📊', label: 'Go to Dashboard',       sub: 'Overview & charts',         action: () => goTab('dashboard') },
  { icon: '⚔️', label: 'Go to Arena Match',      sub: 'Pairwise model battle',     action: () => goTab('battle') },
  { icon: '🏆', label: 'Go to Tournament',       sub: 'Round-robin between N models', action: () => goTab('tournament') },
  { icon: '🎮', label: 'Go to Playground',       sub: 'A/B test prompts manually', action: () => goTab('playground') },
  { icon: '🔍', label: 'Go to Inspect',          sub: 'Drill into a task ID',      action: () => goTab('inspect') },
  { icon: '📈', label: 'Go to Report',           sub: 'Per-model category stats',  action: () => goTab('report') },
  { icon: '📚', label: 'Go to Datasets',         sub: 'Import HuggingFace tasks',  action: () => goTab('datasets') },
  { icon: '⚡', label: 'Go to Performance',      sub: 'TPS / latency / TTFT',      action: () => goTab('performance') },
  { icon: '🚀', label: 'Go to Spec Decode',      sub: 'Speculative decoding servers', action: () => goTab('spec') },
  { icon: '🎨', label: 'Cycle theme',            sub: 'default ↔ cyber ↔ forest',  action: cycleTheme,            kbd: 'T' },
  { icon: '↻',  label: 'Refresh leaderboard',    sub: 'Reload ELO & history',      action: () => { loadAll(); toast('Refreshed', 'success', 1500); } },
  { icon: '🚀', label: 'Start ALL spec servers', sub: 'llama-server × 10',         action: () => specStartAll() },
  { icon: '🛑', label: 'Stop ALL spec servers',  sub: 'kill all spec processes',   action: () => specStopAll() },
  { icon: '🏁', label: 'Bench ALL running spec', sub: 'Parallel TPS bench',        action: () => { goTab('spec'); setTimeout(() => specBenchAll(), 200); } },
];
function goTab(name) { const t = document.querySelector(`.tab[data-tab="${name}"]`); if (t) t.click(); closePalette(); }
let paletteIndex = 0;
function openPalette() {
  document.getElementById('palette-backdrop').classList.add('visible');
  const inp = document.getElementById('palette-input');
  inp.value = ''; paletteIndex = 0;
  renderPalette('');
  setTimeout(() => inp.focus(), 50);
}
function closePalette() { document.getElementById('palette-backdrop').classList.remove('visible'); }
function renderPalette(q) {
  q = q.toLowerCase().trim();
  const matches = q
    ? PALETTE_COMMANDS.filter(c => c.label.toLowerCase().includes(q) || c.sub.toLowerCase().includes(q))
    : PALETTE_COMMANDS;
  const list = document.getElementById('palette-list');
  if (!matches.length) { list.innerHTML = '<div class="palette-empty">No commands match.</div>'; return; }
  paletteIndex = Math.min(paletteIndex, matches.length - 1);
  list.innerHTML = matches.map((c, i) => `
    <div class="palette-item ${i === paletteIndex ? 'active' : ''}" data-idx="${i}">
      <span class="pal-icon">${c.icon}</span>
      <div class="pal-label">${c.label}<div class="pal-sub">${c.sub}</div></div>
      ${c.kbd ? `<span class="pal-kbd">${c.kbd}</span>` : ''}
    </div>
  `).join('');
  list.querySelectorAll('.palette-item').forEach((el, i) => {
    el.onclick = () => matches[i].action();
    el.onmouseenter = () => { paletteIndex = i; renderPalette(q); };
  });
}
document.getElementById('palette-input').addEventListener('input', e => renderPalette(e.target.value));
document.getElementById('palette-input').addEventListener('keydown', e => {
  const q = e.target.value;
  const matches = q
    ? PALETTE_COMMANDS.filter(c => c.label.toLowerCase().includes(q.toLowerCase()) || c.sub.toLowerCase().includes(q.toLowerCase()))
    : PALETTE_COMMANDS;
  if (e.key === 'ArrowDown') { paletteIndex = Math.min(matches.length - 1, paletteIndex + 1); renderPalette(q); e.preventDefault(); }
  else if (e.key === 'ArrowUp') { paletteIndex = Math.max(0, paletteIndex - 1); renderPalette(q); e.preventDefault(); }
  else if (e.key === 'Enter') { if (matches[paletteIndex]) matches[paletteIndex].action(); }
  else if (e.key === 'Escape') closePalette();
});
document.getElementById('palette-backdrop').addEventListener('click', e => {
  if (e.target.id === 'palette-backdrop') closePalette();
});
document.getElementById('palette-btn').onclick = openPalette;
document.getElementById('theme-toggle').onclick = cycleTheme;

// Global keyboard shortcuts
document.addEventListener('keydown', e => {
  const inField = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault(); openPalette();
  } else if (!inField && e.key === '?' && !e.metaKey && !e.ctrlKey) {
    e.preventDefault(); openPalette();
  } else if (!inField && e.key.toLowerCase() === 't') {
    cycleTheme();
  } else if (e.key === 'Escape') {
    closePalette();
  }
});

// ═══════════════════════════════════════════════════════════════
// CONFETTI (tournament wins, big victories)
// ═══════════════════════════════════════════════════════════════
function fireConfetti(count = 80) {
  const colors = ['#58a6ff', '#3fb950', '#b794f6', '#f59e0b', '#22d3ee'];
  for (let i = 0; i < count; i++) {
    const c = document.createElement('div');
    c.className = 'confetti';
    const sz = 6 + Math.random() * 8;
    c.style.cssText = `
      left: ${50 + (Math.random() - 0.5) * 30}%; top: -20px;
      width: ${sz}px; height: ${sz * 0.4}px;
      background: ${colors[Math.floor(Math.random() * colors.length)]};
      transform: rotate(${Math.random() * 360}deg);
      border-radius: 2px;
    `;
    document.body.appendChild(c);
    const dx = (Math.random() - 0.5) * 400;
    const dy = window.innerHeight + 100;
    const rot = (Math.random() - 0.5) * 720;
    const dur = 1800 + Math.random() * 1400;
    c.animate(
      [
        { transform: c.style.transform, opacity: 1 },
        { transform: `translate(${dx}px, ${dy}px) rotate(${rot}deg)`, opacity: 0 }
      ],
      { duration: dur, easing: 'cubic-bezier(0.2, 0.6, 0.4, 1)', fill: 'forwards' }
    );
    setTimeout(() => c.remove(), dur);
  }
}

