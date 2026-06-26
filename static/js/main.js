/**
 * AURON — main.js
 * Handles all interactive behaviour across every page:
 *   - Modal open / close / keyboard / backdrop
 *   - Toast auto-dismiss
 *   - Form loading states & double-submit guard
 *   - Login role toggle
 *   - Water quick-log animation
 *   - Score ring entrance animation
 *   - Progress bar entrance animation
 *   - Workout — openAddEx helper
 *   - Trainer messages — setMsgType toggle
 *   - Trainer programs — openAssign helper
 *   - PWA install prompt
 *   - Service-worker registration
 *   - Page-load skeleton fade
 *   - Confirm-delete guard
 *   - Active nav highlight fallback
 *   - File input preview (timeline photo)
 *   - Character counter on textareas
 *   - Scroll-to-top on mobile after form submit
 *   - Unread-message badge polling (trainer)
 */

'use strict';

/* ══════════════════════════════════════════════
   1.  UTILITIES
   ══════════════════════════════════════════════ */

/** Query shorthand */
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

/** Safe JSON parse */
function safeJSON(str, fallback = null) {
  try { return JSON.parse(str); } catch { return fallback; }
}

/** Throttle */
function throttle(fn, ms) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last >= ms) { last = now; fn(...args); }
  };
}


/* ══════════════════════════════════════════════
   2.  MODAL SYSTEM
   All modals share .modal class. Open = .open on the wrapper.
   ══════════════════════════════════════════════ */

const Modal = (() => {
  let _stack = [];   // stack of open modal IDs

  function open(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('open');
    _stack.push(id);
    // Focus first focusable element
    const first = el.querySelector('input, select, textarea, button:not([type="button"])');
    if (first) setTimeout(() => first.focus(), 80);
    document.body.style.overflow = 'hidden';
  }

  function close(id) {
    const el = id ? document.getElementById(id) : null;
    if (el) {
      el.classList.remove('open');
      _stack = _stack.filter(x => x !== id);
    } else {
      // Close topmost
      if (_stack.length) close(_stack[_stack.length - 1]);
      return;
    }
    if (!_stack.length) document.body.style.overflow = '';
  }

  function closeAll() {
    [..._stack].forEach(close);
  }

  // Backdrop click closes modal
  document.addEventListener('click', e => {
    if (e.target.classList.contains('modal')) {
      close(e.target.id);
    }
  });

  // ESC key closes topmost modal
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _stack.length) {
      close(_stack[_stack.length - 1]);
    }
  });

  return { open, close, closeAll };
})();

// Expose globally so Jinja inline onclick="" handlers work
window.openModal  = id => Modal.open(id);
window.closeModal = id => Modal.close(id);


/* ══════════════════════════════════════════════
   3.  TOAST AUTO-DISMISS
   ══════════════════════════════════════════════ */

function initToasts() {
  const toasts = $$('.toast');
  toasts.forEach((t, i) => {
    // Stagger entrance
    t.style.animationDelay = `${i * 80}ms`;

    // Auto dismiss
    setTimeout(() => dismissToast(t), 4000 + i * 400);
  });
}

function dismissToast(el) {
  if (!el || !el.parentNode) return;
  el.style.transition = 'opacity 0.3s, transform 0.3s';
  el.style.opacity = '0';
  el.style.transform = 'translateX(20px)';
  setTimeout(() => el.remove(), 320);
}

// Click to dismiss
document.addEventListener('click', e => {
  if (e.target.classList.contains('toast')) dismissToast(e.target);
});


/* ══════════════════════════════════════════════
   4.  FORM LOADING STATES & DOUBLE-SUBMIT GUARD
   ══════════════════════════════════════════════ */

function initForms() {
  $$('form').forEach(form => {
    form.addEventListener('submit', function (e) {
      const submitBtn = this.querySelector('[type="submit"]');
      if (!submitBtn) return;

      // Already submitting guard
      if (this.dataset.submitting === 'true') {
        e.preventDefault();
        return;
      }
      this.dataset.submitting = 'true';

      const original = submitBtn.textContent.trim();
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving…';

      // Safety reset — re-enable after 8 s in case of network error
      setTimeout(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = original;
        delete this.dataset.submitting;
      }, 8000);
    });
  });
}


