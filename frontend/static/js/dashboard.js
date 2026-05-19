/* ============================================================
   FLEXY – Dashboard JS  (Performance-optimised + Wishlist fixed)
   - Auth, watchlist, sections & categories fetched in parallel
   - Skeleton cards replaced when data arrives
   - Heart button adds/removes from WISHLIST (renamed from watchlist)
   ============================================================ */
(function () {
  'use strict';

  const API  = '';
  let currentUser  = null;
  let skip         = 0;
  let activeSort   = 'ends_at';
  let activeFilter = 'all';
  let searchQ      = '';
  let heroAuctions = [];
  let heroIdx      = 0;
  let heroInterval = null;
  let watchingIds  = new Set();

  /* ── Helpers ── */
  function inr(paise) {
    return '₹' + (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 0 });
  }

  function pad(n) { return String(n).padStart(2, '0'); }

  function formatCountdown(isoStr) {
    const secs = Math.max(0, Math.floor((new Date(isoStr) - Date.now()) / 1000));
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
    if (h > 0) return pad(h) + 'h ' + pad(m) + 'm';
    if (m > 0) return pad(m) + 'm ' + pad(s) + 's';
    return pad(s) + 's';
  }

  function urgencyClass(isoStr) {
    const secs = Math.max(0, Math.floor((new Date(isoStr) - Date.now()) / 1000));
    return secs < 3600 ? 'colored' : 'dark';
  }

  /* ── Heart / Wishlist toggle ── */
  window.toggleWatch = async function(e, auctionId) {
    e.stopPropagation();
    const btn  = e.currentTarget;
    const icon = btn.querySelector('span');
    const inWl = btn.dataset.watching === 'true';
    try {
      const res = await fetch('/api/watchlist/' + auctionId, {
        method: inWl ? 'DELETE' : 'POST',
        credentials: 'include'
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      if (res.ok) {
        btn.dataset.watching = inWl ? 'false' : 'true';
        icon.textContent     = inWl ? 'favorite_border' : 'favorite';
        icon.style.color     = inWl ? '#888' : '#ff6e84';
        if (!inWl) watchingIds.add(auctionId); else watchingIds.delete(auctionId);
        btn.style.transform = 'scale(1.35)';
        setTimeout(() => { btn.style.transform = ''; }, 200);
      }
    } catch(err) { console.warn('wishlist err', err); }
  };

  function auctionCard(a) {
    const img  = a.image_url || 'https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=600&auto=format&fit=crop&q=80';
    const isUpcoming = a.status === 'upcoming';
    const isEnded    = a.status === 'ended';
    const urg  = isUpcoming ? '' : urgencyClass(a.ends_at);
    const icon = urg === 'colored' ? 'alarm' : 'schedule';
    const timerLabel = isUpcoming
      ? '⏳ Starts ' + formatCountdown(a.ends_at)
      : isEnded ? '🏁 Ended' : formatCountdown(a.ends_at);
    const badgeBg = isUpcoming ? 'background:rgba(245,158,11,.15);border-color:rgba(245,158,11,.5);color:#f59e0b;'
                  : isEnded   ? 'background:rgba(255,110,132,.1);border-color:rgba(255,110,132,.3);color:#ff6e84;' : '';
    const bidBtn = isUpcoming
      ? `<button class="btn-bid" style="opacity:.55;cursor:not-allowed;font-size:.75rem;" disabled>⏳ Upcoming</button>`
      : isEnded
      ? `<button class="btn-bid" style="opacity:.55;cursor:not-allowed;font-size:.75rem;" disabled>🏁 Ended</button>`
      : `<button class="btn-bid" onclick="event.stopPropagation();window.location.href='/auction/${a.id}'">Bid Now</button>`;
    const isWatching = watchingIds.has(a.id);
    return `
      <div class="auction-card" onclick="window.location.href='/auction/${a.id}'" style="cursor:pointer;">
        <div class="card-img-wrap" style="position:relative;">
          <img src="${img}" alt="${a.title}" loading="lazy"
               onerror="this.src='https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=600&auto=format&fit=crop&q=80'" />
          <div class="card-timer-badge ${urg}" style="${badgeBg}">
            <span class="material-symbols-outlined" style="font-size:.875rem;">${icon}</span>
            <span ${isUpcoming||isEnded ? '' : 'data-ends="'+a.ends_at+'"'}>${timerLabel}</span>
          </div>
          ${a.bid_count > 10 && !isEnded ? '<div style="position:absolute;top:.5rem;left:.5rem;background:rgba(200,153,255,.2);border:1px solid var(--primary);color:var(--primary);font-size:.65rem;font-weight:700;padding:.2rem .5rem;border-radius:.25rem;backdrop-filter:blur(4px);">&#128293; HOT</div>' : ''}
          <!-- Heart = add/remove from Wishlist -->
          <button class="heart-btn" data-auction-id="${a.id}" data-watching="${isWatching ? 'true' : 'false'}"
            onclick="toggleWatch(event,'${a.id}')" title="${isWatching ? 'Remove from Wishlist' : 'Add to Wishlist'}"
            style="position:absolute;bottom:.6rem;right:.6rem;background:rgba(14,14,14,.8);border:none;border-radius:50%;width:2.2rem;height:2.2rem;display:flex;align-items:center;justify-content:center;cursor:pointer;backdrop-filter:blur(8px);transition:transform .2s;z-index:10;">
            <span class="material-symbols-outlined" style="font-size:1.15rem;color:${isWatching ? '#ff6e84' : '#888'};">${isWatching ? 'favorite' : 'favorite_border'}</span>
          </button>
        </div>
        <div class="card-body">
          <p style="font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--primary);margin-bottom:.25rem;">${a.category || 'Uncategorized'}</p>
          <h3 class="card-title">${a.title}</h3>
          <div class="card-footer">
            <div>
              <p class="bid-label">${isEnded ? 'Final Bid' : 'Current Bid'}</p>
              <p class="bid-amount">${inr(a.current_bid)}</p>
            </div>
            ${bidBtn}
          </div>
        </div>
      </div>`;
  }

  /* ── Horizontal scroll section ── */
  function renderSection(containerId, auctions, emptyMsg) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!auctions || !auctions.length) {
      el.innerHTML = `<p style="color:var(--on-surface-variant);font-size:.875rem;padding:.5rem 0;">${emptyMsg}</p>`;
      return;
    }
    el.innerHTML = auctions.map(auctionCard).join('');
    el.querySelectorAll('[data-ends]').forEach(span => {
      setInterval(() => { span.textContent = formatCountdown(span.dataset.ends); }, 1000);
    });
  }

  /* ── Hero carousel ── */
  function buildHeroItem(a) {
    const img = a.image_url || 'https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=1200&auto=format&fit=crop&q=60';
    const heroImg = document.getElementById('heroImg');
    if (heroImg) heroImg.src = img;
    const t = document.getElementById('heroTitle');   if (t) t.textContent = a.title;
    const d = document.getElementById('heroDesc');    if (d) d.textContent = a.description || '';
    const b = document.getElementById('heroBid');     if (b) b.textContent = inr(a.current_bid);
    const btn = document.getElementById('heroBidBtn');if (btn) btn.onclick = () => window.location.href = '/auction/' + a.id;
  }

  function startHeroCarousel(auctions) {
    if (!auctions.length) return;
    heroAuctions = auctions;
    heroIdx = 0;
    buildHeroItem(heroAuctions[0]);

    function tickHero() {
      const el = document.getElementById('heroTimer');
      if (el && heroAuctions[heroIdx]) el.textContent = 'Ends in ' + formatCountdown(heroAuctions[heroIdx].ends_at);
    }
    tickHero();
    setInterval(tickHero, 1000);

    if (heroInterval) clearInterval(heroInterval);
    heroInterval = setInterval(() => {
      heroIdx = (heroIdx + 1) % heroAuctions.length;
      buildHeroItem(heroAuctions[heroIdx]);
    }, 6000);

    const dots = document.getElementById('heroDots');
    if (dots) {
      dots.innerHTML = heroAuctions.map((_, i) =>
        `<span class="hero-dot${i===0?' active':''}" onclick="goHero(${i})"></span>`
      ).join('');
    }
    window.goHero = function(i) {
      heroIdx = i;
      buildHeroItem(heroAuctions[i]);
      clearInterval(heroInterval);
      heroInterval = setInterval(() => { heroIdx=(heroIdx+1)%heroAuctions.length; buildHeroItem(heroAuctions[heroIdx]); }, 6000);
      document.querySelectorAll('.hero-dot').forEach((d,j)=>d.classList.toggle('active',j===i));
    };
  }

  /* ── Main grid fetch ── */
  async function fetchAndRender(reset = false) {
    if (reset) { skip = 0; document.getElementById('auctionGrid').innerHTML = ''; }
    const params = new URLSearchParams({ status: 'active', limit: 12, skip, sort: activeSort });
    if (activeFilter !== 'all') params.set('category', activeFilter);
    if (searchQ)               params.set('q', searchQ);
    const res  = await fetch(API + '/api/auctions/?' + params, { credentials: 'include' });
    if (!res.ok) return [];
    const data = await res.json();
    return data.auctions || [];
  }

  function appendCards(auctions) {
    const grid = document.getElementById('auctionGrid');
    if (!grid) return;
    // Clear skeleton placeholders on first load
    if (skip === 0) grid.innerHTML = '';
    if (!auctions.length && skip === 0) {
      grid.innerHTML = `<p style="color:var(--on-surface-variant);grid-column:1/-1;text-align:center;padding:3rem 0;">
        No auctions found. <a href="/create" style="color:var(--primary);">Create one!</a></p>`;
      return;
    }
    auctions.forEach(a => {
      grid.insertAdjacentHTML('beforeend', auctionCard(a));
    });
    grid.querySelectorAll('[data-ends]').forEach(span => {
      if (!span.dataset._wired) {
        span.dataset._wired = '1';
        setInterval(() => { span.textContent = formatCountdown(span.dataset.ends); }, 1000);
      }
    });
  }

  /* ── Init – fetch everything in parallel for speed ── */
  async function init() {
    // Read search from URL early
    const urlQ = new URLSearchParams(window.location.search).get('q');
    if (urlQ) {
      searchQ = urlQ;
      const inp = document.querySelector('.nav-search input');
      if (inp) inp.value = urlQ;
    }

    // ── 1. Auth guard — use nav.js sessionStorage cache if available ──
    try {
      if (window.FLEXY_USER) {
        currentUser = window.FLEXY_USER;
      } else if (window.FLEXY_GET_ME) {
        currentUser = await window.FLEXY_GET_ME();
        if (!currentUser) { window.location.href = '/login'; return; }
      } else {
        const res = await fetch('/api/auth/me', { credentials: 'include' });
        if (!res.ok) { window.location.href = '/login'; return; }
        currentUser = (await res.json()).user;
      }
    } catch { window.location.href = '/login'; return; }

    // ── 2. Fire all data requests IN PARALLEL ──
    const [wlRes, sectionsRes, catsRes, mainAuctions] = await Promise.allSettled([
      fetch('/api/watchlist/', { credentials: 'include' }),
      fetch(API + '/api/auctions/sections', { credentials: 'include' }),
      fetch(API + '/api/auctions/categories', { credentials: 'include' }),
      fetchAndRender(true),
    ]);

    // Watchlist ids
    if (wlRes.status === 'fulfilled' && wlRes.value.ok) {
      try {
        const wlData = await wlRes.value.json();
        watchingIds = new Set((wlData.watchlist || []).map(a => a.id));
      } catch(e) { console.warn('watchlist parse err', e); }
    }

    // Sections (Live Now, Upcoming, Popular, Ended)
    if (sectionsRes.status === 'fulfilled' && sectionsRes.value.ok) {
      try {
        const data = await sectionsRes.value.json();
        startHeroCarousel([...(data.live_now || []), ...(data.featured || [])].slice(0, 5));
        renderSection('liveNowRow',    data.live_now,   'No auctions live right now.');
        renderSection('upcomingRow',   data.upcoming,   'No upcoming auctions.');
        renderSection('popularRow',    data.popular,    'Be the first to bid!');
        renderSection('endingSoonRow', data.ended,      'No ended auctions yet.');
      } catch(e) { console.error('Sections error', e); }
    }

    // Categories pills
    if (catsRes.status === 'fulfilled' && catsRes.value.ok) {
      try {
        const data = await catsRes.value.json();
        const myCatsRow = document.getElementById('myCatsRow');
        if (myCatsRow && data.categories) {
          myCatsRow.innerHTML = data.categories.map(c => `
            <div class="cat-pill" onclick="filterByCategory('${c.name}')" style="cursor:pointer;background:var(--surface-container);border:1px solid var(--outline-variant);border-radius:3rem;padding:.6rem 1.25rem;display:inline-flex;align-items:center;gap:.5rem;white-space:nowrap;transition:.2s;user-select:none;" onmouseenter="this.style.borderColor='var(--primary)'" onmouseleave="this.style.borderColor='var(--outline-variant)'">
              <span style="font-size:.8rem;font-weight:700;color:var(--primary);">${c.name}</span>
              <span style="font-size:.7rem;color:var(--on-surface-variant);">${c.count}</span>
            </div>`).join('');
        }
      } catch (_) {}
    }

    // Main grid
    const auctions = mainAuctions.status === 'fulfilled' ? mainAuctions.value : [];
    appendCards(auctions);
    skip += auctions.length;

    // Sort
    const sortSel = document.querySelector('.sort-select');
    if (sortSel) {
      sortSel.addEventListener('change', async () => {
        const map = {'Ending Soonest':'ends_at','Highest Bid':'bid_high','Newest':'newest','Most Popular':'popular'};
        activeSort = map[sortSel.value] || 'ends_at';
        const rows = await fetchAndRender(true);
        appendCards(rows);
        skip += rows.length;
      });
    }

    // Filter pills
    document.querySelectorAll('.pill').forEach(pill => {
      pill.addEventListener('click', async () => {
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeFilter = pill.textContent.trim() === 'All Items' ? 'all' : pill.textContent.trim();
        const rows = await fetchAndRender(true);
        appendCards(rows);
        skip += rows.length;
      });
    });

    // Load more
    const loadMore = document.getElementById('loadMoreBtn');
    if (loadMore) {
      loadMore.addEventListener('click', async () => {
        loadMore.disabled = true;
        loadMore.textContent = 'Loading...';
        const more = await fetchAndRender(false);
        appendCards(more);
        skip += more.length;
        if (more.length < 12) {
          loadMore.textContent = 'All auctions loaded';
        } else {
          loadMore.innerHTML = 'Show more <span class="material-symbols-outlined">expand_more</span>';
          loadMore.disabled = false;
        }
      });
    }
  }

  window.filterByCategory = async function(cat) {
    activeFilter = cat;
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    const rows = await fetchAndRender(true);
    appendCards(rows);
    skip += rows.length;
    document.getElementById('auctionGrid')?.scrollIntoView({ behavior: 'smooth' });
  };

  document.addEventListener('DOMContentLoaded', init);

  // Global countdown ticker (single interval, efficient)
  setInterval(function () {
    document.querySelectorAll('[data-ends]').forEach(function (el) {
      el.textContent = formatCountdown(el.dataset.ends);
    });
  }, 1000);
})();