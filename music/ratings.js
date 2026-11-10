/* Star ratings. Stored per device in localStorage — there is no backend, and the UI says so. */
(function () {
  const KEY = id => 'music:rating:' + id;

  function get(id) {
    try { return Number(localStorage.getItem(KEY(id)) || 0); } catch (e) { return 0; }
  }

  function set(id, value) {
    try { localStorage.setItem(KEY(id), String(value)); } catch (e) {}
  }

  function widget(trackId, onChange) {
    const wrap = document.createElement('div');
    wrap.className = 'stars';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', 'Your rating, saved on this device');

    function paint(value) {
      [...wrap.children].forEach((b, i) => {
        b.classList.toggle('on', i < value);
        b.setAttribute('aria-pressed', String(i < value));
      });
    }

    for (let i = 1; i <= 5; i++) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = '★';
      b.setAttribute('aria-label', i + (i === 1 ? ' star' : ' stars'));
      b.addEventListener('click', () => {
        const next = get(trackId) === i ? 0 : i;   // click the same star to clear
        set(trackId, next);
        paint(next);
        if (onChange) onChange(next);
      });
      wrap.appendChild(b);
    }

    paint(get(trackId));
    return wrap;
  }

  window.Ratings = { get, set, widget };
})();