/* ══════════════════════════════════════════════
   5.  LOGIN — ROLE TOGGLE
   The login.html also has inline JS but this is
   the canonical implementation, safe to run twice.
   ══════════════════════════════════════════════ */

window.setRole = function (role) {
  const inp = document.getElementById('roleInput');
  if (inp) inp.value = role;
  $$('.role-btn[data-role]').forEach(b => {
    b.classList.toggle('active', b.dataset.role === role);
  });
};


/* ══════════════════════════════════════════════
   6.  SCORE RING ENTRANCE ANIMATION
   Animates the gold arc from 0 to its target dasharray.
   ══════════════════════════════════════════════ */

function initScoreRing() {
  const arc = $('.score-ring circle:last-child');
  if (!arc) return;

  const target = parseFloat(arc.getAttribute('stroke-dasharray'));
  if (!target) return;

  // Start at 0
  arc.style.transition = 'none';
  arc.setAttribute('stroke-dasharray', `0 326.7`);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      arc.style.transition = 'stroke-dasharray 1s cubic-bezier(0.4,0,0.2,1)';
      arc.setAttribute('stroke-dasharray', `${target} 326.7`);
    });
  });
}


/* ══════════════════════════════════════════════
   7.  PROGRESS BAR ENTRANCE ANIMATION
   ══════════════════════════════════════════════ */

function initProgressBars() {
  $$('.progress-bar').forEach(bar => {
    const target = bar.style.width || '0%';
    bar.style.width = '0%';
    // Use IntersectionObserver so bars animate when they scroll into view
    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          requestAnimationFrame(() => {
            bar.style.transition = 'width 0.8s cubic-bezier(0.4,0,0.2,1)';
            bar.style.width = target;
          });
          obs.unobserve(bar);
        }
      });
    }, { threshold: 0.1 });
    obs.observe(bar);
  });

  // Compliance bars inside trainer pages
  $$('.comp-bar div').forEach(bar => {
    const target = bar.style.width || '0%';
    bar.style.width = '0%';
    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          requestAnimationFrame(() => {
            bar.style.transition = 'width 0.7s cubic-bezier(0.4,0,0.2,1)';
            bar.style.width = target;
          });
          obs.unobserve(bar);
        }
      });
    }, { threshold: 0.1 });
    obs.observe(bar);
  });
}


/* ══════════════════════════════════════════════
   8.  WATER QUICK-BUTTONS — RIPPLE FEEDBACK
   ══════════════════════════════════════════════ */

function initWaterButtons() {
  $$('.quick-btns .btn').forEach(btn => {
    btn.addEventListener('click', function () {
      this.textContent = '✓';
      this.style.background = 'var(--success)';
      this.style.color = '#000';
      // The form will submit and reload; this is just a visual flash
    });
  });
}


/* ══════════════════════════════════════════════
   9.  WORKOUT PAGE — openAddEx HELPER
   Sets the hidden workout_id input before opening the modal.
   Also defined inline in the template but re-exported here
   so it always exists even if the template snippet is skipped.
   ══════════════════════════════════════════════ */

window.openAddEx = function (workoutId) {
  const inp = document.getElementById('addExWorkoutId');
  if (inp) inp.value = workoutId;
  Modal.open('addExModal');
};


/* ══════════════════════════════════════════════
   10.  TRAINER MESSAGES — setMsgType
   ══════════════════════════════════════════════ */

