/* ============================================================
   FLEXY - Login Page JS (login.js)
   UI helpers only – API calls handled in login.html inline script.
   ============================================================ */

(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.form-input').forEach(function (input) {
      input.addEventListener('focus', function () {
        input.style.boxShadow = '';
        var parent = input.closest('.form-group');
        if (parent) { var e = parent.querySelector('.field-error-msg'); if (e) e.remove(); }
      });
    });
  });
})();
