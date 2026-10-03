/* ============================================================
   FLEXY – Shared Navigation JS  (Performance Edition)
   Key fix: /api/auth/me is cached in sessionStorage for 60s
   so navigating between pages doesn't block on an auth round-trip.
   ============================================================ */
(function () {
  'use strict';

  var AUTH_CACHE_KEY = 'flexy_me';
  var AUTH_CACHE_TTL = 60 * 1000; // 60 seconds

  /* ── Cached auth fetch ─────────────────────────────────────── */
  async function getMe() {
    try {
      var cached = sessionStorage.getItem(AUTH_CACHE_KEY);
      if (cached) {
        var parsed = JSON.parse(cached);
        if (Date.now() - parsed.ts < AUTH_CACHE_TTL) {
          return parsed.user;
        }
      }
    } catch (_) {}

    var res = await fetch('/api/auth/me', { credentials: 'include' });
    if (!res.ok) {
      // Clear stale cache on auth failure
      try { sessionStorage.removeItem(AUTH_CACHE_KEY); } catch (_) {}
      return null;
    }
    var data = await res.json();
    var user = data.user;
    try {
      sessionStorage.setItem(AUTH_CACHE_KEY, JSON.stringify({ user: user, ts: Date.now() }));
    } catch (_) {}
    return user;
  }

  // Expose so other scripts can reuse without another fetch
  window.FLEXY_GET_ME = getMe;

  /* ── Active nav ─────────────────────────────────────────────── */
  function setActiveNav() {
    var page = window.location.pathname;
    document.querySelectorAll('.top-nav-links a, .side-nav-links a, .bottom-nav a').forEach(function (a) {
      a.classList.remove('active');
      var href = a.getAttribute('href');
      if (!href || href === '#') return;
      if (page === href || (href.length > 1 && page.startsWith(href))) {
        a.classList.add('active');
      }
    });
  }

  /* ── Logout ─────────────────────────────────────────────────── */
  function setupLogout() {
    document.querySelectorAll('a[href="/login"]').forEach(function (link) {
      if (link.closest('.side-nav-bottom, .bottom-nav')) {
        link.addEventListener('click', async function (e) {
          e.preventDefault();
          try {
            await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
          } catch (_) {}
          try { sessionStorage.removeItem(AUTH_CACHE_KEY); } catch (_) {}
          window.location.href = '/login';
        });
      }
    });
  }

  /* ── Notification badge ─────────────────────────────────────── */
  var _lastNotifCount = -1;
  async function updateNotifBadge() {
    try {
      var res = await fetch('/api/notifications/unread', { credentials: 'include' });
      if (!res.ok) return;
      var data  = await res.json();
      var count = data.count || 0;
      if (count === _lastNotifCount) return; // skip DOM update if unchanged
      _lastNotifCount = count;
      document.querySelectorAll('.notif-badge').forEach(function (el) {
        el.textContent   = count > 9 ? '9+' : count;
        el.style.display = count > 0 ? 'flex' : 'none';
      });
    } catch (_) {}
  }

  /* ── Populate nav from cached session ───────────────────────── */
  async function populateNav() {
    var page = window.location.pathname;
    var noAuthPages = ['/login', '/', '/signup', '/verify-email', '/reset-password'];
    if (noAuthPages.includes(page)) return;

    var user = await getMe();
    if (!user) {
      window.location.href = '/login';
      return;
    }

    // Expose globally for page scripts
    window.FLEXY_USER = user;

    // Update avatar
    var avatarSrc = user.avatar_url || ('https://api.dicebear.com/7.x/avataaars/svg?seed=' + user.username);
    document.querySelectorAll('.nav-avatar img').forEach(function (img) {
      img.src = avatarSrc;
      img.alt = user.username;
    });

    // Notification badge (fire-and-forget, don't block nav render)
    updateNotifBadge();
    setInterval(updateNotifBadge, 30000);
  }

  /* ── Search bar ─────────────────────────────────────────────── */
  function setupSearch() {
    document.querySelectorAll('.nav-search input').forEach(function (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          var q = input.value.trim();
          if (q) window.location.href = '/dashboard?q=' + encodeURIComponent(q);
        }
      });
    });
  }

  /* ── SPA-style instant navigation ───────────────────────────── */
  // Prefetch pages on hover so clicks feel instant
  function setupPrefetch() {
    var prefetched = new Set();
    document.querySelectorAll('a[href]').forEach(function (a) {
      var href = a.getAttribute('href');
      if (!href || href.startsWith('http') || href.startsWith('#') || href.startsWith('javascript')) return;
      a.addEventListener('mouseenter', function () {
        if (prefetched.has(href)) return;
        prefetched.add(href);
        var link = document.createElement('link');
        link.rel  = 'prefetch';
        link.href = href;
        document.head.appendChild(link);
      }, { passive: true });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setActiveNav();
    setupLogout();
    setupSearch();
    populateNav();
    setupPrefetch();
  });
})();