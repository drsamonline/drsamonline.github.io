/* Music page: album grid, album view, per-track players, ratings, licence badges. */
(function () {
  const HUB = 'https://drsamonline.github.io/';
  const state = {
    data: null,
    queue: [],          // soundcloud tracks currently queued
    qi: -1,
    widget: null,
    playing: false
  };

  const app = document.getElementById('app');
  const bar = document.getElementById('playerbar');
  const pbTitle = document.getElementById('pb-title');
  const pbSub = document.getElementById('pb-sub');
  const pbFrame = document.getElementById('pb-frame');
  const pbToggle = document.getElementById('pb-toggle');

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const SITE_LABEL = {
    soundcloud: 'SoundCloud', suno: 'Suno', flow_music: 'Flow Music',
    newgrounds: 'Newgrounds', freesound: 'Freesound'
  };

  /* ---------- data ---------- */
  async function loadData() {
    if (window.__MUSIC_DATA__) return window.__MUSIC_DATA__;
    const res = await fetch('data/tracks.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error('manifest ' + res.status);
    return res.json();
  }

  /* ---------- covers ---------- */
  function coverStyle(seed) {
    let h = 0;
    for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 360;
    const a = h, b = (h + 46) % 360;
    return `background:linear-gradient(150deg,hsl(${a} 52% 26%),hsl(${b} 60% 12%))`;
  }

  /* cover block: real artwork when we have it, generated gradient behind it otherwise */
  function coverHTML(album, extraClass) {
    const art = album.cover_url
      ? `<img class="cover-img" src="${esc(album.cover_url)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">`
      : '';
    return `<div class="cover ${extraClass || ''}" style="${coverStyle(album.id)}">${art}` +
           `<span class="cover-count">${album.track_count} tracks</span></div>`;
  }

  /* ---------- grid ---------- */
  function renderGrid() {
    const d = state.data;
    const groups = {};
    d.albums.forEach(a => (groups[a.source_label] = groups[a.source_label] || []).push(a));

    let html = `
      <div class="page-intro">
        <h1>Music</h1>
        <p>Albums and collections from SoundCloud, Suno, Flow Music, Newgrounds and Freesound.
           Playback happens on the platform that hosts the audio; this page is the index.</p>
        <div class="stat-line">
          <span><b>${d.counts.albums}</b> albums</span>
          <span><b>${d.counts.tracks}</b> tracks</span>
          <span><b>${d.counts.commercial}</b> commercial-use</span>
          <span><b>${d.counts.personal}</b> personal-use only</span>
        </div>
      </div>`;

    Object.keys(groups).forEach(label => {
      html += `<h2 class="section-label">${esc(label)}</h2><div class="grid">`;
      groups[label].forEach(a => {
        html += `
          <a class="album-card" href="#/a/${esc(a.slug)}">
            ${coverHTML(a)}
            <div class="album-body">
              <p class="album-title">${esc(a.title)}</p>
              <div class="album-meta">
                <span>${[a.year, a.duration_label].filter(Boolean).map(esc).join(' · ')}</span>
              </div>
            </div>
          </a>`;
      });
      html += '</div>';
    });

    app.innerHTML = html;
    window.scrollTo({ top: 0 });
  }

  /* ---------- album ---------- */
  function renderAlbum(slug) {
    const d = state.data;
    const album = d.albums.find(a => a.slug === slug);
    if (!album) return renderGrid();

    const tracks = d.tracks
      .filter(t => t.album_id === album.id)
      .sort((x, y) => x.position - y.position);

    let html = `
      <a class="back" href="#/">◄ All albums</a>
      <div class="album-head">
        ${coverHTML(album)}
        <div class="album-head-txt">
          <h1>${esc(album.title)}</h1>
          <p>${[
                album.title.startsWith(album.source_label) ? null : album.source_label,
                album.year, album.duration_label
              ].filter(Boolean).map(esc).join(' · ')}</p>
        </div>
      </div>
      <div class="tracklist">`;

    tracks.forEach(t => {
      const isLink = t.embed.kind === 'link';
      const playLabel = isLink ? 'Open on ' + (SITE_LABEL[t.embed.site] || 'source') : 'Play';
      html += `
        <div class="track" data-id="${esc(t.id)}">
          <button class="play ${isLink ? 'is-link' : ''}" type="button"
                  aria-label="${esc(playLabel)} — ${esc(t.title)}">${isLink ? '↗' : '▶'}</button>
          <span class="track-pos">${t.position}</span>
          <div class="track-main">
            <div class="track-title">${esc(t.title)} ${t.is_take ? '<span class="take-badge">take</span>' : ''}</div>
            <div class="track-sub">
              <span>${esc(SITE_LABEL[t.embed.site] || t.embed.site)}</span>
              ${t.link_pending ? '<span title="The direct link for this track was never captured; the button opens the profile page.">· link pending</span>' : ''}
              ${t.also_on.length ? '· ' + t.also_on.map(o =>
                `<a href="${esc(o.url)}" target="_blank" rel="noopener">also on ${esc(o.label)}` +
                (o.licence ? ` (${esc(o.licence)})` : '') + '</a>').join(' · ') : ''}
            </div>
          </div>
          <span class="track-dur">${esc(t.duration_label)}</span>
          <div class="stars-slot"></div>
          <div class="badge-slot"></div>
        </div>`;
    });

    html += '</div>';
    app.innerHTML = html;

    tracks.forEach(t => {
      const row = app.querySelector(`.track[data-id="${t.id}"]`);
      row.querySelector('.stars-slot').appendChild(Ratings.widget(t.id));
      const slot = row.querySelector('.badge-slot');
      slot.appendChild(Licences.badge(t.rights));
      if (t.embed.source_url) {
        const src = document.createElement('a');
        src.className = 'src-link';
        src.href = t.embed.source_url;
        src.target = '_blank';
        src.rel = 'noopener';
        src.textContent = 'source ↗';
        src.title = 'Where this track lives, and where its licence is stated';
        slot.appendChild(src);
      }

      row.querySelector('.play').addEventListener('click', () => {
        if (t.embed.kind === 'link') {
          window.open(t.embed.source_url, '_blank', 'noopener');
        } else if (t.embed.site === 'soundcloud') {
          state.queue = tracks.filter(x => x.embed.kind === 'iframe' && x.embed.site === 'soundcloud');
          state.qi = state.queue.findIndex(x => x.id === t.id);
          playQueueItem();
        } else {
          toggleInline(row, t);
        }
      });
    });

    window.scrollTo({ top: 0 });
  }

  /* ---------- suno inline player ---------- */
  function toggleInline(row, track) {
    const next = row.nextElementSibling;
    if (next && next.classList.contains('inline-player')) { next.remove(); return; }
    document.querySelectorAll('.inline-player').forEach(el => el.remove());
    const holder = document.createElement('div');
    holder.className = 'inline-player';
    holder.appendChild(Embeds.sunoFrame(track.embed.player_url, 240));
    row.after(holder);
  }

  /* ---------- soundcloud queue in the bottom bar ---------- */
  function playQueueItem() {
    const t = state.queue[state.qi];
    if (!t) return;
    bar.hidden = false;
    pbTitle.textContent = t.title;
    pbSub.textContent = 'SoundCloud · track ' + (state.qi + 1) + ' of ' + state.queue.length;
    document.querySelectorAll('.play').forEach(b => b.classList.remove('is-playing'));
    const btn = app.querySelector(`.track[data-id="${t.id}"] .play`);
    if (btn) btn.classList.add('is-playing');

    if (!state.widget) {
      const f = document.createElement('iframe');
      f.id = 'scw';
      f.allow = 'autoplay';
      f.src = Embeds.soundcloudWidgetSrc(t.embed.source_url);
      pbFrame.appendChild(f);
      Embeds.loadSCApi().then(SC => {
        state.widget = SC.Widget(f);
        state.widget.bind(SC.Widget.Events.FINISH, () => next());
        state.widget.bind(SC.Widget.Events.PLAY, () => { state.playing = true; pbToggle.textContent = '❚❚'; });
        state.widget.bind(SC.Widget.Events.PAUSE, () => { state.playing = false; pbToggle.textContent = '▶'; });
      }).catch(() => {});
    } else {
      state.widget.load(t.embed.source_url, { auto_play: true });
    }
  }

  function next() {
    if (!state.queue.length) return;
    state.qi = (state.qi + 1) % state.queue.length;
    playQueueItem();
  }

  function prev() {
    if (!state.queue.length) return;
    state.qi = (state.qi - 1 + state.queue.length) % state.queue.length;
    playQueueItem();
  }

  document.getElementById('pb-next').addEventListener('click', next);
  document.getElementById('pb-prev').addEventListener('click', prev);
  pbToggle.addEventListener('click', () => {
    if (!state.widget) return;
    if (state.playing) state.widget.pause(); else state.widget.play();
  });

  /* ---------- licensing ---------- */
  function renderLicensing() {
    const d = state.data;
    app.innerHTML = `
      <a class="back" href="#/">◄ All albums</a>
      <div class="page-intro">
        <h1>Licensing</h1>
        <p>Every track carries one of two badges. The tier is decided when the track is catalogued,
           never guessed in the browser.</p>
      </div>
      <div class="lic-grid">
        <div class="lic-card">
          <h3><span class="badge badge-commercial">Commercial use granted</span></h3>
          <p>Listening on this page is free. Commercial use of the file is a separate permission
             that comes from the platform or from me.</p>
          <ul>
            <li>SoundCloud tracks marked all-rights-reserved or CC-BY-SA</li>
            <li>Suno songs downloaded on a paid plan</li>
            <li>Freesound sounds under an attribution licence — credit required</li>
          </ul>
        </div>
        <div class="lic-card">
          <h3><span class="badge badge-personal">Personal use only</span></h3>
          <p>Free to listen here. No commercial use, and no re-upload. This covers most of the
             catalogue, because Flow Music publishes no music-specific licence.</p>
          <ul>
            <li>Everything on Flow Music, until clearance is confirmed</li>
            <li>SoundCloud tracks under CC-BY-NC-SA or CC-BY-NC-ND</li>
            <li>Suno songs whose download tier is unverified</li>
          </ul>
        </div>
      </div>
      <p class="note">Where the same recording appears on two platforms under different licences,
        the stricter licence governs until stated otherwise. ${d.counts.commercial} tracks are
        marked commercial-use and ${d.counts.personal} personal-use only. For anything beyond
        listening, ask me directly rather than assuming.</p>`;
    window.scrollTo({ top: 0 });
  }

  /* ---------- router ---------- */
  function route() {
    const hash = location.hash.replace(/^#/, '') || '/';
    if (hash.startsWith('/a/')) renderAlbum(decodeURIComponent(hash.slice(3)));
    else if (hash === '/licensing') renderLicensing();
    else renderGrid();
  }

  window.addEventListener('hashchange', route);

  loadData().then(data => {
    state.data = data;
    route();
  }).catch(err => {
    app.innerHTML = '<div class="page-intro"><h1>Could not load the catalogue</h1>' +
      '<p>The manifest at <code>data/tracks.json</code> did not load: ' + esc(err.message) + '</p></div>';
  });
})();