window.setMsgType = function (type, btn) {
  const inp = document.getElementById('msgType');
  if (inp) inp.value = type;

  $$('#newMsgModal .role-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const group = document.getElementById('recipientGroup');
  if (group) group.style.display = type === 'broadcast' ? 'none' : 'block';
};


/* ══════════════════════════════════════════════
   11.  TRAINER PROGRAMS — openAssign HELPER
   Populates the client checkbox list, then opens the modal.
   clientData is injected by the Jinja template.
   ══════════════════════════════════════════════ */

window.openAssign = function (programId) {
  // Set form action
  const form = document.getElementById('assignForm');
  if (form) form.action = `/trainer/programs/${programId}/assign`;

  // Populate checkboxes from clientData (set by Jinja)
  const container = document.getElementById('clientCheckboxes');
  if (container) {
    const clients = window.clientData || [];
    if (clients.length === 0) {
      container.innerHTML = '<p class="text-muted" style="font-size:.85rem">No clients added yet.</p>';
    } else {
      container.innerHTML = clients.map(c => `
        <label class="checkbox-label">
          <input type="checkbox" name="client_ids" value="${c.id || c._id}" />
          ${c.username}
        </label>
      `).join('');
    }
  }

  Modal.open('assignModal');
};


/* ══════════════════════════════════════════════
   12.  FILE INPUT — PHOTO PREVIEW
   Shows a thumbnail when the user picks a progress photo.
   ══════════════════════════════════════════════ */

function initPhotoPreview() {
  $$('input[type="file"][accept*="image"]').forEach(input => {
    input.addEventListener('change', function () {
      const file = this.files[0];
      if (!file) return;

      // Find or create preview img
      let preview = this.parentNode.querySelector('.photo-preview');
      if (!preview) {
        preview = document.createElement('img');
        preview.className = 'photo-preview';
        preview.style.cssText = `
          display:block; width:100%; max-height:200px;
          object-fit:cover; border-radius:8px;
          margin-top:.75rem; border:1px solid var(--border);
        `;
        this.parentNode.appendChild(preview);
      }

      const reader = new FileReader();
      reader.onload = e => { preview.src = e.target.result; };
      reader.readAsDataURL(file);
    });
  });
}


/* ══════════════════════════════════════════════
   13.  TEXTAREA CHARACTER COUNTER
   Adds a subtle counter under any textarea with data-maxlength.
   ══════════════════════════════════════════════ */

function initCharCounters() {
  $$('textarea[data-maxlength]').forEach(ta => {
    const max = parseInt(ta.dataset.maxlength, 10);
    const counter = document.createElement('span');
    counter.style.cssText = 'display:block;font-size:.7rem;color:var(--muted);text-align:right;margin-top:2px;';
    ta.parentNode.appendChild(counter);

    function update() {
      const left = max - ta.value.length;
      counter.textContent = `${left} chars left`;
      counter.style.color = left < 20 ? 'var(--warn)' : 'var(--muted)';
    }
    ta.addEventListener('input', update);
    update();
  });
}


/* ══════════════════════════════════════════════
   14.  CONFIRM DELETE GUARD
   Any form with data-confirm attribute shows a confirmation
   dialog before submitting (used on Remove Client button).
   ══════════════════════════════════════════════ */

function initConfirmForms() {
  $$('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', function (e) {
      const msg = this.dataset.confirm || 'Are you sure?';
      if (!confirm(msg)) e.preventDefault();
    });
  });

  // Also handle any button with data-confirm
  $$('button[data-confirm]').forEach(btn => {
    btn.addEventListener('click', function (e) {
      const msg = this.dataset.confirm || 'Are you sure?';
      if (!confirm(msg)) e.preventDefault();
    });
  });
}


/* ══════════════════════════════════════════════
   15.  ACTIVE NAV HIGHLIGHT FALLBACK
   In case Jinja active class is wrong (e.g. sub-routes),
   this JS ensures the right nav item is highlighted.
   ══════════════════════════════════════════════ */

function initActiveNav() {
  const path = window.location.pathname;

  // Sidebar links
  $$('.nav-item[href]').forEach(link => {
    const href = link.getAttribute('href');
    if (!href || href === '#') return;
    // Remove any existing active from mis-matched ones
    if (path.startsWith(href) && href !== '/') {
      link.classList.add('active');
    }
  });

  // Bottom nav links
  $$('.bn-item[href]').forEach(link => {
    const href = link.getAttribute('href');
    if (!href || href === '#') return;
    if (path.startsWith(href) && href !== '/') {
      link.classList.add('active');
    }
  });
}


/* ══════════════════════════════════════════════
   16.  PAGE SKELETON FADE-IN
   Remove a skeleton loader class once the page is ready.
   ══════════════════════════════════════════════ */

function initPageFade() {
  document.body.style.opacity = '0';
  document.body.style.transition = 'opacity 0.2s ease';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.body.style.opacity = '1';
    });
  });
}


