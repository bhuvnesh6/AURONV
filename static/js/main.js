/**
 * AURON — main.js  (full rewrite)
 * Covers every page: modals, toasts, forms, score ring,
 * progress bars, unread polling, PWA, avatar upload,
 * live client/trainer search, inbox, leaderboard DM.
 */
'use strict';

/* ── Utilities ─────────────────────────────────────────── */
const $ = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => [...c.querySelectorAll(s)];
const throttle = (fn, ms) => { let t = 0; return (...a) => { const n = Date.now(); if (n - t >= ms) { t = n; fn(...a); } }; };

/* ── Modal System ──────────────────────────────────────── */
const Modal = (() => {
  let stack = [];
  function open(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('open');
    stack.push(id);
    document.body.style.overflow = 'hidden';
    const first = el.querySelector('input:not([type=hidden]),select,textarea');
    if (first) setTimeout(() => first.focus(), 80);
  }
  function close(id) {
    if (!id && stack.length) { close(stack[stack.length - 1]); return; }
    const el = document.getElementById(id);
    if (el) el.classList.remove('open');
    stack = stack.filter(x => x !== id);
    if (!stack.length) document.body.style.overflow = '';
  }
  document.addEventListener('click', e => { if (e.target.classList.contains('modal')) close(e.target.id); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && stack.length) close(); });
  return { open, close };
})();

window.openModal  = id => Modal.open(id);
window.closeModal = id => Modal.close(id);

/* ── Toast ─────────────────────────────────────────────── */
function showToast(msg, type = 'info') {
  let c = document.getElementById('toastContainer');
  if (!c) { c = document.createElement('div'); c.id = 'toastContainer'; c.className = 'toast-container'; document.body.appendChild(c); }
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; setTimeout(() => t.remove(), 300); }, 3800);
}
window.showToast = showToast;

function initToasts() {
  $$('.toast').forEach((t, i) => {
    t.style.animationDelay = `${i * 80}ms`;
    setTimeout(() => { t.style.transition = 'opacity .3s,transform .3s'; t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; setTimeout(() => t.remove(), 320); }, 4000 + i * 400);
    t.addEventListener('click', () => t.remove());
  });
}

/* ── Form loading guard ────────────────────────────────── */
function initForms() {
  $$('form').forEach(form => {
    form.addEventListener('submit', function () {
      if (this.dataset.submitting) return;
      this.dataset.submitting = '1';
      const btn = this.querySelector('[type=submit]');
      if (btn) { const orig = btn.textContent; btn.disabled = true; btn.textContent = 'Saving…'; setTimeout(() => { btn.disabled = false; btn.textContent = orig; delete this.dataset.submitting; }, 8000); }
    });
  });
}

/* ── Score ring count-up ───────────────────────────────── */
function initScoreRing() {
  const arc = $('.score-ring circle:last-child');
  if (!arc) return;
  const target = parseFloat(arc.getAttribute('stroke-dasharray'));
  if (!target) return;
  arc.setAttribute('stroke-dasharray', '0 326.7');
  requestAnimationFrame(() => requestAnimationFrame(() => {
    arc.style.transition = 'stroke-dasharray 1s cubic-bezier(.4,0,.2,1)';
    arc.setAttribute('stroke-dasharray', `${target} 326.7`);
  }));
}

function initScoreCountUp() {
  const el = $('.score-number');
  if (!el) return;
  const target = parseInt(el.textContent, 10);
  if (isNaN(target)) return;
  let cur = 0;
  const step = Math.max(1, target / 40);
  el.textContent = '0';
  setTimeout(() => {
    const tick = () => { cur = Math.min(cur + step, target); el.textContent = Math.round(cur); if (cur < target) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }, 200);
}

/* ── Progress bars ─────────────────────────────────────── */
function initProgressBars() {
  const animate = bar => {
    const target = bar.style.width || '0%';
    bar.style.width = '0%';
    const obs = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) {
        requestAnimationFrame(() => { bar.style.transition = 'width .8s cubic-bezier(.4,0,.2,1)'; bar.style.width = target; });
        obs.unobserve(bar);
      }
    }, { threshold: 0.1 });
    obs.observe(bar);
  };
  $$('.progress-bar').forEach(animate);
  $$('.comp-bar div').forEach(animate);
}

