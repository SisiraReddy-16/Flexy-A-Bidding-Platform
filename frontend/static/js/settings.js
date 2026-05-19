/* ============================================================
   FLEXY – Settings Page JS
   Sections: Profile, Change Password, MFA Setup/Disable,
             Active Sessions, Account Info
   ============================================================ */
(async function () {
  'use strict';

  /* ── Helpers ── */
  function showMsg(id, msg, ok) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.className   = 'status-msg ' + (ok ? 'ok' : 'err');
    el.style.display = 'block';
    if (ok) setTimeout(() => { el.style.display = 'none'; }, 4000);
  }

  /* ── Load user data ── */
  let user = {};
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    if (!res.ok) { window.location.href = '/login'; return; }
    user = (await res.json()).user;
  } catch { window.location.href = '/login'; return; }

  /* ── Fill profile form ── */
  document.getElementById('avatar_url').value = user.avatar_url || '';
  document.getElementById('location').value   = user.location   || '';
  document.getElementById('bio').value         = user.bio        || '';

  /* ── Fill account info ── */
  document.getElementById('infoEmail').textContent     = user.email || '—';
  document.getElementById('infoUsername').textContent  = user.username || '—';
  document.getElementById('infoVerified').innerHTML    = user.is_email_verified
    ? '<span style="color:#4ade80;">✅ Verified</span>'
    : '<span style="color:#ff6e84;">❌ Not verified</span>';
  document.getElementById('infoRole').textContent      = user.role || 'user';
  if (user.created_at) {
    document.getElementById('infoJoined').textContent = new Date(user.created_at).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' });
  }
  if (user.last_login) {
    document.getElementById('infoLastLogin').textContent = new Date(user.last_login).toLocaleString('en-IN', { day:'numeric', month:'short', hour:'2-digit', minute:'2-digit' });
  }

  /* ── MFA state ── */
  function setMfaState(enabled) {
    const badge = document.getElementById('mfaBadge');
    if (enabled) {
      badge.className = 'mfa-badge on';
      badge.innerHTML = '<span class="material-symbols-outlined" style="font-size:.875rem;">lock</span> Enabled';
      document.getElementById('mfaSetupSection').style.display  = 'none';
      document.getElementById('mfaDisableSection').style.display = 'block';
    } else {
      badge.className = 'mfa-badge off';
      badge.innerHTML = '<span class="material-symbols-outlined" style="font-size:.875rem;">lock_open</span> Disabled';
      document.getElementById('mfaSetupSection').style.display  = 'block';
      document.getElementById('mfaDisableSection').style.display = 'none';
    }
  }
  setMfaState(user.mfa_enabled);

  /* ── 1. Profile form ── */
  document.getElementById('profileForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const updates = {
      avatar_url: document.getElementById('avatar_url').value.trim(),
      location:   document.getElementById('location').value.trim(),
      bio:        document.getElementById('bio').value.trim(),
    };
    try {
      const res  = await fetch('/api/user/profile', { method:'PUT', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify(updates) });
      const data = await res.json();
      if (res.ok) {
        showMsg('profileMsg', '✅ Profile updated!', true);
        // Update nav avatar if changed
        if (updates.avatar_url) document.querySelectorAll('.nav-avatar img').forEach(img => img.src = updates.avatar_url);
      } else {
        showMsg('profileMsg', data.error || 'Failed to update profile.', false);
      }
    } catch { showMsg('profileMsg', 'Network error. Please try again.', false); }
  });

  /* ── 2. Change password with inline strength ── */
  const cpwRules = {
    len:   { re: /.{8,}/, id: 'cpw-len'   },
    upper: { re: /[A-Z]/, id: 'cpw-upper' },
    lower: { re: /[a-z]/, id: 'cpw-lower' },
    digit: { re: /\d/,    id: 'cpw-digit' },
  };
  document.getElementById('newPass').addEventListener('input', function () {
    const pw = this.value;
    for (const [, rule] of Object.entries(cpwRules)) {
      const ok = rule.re.test(pw);
      const el = document.getElementById(rule.id);
      el.classList.toggle('ok', ok);
      el.querySelector('.material-symbols-outlined').textContent = ok ? 'check' : 'close';
    }
  });

  document.getElementById('changePassForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const currentPass    = document.getElementById('currentPass').value;
    const newPass        = document.getElementById('newPass').value;
    const confirmNewPass = document.getElementById('confirmNewPass').value;
    const btn            = document.getElementById('changePwBtn');

    if (newPass !== confirmNewPass) { showMsg('changePassMsg', 'New passwords do not match.', false); return; }
    btn.disabled = true; btn.textContent = 'Updating…';
    try {
      const res  = await fetch('/api/auth/change-password', { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ current_password: currentPass, new_password: newPass }) });
      const data = await res.json();
      if (res.ok) {
        showMsg('changePassMsg', '✅ ' + data.message, true);
        document.getElementById('changePassForm').reset();
        document.querySelectorAll('.pw-rule-s').forEach(el => { el.classList.remove('ok'); el.querySelector('.material-symbols-outlined').textContent='close'; });
      } else {
        showMsg('changePassMsg', data.error || 'Failed to change password.', false);
      }
    } catch { showMsg('changePassMsg', 'Network error.', false); }
    finally { btn.disabled=false; btn.textContent='Change Password'; }
  });

  /* ── 3. MFA Enable ── */
  let pendingMfaSecret = '';

  document.getElementById('setupMfaBtn').addEventListener('click', async function () {
    this.disabled = true; this.textContent = 'Generating…';
    try {
      const res  = await fetch('/api/auth/mfa/setup', { method:'POST', credentials:'include' });
      const data = await res.json();
      if (res.ok) {
        pendingMfaSecret = data.secret;
        document.getElementById('mfaQr').src     = 'data:image/png;base64,' + data.qr_code;
        document.getElementById('mfaSecret').textContent = data.secret;
        document.getElementById('mfaQrSection').style.display = 'block';
        document.getElementById('mfaCodeInput').focus();
      } else {
        showMsg('mfaSetupMsg', data.error || 'Failed to generate QR.', false);
      }
    } catch { showMsg('mfaSetupMsg', 'Network error.', false); }
    finally { this.disabled=false; this.textContent='Enable Two-Factor Auth'; }
  });

  document.getElementById('mfaCodeInput').addEventListener('input', function () {
    this.value = this.value.replace(/\D/g,'').slice(0,6);
  });

  document.getElementById('confirmMfaBtn').addEventListener('click', async function () {
    const code = document.getElementById('mfaCodeInput').value.trim();
    if (code.length !== 6) { showMsg('mfaSetupMsg', 'Enter a 6-digit code from your app.', false); return; }
    this.disabled = true; this.textContent = 'Verifying…';
    try {
      const res  = await fetch('/api/auth/mfa/verify', { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ secret: pendingMfaSecret, code }) });
      const data = await res.json();
      if (res.ok) {
        showMsg('mfaSetupMsg', '✅ ' + data.message, true);
        setTimeout(() => { setMfaState(true); document.getElementById('mfaQrSection').style.display='none'; }, 1200);
      } else {
        showMsg('mfaSetupMsg', data.error || 'Invalid code.', false);
      }
    } catch { showMsg('mfaSetupMsg', 'Network error.', false); }
    finally { this.disabled=false; this.textContent='Confirm & Enable'; }
  });

  /* ── 4. MFA Disable ── */
  document.getElementById('disableMfaCode').addEventListener('input', function () {
    this.value = this.value.replace(/\D/g,'').slice(0,6);
  });

  document.getElementById('disableMfaBtn').addEventListener('click', async function () {
    const code = document.getElementById('disableMfaCode').value.trim();
    if (code.length !== 6) { showMsg('mfaDisableMsg', 'Enter your 6-digit OTP.', false); return; }
    if (!confirm('Are you sure you want to disable two-factor authentication?')) return;
    this.disabled = true; this.textContent = 'Disabling…';
    try {
      const res  = await fetch('/api/auth/mfa/disable', { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ code }) });
      const data = await res.json();
      if (res.ok) {
        showMsg('mfaDisableMsg', '✅ ' + data.message, true);
        setTimeout(() => setMfaState(false), 1200);
      } else {
        showMsg('mfaDisableMsg', data.error || 'Failed to disable MFA.', false);
      }
    } catch { showMsg('mfaDisableMsg', 'Network error.', false); }
    finally { this.disabled=false; this.textContent='Disable 2FA'; }
  });

  /* ── 5. Sessions ── */
  async function loadSessions() {
    try {
      const res  = await fetch('/api/auth/sessions', { credentials:'include' });
      const data = await res.json();
      const list = document.getElementById('sessionsList');
      if (!data.sessions || !data.sessions.length) {
        list.innerHTML = '<p style="color:var(--on-surface-variant);font-size:.875rem;">No active sessions.</p>';
        return;
      }
      list.innerHTML = data.sessions.map(s => `
        <div class="session-item">
          <div>
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.2rem;">
              <span class="material-symbols-outlined" style="font-size:1rem;color:var(--on-surface-variant);">${s.user_agent.toLowerCase().includes('mobile')?'smartphone':'computer'}</span>
              <p style="font-size:.85rem;font-weight:600;">${s.ip}</p>
              ${s.current ? '<span class="session-current">Current</span>' : ''}
            </div>
            <p style="font-size:.75rem;color:var(--on-surface-variant);">${s.user_agent.slice(0,60)} • ${new Date(s.created_at).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</p>
          </div>
          ${!s.current ? `<button onclick="revokeSession('${s.id}', this)" style="background:transparent;border:1px solid var(--outline-variant);color:var(--error);padding:.35rem .75rem;border-radius:.4rem;cursor:pointer;font-size:.75rem;font-family:var(--font-body);">Revoke</button>` : ''}
        </div>`).join('');
    } catch (e) { document.getElementById('sessionsList').innerHTML = '<p style="color:var(--on-surface-variant);">Failed to load sessions.</p>'; }
  }
  loadSessions();

  window.revokeSession = async function (id, btn) {
    btn.disabled = true; btn.textContent = 'Revoking…';
    try {
      const res = await fetch('/api/auth/sessions/' + id, { method:'DELETE', credentials:'include' });
      if (res.ok) { btn.closest('.session-item').remove(); }
      else { btn.textContent = 'Failed'; btn.disabled = false; }
    } catch { btn.textContent = 'Error'; btn.disabled = false; }
  };

})();
