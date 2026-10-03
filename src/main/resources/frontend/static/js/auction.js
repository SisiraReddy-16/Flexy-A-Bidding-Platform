/* ============================================================
   FLEXY - Auction Detail Page JS (auction.js)
   Static helpers only – all real-time logic is in the
   inline <script> block of auction.html (Socket.IO).
   ============================================================ */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    /* ── Thumbnail image switching ── */
    document.querySelectorAll('.thumb').forEach(function (thumb) {
      thumb.addEventListener('click', function () {
        var thumbImg  = thumb.querySelector('img');
        var mainImg   = document.getElementById('mainProductImg');
        if (thumbImg && mainImg) {
          mainImg.src = thumbImg.src;
        }
      });
    });

    /* ── View All Bids button ── */
    var viewAllBtn = document.getElementById('viewAllBids');
    if (viewAllBtn) {
      viewAllBtn.addEventListener('click', function () {
        // Scroll bid history into view
        var historyEl = document.getElementById('bidHistoryList');
        if (historyEl) historyEl.scrollIntoView({ behavior: 'smooth' });
      });
    }

    /* ── Share / Favourite buttons ── */
    var shareBtn = document.querySelector('.product-action-btn.share');
    if (shareBtn) {
      shareBtn.addEventListener('click', function () {
        if (navigator.share) {
          navigator.share({ title: document.title, url: window.location.href });
        } else {
          navigator.clipboard.writeText(window.location.href)
            .then(function () { alert('Link copied to clipboard!'); });
        }
      });
    }

    /* ── NOTE: Timer, bid history, and place-bid are all handled
       by the Socket.IO inline script block in auction.html ── */

  });
})();