/* ── Stat count-up ─────────────────────────────────────── */
function initStatCountUp() {
  $$('.stat-big').forEach(el => {
    const raw = el.textContent.trim().replace(/[^\d]/g, '');
    if (!raw) return;
    const target = parseInt(raw, 10);
    const suffix = el.textContent.trim().replace(/\d/g, '');
    if (!target) return;
    let cur = 0;
    const step = Math.max(1, Math.ceil(target / 30));
    el.textContent = '0' + suffix;
    const tick = () => { cur = Math.min(cur + step, target); el.textContent = cur + suffix; if (cur < target) requestAnimationFrame(tick); };
    setTimeout(() => requestAnimationFrame(tick), 100);
  });
}

/* ── Password toggle ───────────────────────────────────── */
function initPasswordToggle() {
  $$('input[type=password]').forEach(input => {
    const wrap = input.parentNode;
    if (!wrap.classList.contains('form-group')) return;
    wrap.style.position = 'relative';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.style.cssText = 'position:absolute;right:10px;top:50%;transform:translateY(-20%);background:none;border:none;cursor:pointer;color:var(--muted);padding:4px;display:flex;align-items:center;';
    btn.innerHTML = eyeSvg('closed');
    input.style.paddingRight = '2.5rem';
    wrap.appendChild(btn);
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = eyeSvg(show ? 'open' : 'closed');
    });
  });
}
function eyeSvg(s) {
  return s === 'open'
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
}

/* ── Avatar upload (profile pages) ────────────────────── */
function initAvatarUpload() {
  const input    = document.getElementById('avatarInput');
  const formFile = document.getElementById('avatarFormFile');
  const form     = document.getElementById('avatarForm');
  if (!input || !form) return;
  input.addEventListener('change', function () {
    const file = this.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { alert('Max 5 MB'); return; }
    const reader = new FileReader();
    reader.onload = e => {
      const img = document.getElementById('avatarImg');
      const ini = document.getElementById('avatarInitials');
      if (img) img.src = e.target.result;
      else if (ini) {
        const newImg = document.createElement('img');
        newImg.src = e.target.result; newImg.className = 'avatar-img'; newImg.id = 'avatarImg';
        ini.replaceWith(newImg);
      }
      document.getElementById('avatarRing')?.classList.add('avatar-uploading');
      const prog = document.getElementById('uploadProgress');
      if (prog) prog.style.display = 'flex';
    };
    reader.readAsDataURL(file);
    if (formFile) { const dt = new DataTransfer(); dt.items.add(file); formFile.files = dt.files; }
    form.submit();
  });
}

/* ── Photo preview (timeline) ──────────────────────────── */
function initPhotoPreview() {
  $$('input[type=file][accept*=image]').forEach(input => {
    if (input.id === 'avatarInput') return;
    input.addEventListener('change', function () {
      const file = this.files[0];
      if (!file) return;
      let preview = this.parentNode.querySelector('.photo-preview');
      if (!preview) {
        preview = document.createElement('img');
        preview.className = 'photo-preview';
        preview.style.cssText = 'display:block;width:100%;max-height:200px;object-fit:cover;border-radius:8px;margin-top:.75rem;border:1px solid var(--border)';
        this.parentNode.appendChild(preview);
      }
      const r = new FileReader();
      r.onload = e => { preview.src = e.target.result; };
      r.readAsDataURL(file);
    });
  });
}

/* ── Water button ripple ───────────────────────────────── */
function initWaterButtons() {
  $$('.quick-btns .btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const orig = this.textContent;
      this.textContent = '✓'; this.style.background = 'var(--success)'; this.style.color = '#000';
      setTimeout(() => { this.textContent = orig; this.style.background = ''; this.style.color = ''; }, 1200);
    });
  });
}

/* ── Trainer client live search (clients page) ────────── */
window.openAddEx = function (wid) {
  const inp = document.getElementById('addExWorkoutId');
  if (inp) inp.value = wid;
  Modal.open('addExModal');
};