/* ══════════════════════════════════════════════
   17.  UNREAD MESSAGE BADGE (USER SIDE)
   Polls /api/messages/unread every 60 s when logged in
   as a user, and shows a badge on the Messages nav item
   if the trainer has sent new messages.
   ══════════════════════════════════════════════ */

function initMessageBadge() {
  // Only run on user pages
  const isUserPage = document.querySelector('.nav-item[href="/user/dashboard"]');
  if (!isUserPage) return;

  function fetchUnread() {
    fetch('/api/messages/unread')
      .then(r => r.json())
      .then(data => {
        const count = data.count || 0;
        // Look for any existing badge
        $$('.nav-badge').forEach(b => b.remove());

        if (count > 0) {
          // We don't have a messages link in the user sidebar by default,
          // but inject a badge on the profile icon as a notification hint
          const profileLinks = $$('.nav-item[href="/user/profile"], .bn-item[href="/user/profile"]');
          profileLinks.forEach(link => {
            const badge = document.createElement('span');
            badge.className = 'nav-badge';
            badge.textContent = count > 9 ? '9+' : count;
            badge.style.cssText = `
              position:absolute; top:4px; right:4px;
              background:var(--gold); color:#000;
              border-radius:999px; font-size:.6rem;
              font-weight:800; padding:1px 5px;
              min-width:16px; text-align:center;
              line-height:14px;
            `;
            link.style.position = 'relative';
            link.appendChild(badge);
          });
        }
      })
      .catch(() => {}); // Silent fail — offline or not logged in
  }

  fetchUnread();
  setInterval(fetchUnread, 60_000);
}


/* ══════════════════════════════════════════════
   18.  PWA — SERVICE WORKER REGISTRATION
   ══════════════════════════════════════════════ */

function initServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker
      .register('/static/service-worker.js')
      .then(reg => console.log('[SW] Registered, scope:', reg.scope))
      .catch(err => console.warn('[SW] Registration failed:', err));
  }
}


/* ══════════════════════════════════════════════
   19.  PWA — INSTALL PROMPT (A2HS)
   Shows a custom "Add to Home Screen" banner when the
   browser fires the beforeinstallprompt event.
   ══════════════════════════════════════════════ */

