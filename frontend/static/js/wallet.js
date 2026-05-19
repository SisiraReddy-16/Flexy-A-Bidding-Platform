/* ============================================================
   FLEXY - Wallet & Profile Page JS (wallet.js)
   ============================================================ */

(async function () {
  'use strict';

  // 1. Fetch User Profile
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    if (!res.ok) { window.location.href = '/login'; return; }
    const data = await res.json();
    const user = data.user;

    document.getElementById('profileName').textContent = user.username;
    document.getElementById('profileBio').textContent = user.bio || 'Curating high-velocity digital assets.';
    document.getElementById('profileLocation').textContent = user.location || 'Unknown location';
    if (user.avatar_url) {
      document.getElementById('profileAvatar').src = user.avatar_url;
      const topNavImg = document.querySelector('.nav-avatar img');
      if (topNavImg) topNavImg.src = user.avatar_url;
    }
    const joinedDate = new Date(user.created_at);
    document.getElementById('profileJoined').textContent = `Joined ${joinedDate.toLocaleString('default', {month:'short'})} ${joinedDate.getFullYear()}`;
    
  } catch (e) {
    console.error('Failed to load profile', e);
  }

  // 2. Fetch User Stats
  try {
    const res = await fetch('/api/user/stats', { credentials: 'include' });
    if (res.ok) {
      const stats = await res.json();
      document.getElementById('statsWins').textContent = stats.items_won;
      document.getElementById('statsActiveBids').textContent = stats.active_bids;
      document.getElementById('statsValuation').textContent = `₹${Math.floor(stats.total_valuation_inr).toLocaleString('en-IN')}`;
    }
  } catch (e) {
    console.error('Failed to load stats', e);
  }

  // 3. Fetch Wallet Balance
  try {
    const res = await fetch('/api/wallet/balance', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      document.getElementById('walletBalance').textContent = `₹${data.balance_inr.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    }
  } catch(e) { console.error('Failed to load balance', e); }

  // 4. Fetch Transactions
  async function loadTransactions() {
    try {
      const res = await fetch('/api/wallet/transactions?limit=15', { credentials: 'include' });
      if (!res.ok) return;
      const data = await res.json();
      
      const txList = document.getElementById('txList');
      txList.innerHTML = '';

      if (!data.transactions || data.transactions.length === 0) {
        txList.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem 0;">No transactions yet.</p>';
        return;
      }

      data.transactions.forEach(tx => {
        let iconClass = 'deposit';
        let iconSymbol = 'account_balance';
        let amountClass = 'positive';
        let statusClass = 'completed';
        let amountStr = `+₹${tx.amount_inr.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        
        if (tx.type === 'withdraw' || tx.type === 'bid') {
          iconClass = 'win';
          iconSymbol = 'gavel';
          amountClass = 'negative';
          statusClass = 'settled';
          amountStr = `-₹${tx.amount_inr.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        }
        
        const txDate = new Date(tx.created_at);
        const dateStr = txDate.toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'}) + ' • ' + txDate.toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});

        const html = `
          <div class="tx-item">
            <div class="tx-item-left">
              <div class="tx-icon ${iconClass}">
                <span class="material-symbols-outlined">${iconSymbol}</span>
              </div>
              <div>
                <p class="tx-name">${tx.type.charAt(0).toUpperCase() + tx.type.slice(1)}: ${tx.note || 'Transfer'}</p>
                <p class="tx-date">${dateStr}</p>
              </div>
            </div>
            <div class="tx-item-right">
              <p class="tx-amount ${amountClass === 'positive' ? 'positive' : ''}" style="${amountClass !== 'positive' ? 'color:#fff;' : ''}">${amountStr}</p>
              <span class="tx-status ${statusClass}">
                <span class="status-dot"></span> ${(tx.type==='bid') ? 'Settled' : 'Completed'}
              </span>
            </div>
          </div>
        `;
        txList.insertAdjacentHTML('beforeend', html);
      });

    } catch(e) { console.error('Failed to load txs', e); }
  }
  loadTransactions();

  // Add Funds via Razorpay
  const depositBtn = document.getElementById('addFundsBtn');
  if (depositBtn) {
    depositBtn.addEventListener('click', function() {
      openAddMoneyModal();
    });
  }

  // ── Add Money Modal ──────────────────────────────────────────
  function openAddMoneyModal() {
    // Remove existing modal if any
    const existing = document.getElementById('addMoneyModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'addMoneyModal';
    modal.style.cssText = `position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.75);
      display:flex;align-items:center;justify-content:center;padding:1rem;backdrop-filter:blur(4px);`;
    modal.innerHTML = `
      <div style="background:#141414;border:1px solid #2a2a2a;border-radius:1.5rem;
                  width:100%;max-width:440px;padding:2rem;position:relative;">
        <button onclick="document.getElementById('addMoneyModal').remove()"
          style="position:absolute;top:1rem;right:1rem;background:none;border:none;
                 color:#666;font-size:1.5rem;cursor:pointer;line-height:1;">&#x2715;</button>
        <h3 style="font-family:var(--font-headline);font-size:1.25rem;font-weight:800;
                   margin:0 0 .25rem;color:#fff;">Add Money to Wallet</h3>
        <p style="color:#888;font-size:.85rem;margin:0 0 1.5rem;">
          Secure payment via UPI, Cards, or Net Banking
        </p>

        <!-- Quick amounts -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem;margin-bottom:1rem;">
          ${[500,1000,2000,5000].map(v=>`
            <button onclick="document.getElementById('addMoneyAmt').value=${v}"
              style="background:rgba(200,153,255,.1);border:1px solid rgba(200,153,255,.3);
                     color:#c899ff;border-radius:.5rem;padding:.5rem;font-size:.85rem;
                     font-weight:700;cursor:pointer;">&#8377;${v.toLocaleString('en-IN')}</button>
          `).join('')}
        </div>

        <!-- Custom amount -->
        <div style="margin-bottom:1.25rem;">
          <label style="display:block;font-size:.8rem;color:#888;margin-bottom:.4rem;">
            Enter Amount (&#8377;)
          </label>
          <input id="addMoneyAmt" type="number" min="100" max="100000"
            placeholder="e.g. 1500"
            style="width:100%;box-sizing:border-box;background:#0e0e0e;border:1px solid #2a2a2a;
                   border-radius:.75rem;padding:.875rem 1rem;color:#fff;font-size:1rem;outline:none;"/>
        </div>

        <div id="addMoneyAlert" style="display:none;padding:.75rem 1rem;border-radius:.5rem;
             font-size:.85rem;margin-bottom:1rem;"></div>

        <button id="addMoneyPayBtn"
          style="width:100%;background:linear-gradient(135deg,#3a7bfd,#1a4fbf);
                 color:#fff;border:none;border-radius:.75rem;padding:1rem;
                 font-family:var(--font-headline);font-size:1rem;font-weight:800;
                 cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.5rem;">
          <span>&#128274;</span> Pay via Razorpay
        </button>
        <p style="text-align:center;color:#444;font-size:.72rem;margin:.75rem 0 0;">
          UPI &nbsp;|&nbsp; Cards &nbsp;|&nbsp; Net Banking &nbsp;|&nbsp; Wallets
        </p>
      </div>`;
    document.body.appendChild(modal);

    document.getElementById('addMoneyPayBtn').addEventListener('click', async function() {
      const amtInr = parseFloat(document.getElementById('addMoneyAmt').value);
      if (!amtInr || amtInr < 100) {
        showModalAlert('Minimum deposit is &#8377;100', true); return;
      }
      if (amtInr > 100000) {
        showModalAlert('Maximum single deposit is &#8377;1,00,000', true); return;
      }
      const amtPaise = Math.round(amtInr * 100);
      this.textContent = 'Creating order…'; this.disabled = true;

      try {
        const orderRes  = await fetch('/api/wallet/razorpay/order', {
          method: 'POST', credentials: 'include',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({amount: amtPaise})
        });
        const orderData = await orderRes.json();
        if (!orderRes.ok) { showModalAlert(orderData.error || 'Failed to create order', true); return; }

        if (orderData.sandbox) {
          // Sandbox mode – simulate payment success
          showModalAlert('Sandbox mode: simulating payment…', false);
          await new Promise(r => setTimeout(r, 1200));
          await verifyAndCredit(orderData.order_id, 'pay_sandbox_' + Date.now(), 'sig_sandbox', amtPaise);
          return;
        }

        // Load Razorpay checkout script if not loaded
        if (!window.Razorpay) {
          await loadScript('https://checkout.razorpay.com/v1/checkout.js');
        }

        const options = {
          key:         orderData.key,
          amount:      amtPaise,
          currency:    'INR',
          name:        'Flexy',
          description: 'Wallet Top-Up',
          order_id:    orderData.order_id,
          prefill:     { name: '', email: '', contact: '' },
          theme:       { color: '#c899ff' },
          handler: async function(response) {
            await verifyAndCredit(
              response.razorpay_order_id,
              response.razorpay_payment_id,
              response.razorpay_signature,
              amtPaise
            );
          },
          modal: { ondismiss: function() {
            document.getElementById('addMoneyPayBtn').textContent = 'Pay via Razorpay';
            document.getElementById('addMoneyPayBtn').disabled = false;
          }}
        };
        const rzp = new window.Razorpay(options);
        rzp.open();

      } catch(err) {
        showModalAlert('Network error: ' + err.message, true);
        this.textContent = 'Pay via Razorpay'; this.disabled = false;
      }
    });
  }

  async function verifyAndCredit(orderId, paymentId, signature, amtPaise) {
    const res = await fetch('/api/wallet/razorpay/verify', {
      method: 'POST', credentials: 'include',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        razorpay_order_id:   orderId,
        razorpay_payment_id: paymentId,
        razorpay_signature:  signature,
        amount:              amtPaise,
      })
    });
    const data = await res.json();
    if (res.ok) {
      document.getElementById('addMoneyModal').remove();
      // Update balance in UI
      const balEl = document.getElementById('walletBalance');
      if (balEl && data.balance_paise !== undefined) {
        balEl.textContent = '\u20b9' + (data.balance_paise/100).toLocaleString('en-IN',{minimumFractionDigits:2});
      }
      showToast('\u20b9' + (amtPaise/100).toLocaleString('en-IN') + ' added to your wallet!');
      setTimeout(() => location.reload(), 1500);
    } else {
      showModalAlert(data.error || 'Payment verification failed', true);
    }
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.onload = resolve; s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  function showModalAlert(msg, isErr) {
    const el = document.getElementById('addMoneyAlert');
    if (!el) return;
    el.innerHTML = msg; el.style.display = 'block';
    el.style.background = isErr ? 'rgba(255,110,132,.12)' : 'rgba(0,200,100,.1)';
    el.style.color       = isErr ? '#ff6e84' : '#00c864';
    el.style.border      = isErr ? '1px solid rgba(255,110,132,.3)' : '1px solid rgba(0,200,100,.3)';
  }

  function showToast(msg) {
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;bottom:5rem;left:50%;transform:translateX(-50%);
      background:#1e0a3c;border:1px solid #c899ff;color:#c899ff;padding:.75rem 1.5rem;
      border-radius:2rem;font-weight:700;font-size:.9rem;z-index:9999;
      animation:fadeIn .3s ease;`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }
  
  // Withdraw handler
  const withdrawBtn = document.getElementById('withdrawBtn');
  if (withdrawBtn) {
    withdrawBtn.addEventListener('click', async function() {
      const amt = prompt('Enter withdraw amount in ₹:');
      if (!amt || isNaN(amt)) return;
      const res = await fetch('/api/wallet/withdraw', {
        method: 'POST', credentials: 'include',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ amount: Math.round(parseFloat(amt) * 100) })
      });
      const data = await res.json();
      alert(data.message || data.error);
      if (res.ok) location.reload();
    });
  }

})();