/* ── Trainer message type toggle ───────────────────────── */
window.setMsgType = function (type, btn) {
  const inp = document.getElementById('msgType');
  if (inp) inp.value = type;
  $$('#newMsgModal .role-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const g = document.getElementById('recipientGroup');
  if (g) g.style.display = type === 'broadcast' ? 'none' : 'block';
};

/* ── Programs assign helper ────────────────────────────── */
window.openAssign = function (pid) {
  const form = document.getElementById('assignForm');
  if (form) form.action = `/trainer/programs/${pid}/assign`;
  const container = document.getElementById('clientCheckboxes');
  if (container) {
    const clients = window.clientData || [];
    container.innerHTML = clients.length
      ? clients.map(c => `<label class="checkbox-label"><input type="checkbox" name="client_ids" value="${c.id || c._id}" /> ${c.username}</label>`).join('')
      : '<p class="text-muted" style="font-size:.85rem">No clients yet.</p>';
  }
  Modal.open('assignModal');
};

/* ── Login role toggle ─────────────────────────────────── */
window.setRole = function (role) {
  const inp = document.getElementById('roleInput');
  if (inp) inp.value = role;
  $$('.role-btn[data-role]').forEach(b => b.classList.toggle('active', b.dataset.role === role));
};

/* ── Unread badge polling ──────────────────────────────── */
function initUnreadPolling() {
  const role = window.AURON_ROLE || '';

  async function pollUser() {
    try {
      const r = await fetch('/api/messages/unread');
      const d = await r.json();
      const count = d.count || 0;
      ['sidebarUnread','bnUnread'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = count > 9 ? '9+' : count;
        el.style.display = count > 0 ? '' : 'none';
      });
    } catch {}
  }

  async function pollTrainer() {
    try {
      const r = await fetch('/api/trainer/unread');
      const d = await r.json();
      const count = d.count || 0;
      ['trainerUnread','trainerBnBadge'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = count > 9 ? '9+' : count;
        el.style.display = count > 0 ? '' : 'none';
      });
    } catch {}
  }

  if (role === 'user')    { pollUser();    setInterval(pollUser,    45000); }
  if (role === 'trainer') { pollTrainer(); setInterval(pollTrainer, 45000); }
}

/* ── Timeline stagger ──────────────────────────────────── */
function initTimeline() {
  $$('.timeline-item').forEach((el, i) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(14px)';
    const obs = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) {
        setTimeout(() => { el.style.transition = 'opacity .4s ease,transform .4s ease'; el.style.opacity = '1'; el.style.transform = 'none'; }, i * 60);
        obs.unobserve(el);
      }
    }, { threshold: 0.05 });
    obs.observe(el);
  });
}

/* ── Leaderboard stagger ───────────────────────────────── */
function initLeaderboard() {
  $$('.lb-row, .llb-row').forEach((row, i) => {
    row.style.opacity = '0';
    row.style.transform = 'translateX(-10px)';
    setTimeout(() => { row.style.transition = 'opacity .3s ease,transform .3s ease'; row.style.opacity = '1'; row.style.transform = 'none'; }, 40 + i * 30);
  });
}

/* ── Goal card hover ───────────────────────────────────── */
function initGoalCards() {
  $$('.goal-card').forEach(c => {
    c.addEventListener('mouseenter', () => { c.style.borderColor = 'rgba(212,175,55,.4)'; });
    c.addEventListener('mouseleave', () => { c.style.borderColor = ''; });
  });
}

/* ── Keyboard shortcuts ────────────────────────────────── */
function initKeyboard() {
  document.addEventListener('keydown', e => {
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'n' || e.key === 'N') {
      const btn = $$('button.btn-gold').find(b => b.textContent.includes('+'));
      if (btn) { e.preventDefault(); btn.click(); }
    }
    if (e.key === 'Escape') Modal.close();
  });
}

/* ── Workout expand ────────────────────────────────────── */
function initWorkoutCards() {
  $$('.workout-card-header').forEach(header => {
    const list = header.closest('.workout-card')?.querySelector('.exercise-list');
    if (!list || !list.children.length) return;
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
      const hidden = list.style.display === 'none';
      list.style.display = hidden ? '' : 'none';
    });
  });
}