function initInstallPrompt() {
  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    deferredPrompt = e;

    // Only show once per session
    if (sessionStorage.getItem('pwa-prompt-shown')) return;

    const banner = document.createElement('div');
    banner.id = 'pwa-banner';
    banner.innerHTML = `
      <div style="
        position:fixed; bottom:5rem; left:50%; transform:translateX(-50%);
        background:var(--surface); border:1px solid var(--gold);
        border-radius:12px; padding:1rem 1.25rem;
        display:flex; align-items:center; gap:1rem;
        z-index:9998; box-shadow:0 8px 32px rgba(0,0,0,.6);
        max-width:340px; width:calc(100% - 2rem);
        animation: slideUp .3s ease;
      ">
        <span style="font-size:1.5rem">📲</span>
        <div style="flex:1">
          <div style="font-weight:700;font-size:.9rem">Install AURON</div>
          <div style="font-size:.78rem;color:var(--muted)">Add to Home Screen for the best experience</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:.4rem">
          <button id="pwa-install-btn" style="
            background:var(--gold);color:#000;border:none;
            border-radius:6px;padding:.35rem .8rem;
            font-size:.8rem;font-weight:700;cursor:pointer;
          ">Install</button>
          <button id="pwa-dismiss-btn" style="
            background:transparent;color:var(--muted);border:none;
            font-size:.75rem;cursor:pointer;text-decoration:underline;
          ">Later</button>
        </div>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `@keyframes slideUp{from{opacity:0;transform:translate(-50%,20px)}to{opacity:1;transform:translate(-50%,0)}}`;
    document.head.appendChild(style);
    document.body.appendChild(banner);

    document.getElementById('pwa-install-btn').addEventListener('click', () => {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(choice => {
        deferredPrompt = null;
        banner.remove();
        sessionStorage.setItem('pwa-prompt-shown', '1');
      });
    });

    document.getElementById('pwa-dismiss-btn').addEventListener('click', () => {
      banner.remove();
      sessionStorage.setItem('pwa-prompt-shown', '1');
    });
  });
}


/* ══════════════════════════════════════════════
   20.  SCROLL-TO-TOP AFTER MOBILE FORM SUBMIT
   On mobile, after a quick-action form submit the page
   reloads and the user should see the top of the dashboard.
   ══════════════════════════════════════════════ */

function initScrollTop() {
  if (window.innerWidth > 768) return;
  // If navigated here via a POST (form result), scroll to top
  if (performance.navigation?.type === 1 || performance.getEntriesByType?.('navigation')[0]?.type === 'reload') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}


/* ══════════════════════════════════════════════
   21.  SCORE NUMBER — COUNT-UP ANIMATION
   Makes the big score number count up from 0 on load.
   ══════════════════════════════════════════════ */

function initScoreCountUp() {
  const el = $('.score-number');
  if (!el) return;

  const target = parseInt(el.textContent, 10);
  if (isNaN(target)) return;

  let current = 0;
  const duration = 1000; // ms
  const step = target / (duration / 16);

  el.textContent = '0';

  const tick = () => {
    current = Math.min(current + step, target);
    el.textContent = Math.round(current);
    if (current < target) requestAnimationFrame(tick);
  };

  // Delay so ring animation starts first
  setTimeout(() => requestAnimationFrame(tick), 200);
}


/* ══════════════════════════════════════════════
   22.  GOAL CARD HOVER — SUBTLE GOLD BORDER
   ══════════════════════════════════════════════ */

function initGoalCardHover() {
  $$('.goal-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.borderColor = 'rgba(212,175,55,0.4)';
    });
    card.addEventListener('mouseleave', () => {
      card.style.borderColor = '';
    });
  });
}


/* ══════════════════════════════════════════════
   23.  TIMELINE — STAGGER ENTRANCE
   ══════════════════════════════════════════════ */

function initTimelineEntrance() {
  const items = $$('.timeline-item');
  if (!items.length) return;

  items.forEach((item, i) => {
    item.style.opacity = '0';
    item.style.transform = 'translateY(16px)';

    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            item.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            item.style.opacity = '1';
            item.style.transform = 'none';
          }, i * 60);
          obs.unobserve(item);
        }
      });
    }, { threshold: 0.05 });

    obs.observe(item);
  });
}


/* ══════════════════════════════════════════════
   24.  LEADERBOARD — ROW STAGGER
   ══════════════════════════════════════════════ */

function initLeaderboardEntrance() {
  $$('.lb-row').forEach((row, i) => {
    row.style.opacity = '0';
    row.style.transform = 'translateX(-12px)';
    setTimeout(() => {
      row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      row.style.opacity = '1';
      row.style.transform = 'none';
    }, 40 + i * 35);
  });
}


/* ══════════════════════════════════════════════
   25.  WORKOUT CARD — EXPAND / COLLAPSE EXERCISES
   Clicking the workout header toggles exercise list visibility.
   ══════════════════════════════════════════════ */

function initWorkoutCards() {
  $$('.workout-card-header').forEach(header => {
    header.style.cursor = 'pointer';
    const exList = header.closest('.workout-card')?.querySelector('.exercise-list');
    if (!exList || !exList.children.length) return;

    header.addEventListener('click', () => {
      const hidden = exList.style.display === 'none';
      exList.style.display = hidden ? '' : 'none';
      // Toggle chevron indicator
      let chevron = header.querySelector('.expand-chevron');
      if (!chevron) {
        chevron = document.createElement('span');
        chevron.className = 'expand-chevron';
        chevron.style.cssText = 'font-size:.7rem;color:var(--muted);margin-left:.5rem;transition:transform .2s';
        chevron.textContent = '▲';
        header.querySelector('.workout-volume')?.appendChild(chevron);
      }
      chevron.style.transform = hidden ? '' : 'rotate(180deg)';
    });
  });
}


/* ══════════════════════════════════════════════
   26.  PASSWORD SHOW / HIDE TOGGLE
   Adds an eye icon inside password inputs on auth pages.
   ══════════════════════════════════════════════ */

function initPasswordToggle() {
  $$('input[type="password"]').forEach(input => {
    const wrap = input.parentNode;
    // Only if wrap is a .form-group
    if (!wrap.classList.contains('form-group')) return;

    wrap.style.position = 'relative';

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Toggle password visibility');
    toggle.style.cssText = `
      position:absolute; right:10px; top:50%; transform:translateY(-50%);
      background:none; border:none; cursor:pointer;
      color:var(--muted); font-size:1rem; padding:4px;
      display:flex; align-items:center;
      /* nudge down to account for label */
      margin-top: 10px;
    `;
    toggle.innerHTML = eyeIcon('closed');
    wrap.appendChild(toggle);

    // Give input padding so text isn't under icon
    input.style.paddingRight = '2.5rem';

    toggle.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      toggle.innerHTML = eyeIcon(show ? 'open' : 'closed');
    });
  });
}

function eyeIcon(state) {
  return state === 'open'
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
}


/* ══════════════════════════════════════════════
   27.  CLIENT CARD — SEARCH FILTER (TRAINER)
   Filters client cards live as the trainer types.
   ══════════════════════════════════════════════ */

function initClientSearch() {
  const searchInput = document.getElementById('clientSearch');
  if (!searchInput) return;

  searchInput.addEventListener('input', throttle(function () {
    const q = this.value.toLowerCase().trim();
    $$('.client-card').forEach(card => {
      const name = card.querySelector('.client-name-lg')?.textContent.toLowerCase() || '';
      card.style.display = name.includes(q) ? '' : 'none';
    });
  }, 120));
}


/* ══════════════════════════════════════════════
   28.  KEYBOARD SHORTCUT — N for New (contextual)
   Press N to open the primary action modal on each page.
   ══════════════════════════════════════════════ */

function initKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    // Don't fire when typing in inputs
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === 'n' || e.key === 'N') {
      // Find the first "+ " button on the page
      const addBtn = $$('button.btn-gold').find(b => b.textContent.includes('+'));
      if (addBtn) { e.preventDefault(); addBtn.click(); }
    }

    if (e.key === 'Escape') {
      Modal.closeAll();
    }
  });
}


/* ══════════════════════════════════════════════
   29.  NUTRITION MACRO RING — ENTRANCE
   ══════════════════════════════════════════════ */

function initMacroRing() {
  const arc = $('.macro-circle circle:last-child');
  if (!arc) return;

  const target = parseFloat(arc.getAttribute('stroke-dasharray'));
  if (!target) return;

  arc.style.transition = 'none';
  arc.setAttribute('stroke-dasharray', `0 150.8`);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      arc.style.transition = 'stroke-dasharray 0.9s cubic-bezier(0.4,0,0.2,1)';
      arc.setAttribute('stroke-dasharray', `${target} 150.8`);
    });
  });
}


/* ══════════════════════════════════════════════
   30.  STAT BOX — COUNT-UP ON TRAINER DASHBOARD
   ══════════════════════════════════════════════ */

function initStatBoxCountUp() {
  $$('.stat-big').forEach(el => {
    // Only numeric content
    const raw = el.textContent.trim().replace(/[^0-9]/g, '');
    if (!raw) return;

    const target = parseInt(raw, 10);
    const suffix = el.textContent.trim().replace(/[0-9]/g, '');
    if (isNaN(target) || target === 0) return;

    let current = 0;
    const step = Math.max(1, Math.ceil(target / 30));

    el.textContent = '0' + suffix;

    const tick = () => {
      current = Math.min(current + step, target);
      el.textContent = current + suffix;
      if (current < target) requestAnimationFrame(tick);
    };

    setTimeout(() => requestAnimationFrame(tick), 100);
  });
}


/* ══════════════════════════════════════════════
   INIT — Run everything on DOMContentLoaded
   ══════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  initPageFade();
  initToasts();
  initForms();
  initActiveNav();
  initPasswordToggle();
  initPhotoPreview();
  initCharCounters();
  initConfirmForms();
  initWaterButtons();
  initProgressBars();
  initGoalCardHover();
  initScoreRing();
  initScoreCountUp();
  initMacroRing();
  initTimelineEntrance();
  initLeaderboardEntrance();
  initWorkoutCards();
  initClientSearch();
  initMessageBadge();
  initKeyboardShortcuts();
  initScrollTop();
  initStatBoxCountUp();
  initInstallPrompt();
  initServiceWorker();
});