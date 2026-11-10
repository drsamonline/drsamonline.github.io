/* Licence badges. The tier is decided at ingest time and never inferred in the browser. */
(function () {
  const LABEL = {
    commercial: 'Commercial use granted',
    personal: 'Personal use only'
  };

  function badge(rights) {
    const el = document.createElement('span');
    const tier = rights && rights.tier === 'commercial' ? 'commercial' : 'personal';
    el.className = 'badge badge-' + tier;
    el.textContent = LABEL[tier];
    const parts = [rights && rights.summary, rights && rights.licence && ('Licence: ' + rights.licence)]
      .filter(Boolean);
    el.title = parts.join('\n\n');
    el.setAttribute('aria-label', LABEL[tier] + '. ' + (rights && rights.summary || ''));
    return el;
  }

  function sourceChip(label) {
    const el = document.createElement('span');
    el.className = 'badge badge-source';
    el.textContent = label;
    return el;
  }

  window.Licences = { badge, sourceChip, LABEL };
})();
