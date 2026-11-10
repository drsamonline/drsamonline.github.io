/* Per-platform player factories.
   soundcloud -> official widget, controllable through the SoundCloud Widget API (queue works)
   suno       -> /embed/ player, one iframe per track, no JS API (no queue)
   others     -> no player page exists, so the row is a link out                        */
(function () {
  const SC_API = 'https://w.soundcloud.com/player/api.js';
  let apiPromise = null;

  function loadSCApi() {
    if (window.SC && window.SC.Widget) return Promise.resolve(window.SC);
    if (apiPromise) return apiPromise;
    apiPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = SC_API;
      s.onload = () => (window.SC ? resolve(window.SC) : reject(new Error('SC missing')));
      s.onerror = () => reject(new Error('SC failed'));
      document.head.appendChild(s);
    });
    return apiPromise;
  }

  function soundcloudWidgetSrc(trackUrl) {
    return 'https://w.soundcloud.com/player/?url=' + encodeURIComponent(trackUrl) +
      '&color=%23ff8a3d&auto_play=true&hide_related=true&show_comments=false' +
      '&show_user=true&show_reposts=false&show_teaser=false&visual=false';
  }

  function sunoFrame(embedUrl, height) {
    const f = document.createElement('iframe');
    f.src = embedUrl;
    f.height = String(height || 240);
    f.loading = 'lazy';
    f.allow = 'autoplay; encrypted-media; fullscreen; clipboard-write';
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    f.title = 'Suno player';
    return f;
  }

  window.Embeds = { loadSCApi, soundcloudWidgetSrc, sunoFrame };
})();
