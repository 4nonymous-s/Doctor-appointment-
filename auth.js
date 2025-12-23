/* auth.js
   Handles login/register modal and updates the account panel on success.
*/
(function(){
  const $ = id => document.getElementById(id);
  const loginModal = $('loginModal');
  const loginModalClose = $('loginModalClose');
  const loginButton = $('loginButton');
  const registerButton = $('registerButton');
  const loginNotif = $('loginNotif');
  const loginForm = $('loginForm');
  const usernameInput = $('login-username');
  const passwordInput = $('login-password');
  const openLoginBtn = document.getElementById('openLogin');
  let lastFocused = null;

  function openLoginModal(){
    lastFocused = document.activeElement;
    loginModal.setAttribute('aria-hidden','false');
    loginModal.classList.add('open');
    loginNotif.hidden = true;
    setTimeout(()=>{ usernameInput.focus(); }, 80);
    document.addEventListener('keydown', trap);
  }

  function closeLoginModal(){
    loginModal.setAttribute('aria-hidden','true');
    loginModal.classList.remove('open');
    document.removeEventListener('keydown', trap);
    if(lastFocused && lastFocused.focus) lastFocused.focus();
  }

  function trap(e){ if(e.key==='Escape') closeLoginModal(); }

  async function doAuth(action){
    const user = usernameInput.value.trim();
    const pass = passwordInput.value;
    if(!user || !pass){ loginNotif.hidden=false; loginNotif.textContent='Enter username and password'; loginNotif.className='notification error'; return }
    try{
      loginButton.disabled = registerButton.disabled = true;
      loginNotif.hidden=false; loginNotif.textContent = (action==='login' ? 'Signing in…' : 'Registering…'); loginNotif.className='notification info';
      const resp = await fetch(action==='login'?'/api/login':'/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pass,full_name:user})});
      const data = await resp.json();
        if(resp.ok){
          loginNotif.className='notification success';
          loginNotif.textContent = (action==='login'?'Signed in':'Registered') + ' — ' + (data.username||data.user||'');
          // store current user id globally so other scripts (booking) can include it
          if(data.user_id) window.currentUserId = data.user_id;
          else if(data.id) window.currentUserId = data.id;
          // persist to localStorage so navigation (Home) doesn't drop the login
          try{
            if(window.currentUserId) localStorage.setItem('currentUserId', window.currentUserId);
            if(data.username) localStorage.setItem('currentUsername', data.username);
          }catch(e){}
          updateAccountUI(data);
          setTimeout(closeLoginModal,800);
        }
      else { loginNotif.className='notification error'; loginNotif.textContent = data.error || JSON.stringify(data); }
    }catch(err){ loginNotif.className='notification error'; loginNotif.textContent = err.message || 'Auth failed'; }
    finally{ loginButton.disabled = registerButton.disabled = false; }
  }

  function updateAccountUI(user){
    const panel = document.querySelector('.account-panel');
    if(!panel) return;
    const uid = user.user_id || user.id || null;

    panel.innerHTML = `
      <h3 id="account-heading">Account</h3>
      <div class="account-box">
        <div>Welcome <strong>${user.username || user.user || user.full_name || 'user'}</strong></div>
        <div id="accountBookings" style="margin-top:8px">Loading bookings…</div>
        <div style="margin-top:8px"><button id="logoutBtn" class="btn ghost">Logout</button></div>
      </div>
    `;

    const bookingsEl = document.getElementById('accountBookings');

    async function renderBookingsFor(uid){
      if(!uid){ bookingsEl.innerHTML = '<div class="muted">Sign in to see your bookings.</div>'; return }
      try{
        const resp = await fetch('/api/history/' + encodeURIComponent(uid));
        if(!resp.ok){ bookingsEl.innerHTML = '<div class="muted">No bookings or failed to load.</div>'; return }
        const data = await resp.json();
        if(!Array.isArray(data) || data.length===0){ bookingsEl.innerHTML = '<div class="empty">No bookings found.</div>'; return }
        bookingsEl.innerHTML = '<div style="display:flex;gap:8px;align-items:center;justify-content:space-between;margin-bottom:6px"><div style="font-weight:700">Your bookings</div><div><button id="clearHistoryBtn" class="btn ghost" style="padding:6px 10px">Clear history</button></div></div>' + '<ul id="bookingsList" class="bookings-list" style="list-style:none;padding:0;margin:0">' + data.map(b=>{
          const canCancel = String(b.status || '').toLowerCase() === 'booked';
          return `<li style="border-bottom:1px solid #eee;padding:8px 0;display:flex;justify-content:space-between;align-items:center"><div><div><strong>${b.doctor || '—'}</strong> · ${b.hospital || '—'}</div><div class="muted small">${b.scheduled_at || ''} — ${b.status || ''}</div></div><div>${canCancel ? `<button class="btn ghost cancel-booking" data-appt-id="${b.id}" style="padding:6px 10px">Cancel</button>` : ''}</div></li>`
        }).join('') + '</ul>';
        // wire clear history button
        const clearBtn = document.getElementById('clearHistoryBtn');
        if(clearBtn){
          clearBtn.addEventListener('click', async function(){
            if(!confirm('Clear all your booking history? This cannot be undone.')) return;
            try{
              clearBtn.disabled = true;
              const resp = await fetch('/api/history/' + encodeURIComponent(effectiveUid) + '/clear', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({user_id: effectiveUid})});
              const res = await resp.json();
              if(resp.ok){
                renderBookingsFor(effectiveUid);
              } else {
                alert(res.error || JSON.stringify(res));
                clearBtn.disabled = false;
              }
            }catch(err){ alert(err.message || 'Clear failed'); clearBtn.disabled = false; }
          });
        }

        // delegate cancel clicks
        const bookingsList = document.getElementById('bookingsList');
        if(bookingsList){
          bookingsList.addEventListener('click', async (e)=>{
            const btn = e.target.closest && e.target.closest('.cancel-booking');
            if(!btn) return;
            const apptId = btn.getAttribute('data-appt-id');
            if(!apptId) return;
            if(!confirm('Cancel this booking?')) return;
            try{
              btn.disabled = true;
              const resp = await fetch('/api/appointment/' + encodeURIComponent(apptId) + '/cancel', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({user_id: effectiveUid})});
              const res = await resp.json();
              if(resp.ok){
                // refresh bookings
                renderBookingsFor(effectiveUid);
              } else {
                alert(res.error || JSON.stringify(res));
                btn.disabled = false;
              }
            }catch(err){ alert(err.message || 'Cancel failed'); btn.disabled = false; }
          });
        }
      }catch(e){ bookingsEl.innerHTML = '<div class="muted">Failed to load bookings.</div>'; }
    }

    // try to render bookings for provided uid or stored id
    const effectiveUid = uid || window.currentUserId || localStorage.getItem('currentUserId');
    renderBookingsFor(effectiveUid);

    // If we have a UID, update header login button to point to user dashboard
    const openLoginBtn = document.getElementById('openLogin');
    if(openLoginBtn){
      if(effectiveUid){
        openLoginBtn.textContent = 'Dashboard';
        openLoginBtn.onclick = function(e){ e.preventDefault(); window.location.href = '/dashboard?user_id=' + encodeURIComponent(effectiveUid); };
      } else {
        openLoginBtn.textContent = 'Login';
        openLoginBtn.onclick = openLoginModal;
      }
    }

    const logout = document.getElementById('logoutBtn');
    logout.addEventListener('click', async ()=>{
      try{ await fetch('/api/logout',{method:'POST'}); }catch(e){}
      panel.innerHTML = `<h3 id="account-heading">Account (Fallback)</h3><div class="account-box"><p>Use the React app for full account features.</p><small class="muted">This fallback UI supports search and viewing doctors.</small></div>`;
      // restore header login button behavior
      const openLoginBtn = document.getElementById('openLogin');
      if(openLoginBtn){
        openLoginBtn.textContent = 'Login';
        openLoginBtn.onclick = openLoginModal;
      }
      try{ window.currentUserId = null; delete window.currentUserId; localStorage.removeItem('currentUserId'); localStorage.removeItem('currentUsername'); }catch(e){}
    });
  }

  loginModalClose.addEventListener('click', closeLoginModal);
  if(openLoginBtn) openLoginBtn.addEventListener('click', openLoginModal);
  loginButton.addEventListener('click', ()=>doAuth('login'));
  registerButton.addEventListener('click', ()=>doAuth('register'));

  // Theme toggle: restore saved theme and wire toggle button
  (function(){
    const themeToggle = document.getElementById('themeToggle');
    function applyTheme(t){
      try{
        if(t === 'dark') document.documentElement.setAttribute('data-theme','dark');
        else document.documentElement.removeAttribute('data-theme');
        if(themeToggle){
          themeToggle.setAttribute('aria-pressed', t==='dark' ? 'true' : 'false');
          themeToggle.textContent = t==='dark' ? '☀️' : '🌙';
        }
      }catch(e){}
    }
    try{
      const savedTheme = localStorage.getItem('theme') || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      applyTheme(savedTheme);
    }catch(e){ applyTheme('light'); }
    if(themeToggle){
      themeToggle.addEventListener('click', function(){
        const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        const next = cur === 'dark' ? 'light' : 'dark';
        try{ localStorage.setItem('theme', next); }catch(e){}
        applyTheme(next);
      });
    }
  })();

  // Restore saved user (if any) and adjust UI once on load (avoid recursion)
  (function(){
    try{
      const saved = localStorage.getItem('currentUserId');
      const savedName = localStorage.getItem('currentUsername');
      if(saved){
        window.currentUserId = saved;
        const u = { user_id: saved, username: savedName };
        updateAccountUI(u);
      }
    }catch(e){}
  })();

  // expose for manual open
  window.openLoginModal = openLoginModal;
})();
