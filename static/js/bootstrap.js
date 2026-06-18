(async () => {
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
  // Restore last tab from localStorage
  if (PREFS.lastTab) {
    const t = document.querySelector(`.tab[data-tab="${PREFS.lastTab}"]`);
    if (t && PREFS.lastTab !== 'dashboard') t.click();
  }
  // Welcome toast (once per session)
  if (!sessionStorage.getItem('arenaWelcomed')) {
    setTimeout(() => {
      toast('Welcome! Press <span class="kbd-tag">⌘K</span> for commands · <span class="kbd-tag">T</span> for theme · <span class="kbd-tag">?</span> for help', 'info', 6000);
      sessionStorage.setItem('arenaWelcomed', '1');
    }, 800);
  }
})();
