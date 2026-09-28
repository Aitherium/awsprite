/*!
 * awsprite embed: the member's Sprite, living on their homestead.
 *
 *   <div data-aither-sprite data-homestead="yourname"></div>
 *   <script src="./sprite-embed.js" defer></script>
 *
 * Dependency-free. Reads ONE public, uncredentialed JSON document (the pet
 * card) and renders it with textContent only, inside a shadow root so the
 * site's own CSS cannot bend it. It never reads or writes cookies and never
 * sends credentials: a homestead is member-authored content on a separate
 * domain, and the embed must work the same for every visitor.
 *
 * Attributes on the slot:
 *   data-homestead  the homestead name (default: first DNS label of
 *                   location.hostname when it ends with .aitherium.org)
 *   data-api        pet-card base URL (default below); the name is appended
 */
(function () {
  'use strict';

  var DEFAULT_API = 'https://api.aitherium.com/api/sprite/pet-card/';
  var NAME_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

  var CSS = [
    ':host{all:initial;display:block}',
    '.card{box-sizing:border-box;max-width:320px;padding:16px 18px;border-radius:14px;',
    'background:#050507;color:#EDEFF5;border:1px solid rgba(255,255,255,.08);',
    'font:400 14px/1.45 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}',
    '.label{font:500 10px/1 "JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;',
    'letter-spacing:.18em;text-transform:uppercase;color:rgba(237,239,245,.55);',
    'display:flex;align-items:center;gap:8px}',
    '.dot{width:6px;height:6px;border-radius:50%;background:#5EC9CC;',
    'box-shadow:0 0 8px rgba(94,201,204,.35);animation:breathe 2.4s cubic-bezier(.2,.8,.2,1) infinite alternate}',
    '.name{margin:10px 0 2px;font-size:22px;font-weight:300;letter-spacing:-.02em}',
    '.line{color:rgba(237,239,245,.55);font-size:13px}',
    '.line b{color:#EDEFF5;font-weight:500}',
    '.off .dot{background:rgba(237,239,245,.25);box-shadow:none;animation:none}',
    '.off .name{color:rgba(237,239,245,.55)}',
    '@keyframes breathe{from{opacity:.45}to{opacity:1}}',
    '@media (prefers-reduced-motion:reduce){.dot{animation:none}}'
  ].join('');

  function homesteadName(el) {
    var explicit = (el.getAttribute('data-homestead') || '').trim().toLowerCase();
    if (explicit) return NAME_RE.test(explicit) ? explicit : '';
    var host = (window.location && window.location.hostname || '').toLowerCase();
    var suffix = '.aitherium.org';
    if (host.length > suffix.length && host.slice(-suffix.length) === suffix) {
      var label = host.slice(0, -suffix.length).split('.')[0];
      return NAME_RE.test(label) ? label : '';
    }
    return '';
  }

  function node(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = String(text);
    return n;
  }

  function mount(el) {
    var root = el.attachShadow ? el.attachShadow({ mode: 'open' }) : el;
    var style = node('style');
    style.textContent = CSS;
    root.appendChild(style);
    var card = node('div', 'card');
    card.setAttribute('role', 'status');
    card.setAttribute('aria-live', 'polite');
    root.appendChild(card);
    return card;
  }

  function header(card, text) {
    var label = node('div', 'label');
    label.appendChild(node('span', 'dot'));
    label.appendChild(node('span', null, text));
    card.appendChild(label);
  }

  function renderOffline(card, reason) {
    card.textContent = '';
    card.className = 'card off';
    header(card, 'sprite \u00b7 offline');
    card.appendChild(node('div', 'name', 'Sprite is away'));
    card.appendChild(node('div', 'line', reason));
  }

  function ageText(days) {
    var d = Math.max(0, Math.floor(Number(days) || 0));
    return d === 1 ? '1 day old' : d + ' days old';
  }

  function renderCard(card, data) {
    card.textContent = '';
    card.className = data.dormant ? 'card off' : 'card';
    header(card, data.dormant ? 'sprite \u00b7 resting' : 'sprite \u00b7 home');
    card.appendChild(node('div', 'name', data.name || 'Sprite'));
    var line = node('div', 'line');
    var stage = node('b', null, data.stage || 'egg');
    line.appendChild(stage);
    if (data.mood_label) line.appendChild(document.createTextNode(' \u00b7 ' + data.mood_label));
    card.appendChild(line);
    card.appendChild(node('div', 'line', ageText(data.age_days)));
    if (data.intellect && data.intellect.label) {
      card.appendChild(node('div', 'line', 'mind \u00b7 ' + data.intellect.label));
    }
  }

  function load(el) {
    if (el.getAttribute('data-aither-sprite-mounted')) return;
    el.setAttribute('data-aither-sprite-mounted', '1');
    var card = mount(el);
    var name = homesteadName(el);
    if (!name) {
      renderOffline(card, 'No homestead name on this page.');
      return;
    }
    header(card, 'sprite');
    card.appendChild(node('div', 'line', 'waking up\u2026'));
    var base = el.getAttribute('data-api') || DEFAULT_API;
    if (base.charAt(base.length - 1) !== '/') base += '/';
    if (typeof fetch !== 'function') {
      renderOffline(card, 'This browser cannot reach the Sprite.');
      return;
    }
    fetch(base + encodeURIComponent(name), {
      method: 'GET',
      credentials: 'omit',
      mode: 'cors',
      headers: { Accept: 'application/json' }
    })
      .then(function (res) {
        if (res.status === 404) throw new Error('No Sprite lives here yet.');
        if (!res.ok) throw new Error('The Sprite service answered ' + res.status + '.');
        return res.json();
      })
      .then(function (data) {
        if (!data || typeof data !== 'object') throw new Error('Unreadable pet card.');
        renderCard(card, data);
      })
      .catch(function (err) {
        // A TypeError is the network layer (offline, DNS, CORS): say so plainly
        // rather than surfacing a browser-specific string.
        var msg = err && err.message && !(err instanceof TypeError)
          ? err.message
          : 'The Sprite service is unreachable.';
        renderOffline(card, msg);
      });
  }

  function boot() {
    var slots = document.querySelectorAll('[data-aither-sprite]');
    for (var i = 0; i < slots.length; i++) load(slots[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