/* ── Macro ring (nutrition) ────────────────────────────── */
function initMacroRing() {
  const arc = $('.macro-circle circle:last-child');
  if (!arc) return;
  const target = parseFloat(arc.getAttribute('stroke-dasharray'));
  if (!target) return;
  arc.setAttribute('stroke-dasharray', '0 150.8');
  requestAnimationFrame(() => requestAnimationFrame(() => {
    arc.style.transition = 'stroke-dasharray .9s cubic-bezier(.4,0,.2,1)';
    arc.setAttribute('stroke-dasharray', `${target} 150.8`);
  }));
}

/* ── Client search filter (trainer clients list) ────────  */
function initClientFilter() {
  const input = document.getElementById('clientSearch');
  if (!input) return;
  input.addEventListener('input', throttle(function () {
    const q = this.value.toLowerCase();
    $$('.client-card').forEach(card => {
      const name = card.querySelector('.client-name-lg')?.textContent.toLowerCase() || '';
      card.style.display = name.includes(q) ? '' : 'none';
    });
  }, 120));
}

/* ── PWA install prompt ────────────────────────────────── */
function initInstallPrompt() {
  let deferred = null;
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    deferred = e;
    if (sessionStorage.getItem('pwa-shown')) return;
    const banner = document.createElement('div');
    banner.innerHTML = `
      <div style="position:fixed;bottom:5rem;left:50%;transform:translateX(-50%);
           background:var(--surface);border:1px solid var(--gold);border-radius:12px;
           padding:1rem 1.25rem;display:flex;align-items:center;gap:1rem;z-index:9998;
           box-shadow:0 8px 32px rgba(0,0,0,.6);max-width:340px;width:calc(100% - 2rem)">
        <span style="font-size:1.5rem">📲</span>
        <div style="flex:1"><div style="font-weight:700;font-size:.9rem">Install AURON</div>
          <div style="font-size:.75rem;color:var(--muted)">Add to Home Screen</div></div>
        <div style="display:flex;flex-direction:column;gap:.4rem">
          <button id="pwaInstall" style="background:var(--gold);color:#000;border:none;border-radius:6px;padding:.35rem .8rem;font-size:.8rem;font-weight:700;cursor:pointer">Install</button>
          <button id="pwaDismiss" style="background:transparent;color:var(--muted);border:none;font-size:.72rem;cursor:pointer;text-decoration:underline">Later</button>
        </div>
      </div>`;
    document.body.appendChild(banner);
    document.getElementById('pwaInstall').onclick = () => { deferred.prompt(); deferred.userChoice.then(() => { banner.remove(); sessionStorage.setItem('pwa-shown','1'); }); };
    document.getElementById('pwaDismiss').onclick = () => { banner.remove(); sessionStorage.setItem('pwa-shown','1'); };
  });
}

/* ── Service worker ────────────────────────────────────── */
function initSW() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/service-worker.js').catch(() => {});
  }
}

/* ── Page fade-in ──────────────────────────────────────── */
function initPageFade() {
  document.body.style.opacity = '0';
  document.body.style.transition = 'opacity .18s ease';
  requestAnimationFrame(() => requestAnimationFrame(() => { document.body.style.opacity = '1'; }));
}

/* ── Copy invite link (trainer profile) ────────────────── */
window.copyInvite = function () {
  const input = document.getElementById('inviteUrl');
  if (!input) return;
  input.select();
  navigator.clipboard?.writeText(input.value).then(() => showToast('Link copied!', 'success'));
};

/* ── INIT ──────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initPageFade();
  initToasts();
  initForms();
  initPasswordToggle();
  initAvatarUpload();
  initPhotoPreview();
  initWaterButtons();
  initProgressBars();
  initGoalCards();
  initScoreRing();
  initScoreCountUp();
  initMacroRing();
  initTimeline();
  initLeaderboard();
  initWorkoutCards();
  initClientFilter();
  initStatCountUp();
  initUnreadPolling();
  initKeyboard();
  initInstallPrompt();
  initSW();
});