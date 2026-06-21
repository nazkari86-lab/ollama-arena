// CSP's script-src has no 'unsafe-inline' (nonces/hashes never apply to
// inline onclick="..." attributes, only to <script> elements) -- every
// action button is wired here instead, via addEventListener, since this
// file is loaded as an external <script src>, which CSP allows unconditionally.
function _wireStaticButtons() {
  const on = (id, handler) => document.getElementById(id)?.addEventListener('click', handler);
  on('lb-refresh-btn', () => loadAll());
  on('run-btn', () => runMatch());
  on('tourney-run-btn', () => runTournament());
  on('royale-run-btn', () => runRoyale());
  on('play-gen-btn', () => generatePlayground());
  on('vote-x-btn', () => votePlayground('x'));
  on('vote-y-btn', () => votePlayground('y'));
  on('vote-draw-btn', () => votePlayground('draw'));
  on('inspect-btn', () => loadInspect());
  on('report-btn', () => loadReport());
  on('spec-refresh-btn', () => loadSpec());
  on('spec-start-all-btn', () => specStartAll());
  on('spec-stop-all-btn', () => specStopAll());
  on('spec-stream-btn', () => specStream());
  on('spec-bench-btn', () => specGenerate());
  on('spec-vs-base-btn', () => specVsBase());
  on('spec-bench-all-btn', () => specBenchAll());
}

(async () => {
  _wireStaticButtons();
  try {
    const v = await api('/api/version');
    document.getElementById('version-badge').textContent = 'v' + v.version;
  } catch(e){}
  loadModels();
  loadCategories();
  loadAll();
  connectWS();
  // Start system telemetry polling (every 3s)
  pollSystem();
  setInterval(pollSystem, 3000);
  // A URL hash (e.g. /#genome, used by the /genome -> /#genome redirect)
  // is an explicit navigation request and takes priority over whatever
  // tab was last open; otherwise fall back to the localStorage-restored
  // last tab.
  const hashTab = window.location.hash.replace(/^#/, '');
  const targetTab = hashTab || PREFS.lastTab;
  if (targetTab) {
    const t = document.querySelector(`.tab[data-tab="${targetTab}"]`);
    if (t && targetTab !== 'dashboard') t.click();
  }
  // Welcome toast (once per session)
  if (!sessionStorage.getItem('arenaWelcomed')) {
    setTimeout(() => {
      toast('Welcome! Press <span class="kbd-tag">⌘K</span> for commands · <span class="kbd-tag">T</span> for theme · <span class="kbd-tag">?</span> for help', 'info', 6000);
      sessionStorage.setItem('arenaWelcomed', '1');
    }, 800);
  }
})();
