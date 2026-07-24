// K M Manohar Insights — shared client script (null-safe across all pages).

// --- Mobile navigation ---------------------------------------------------
const menuButton = document.querySelector('.menu-button');
const nav = document.querySelector('.main-nav');
if (menuButton && nav) {
  menuButton.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('open');
    menuButton.setAttribute('aria-expanded', String(isOpen));
  });
  nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
    nav.classList.remove('open');
    menuButton.setAttribute('aria-expanded', 'false');
  }));
}

// --- Footer year ----------------------------------------------------------
const yearEl = document.querySelector('#year');
if (yearEl) yearEl.textContent = new Date().getFullYear();

// --- Archive / search widget (home, /archive/, /search/) ------------------
const archiveList = document.querySelector('#archive-list');
if (archiveList && typeof articles !== 'undefined') {
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const archiveStatus = document.querySelector('#archive-status');
  const searchInput = document.querySelector('#article-search');
  const filterButtons = [...document.querySelectorAll('[data-filter]')];
  let activeFilter = 'all';

  function renderArchive() {
    const query = (searchInput ? searchInput.value : '').trim().toLowerCase();
    const visible = articles.filter(([number, title, cluster, category]) => {
      const matchesFilter = activeFilter === 'all' || cluster === activeFilter;
      return matchesFilter && `${number} ${title} ${category}`.toLowerCase().includes(query);
    });

    archiveList.innerHTML = visible.length ? visible.map(([number, title, , category, inExport, slug]) => `
      <article class="archive-item">
        <span>${String(number).padStart(3, '0')}</span>
        <h3><a href="/articles/${slug}/">${esc(title)}</a></h3>
        <b>${esc(category)}<small>${inExport ? 'Takeout export' : 'Master list'}</small></b>
        <i aria-hidden="true">&#8599;</i>
      </article>`).join('') : '<p class="empty-state">No signals found. Try a broader search.</p>';

    if (archiveStatus) {
      const exported = visible.filter((a) => a[4]).length;
      archiveStatus.textContent = `Showing ${visible.length} of ${articles.length} articles - ${exported} matched to the March 2026 export`;
    }
  }

  filterButtons.forEach((button) => button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    filterButtons.forEach((item) => item.classList.toggle('active', item === button));
    renderArchive();
  }));

  document.querySelectorAll('[data-filter-jump]').forEach((link) => link.addEventListener('click', () => {
    activeFilter = link.dataset.filterJump;
    filterButtons.forEach((button) => button.classList.toggle('active', button.dataset.filter === activeFilter));
    renderArchive();
  }));

  if (searchInput) searchInput.addEventListener('input', renderArchive);
  renderArchive();
}

// --- Newsletter form ------------------------------------------------------
const signupForm = document.querySelector('.signup-form');
if (signupForm) {
  signupForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const email = form.querySelector('input');
    form.querySelector('div').hidden = true;
    form.querySelector('label').hidden = true;
    const note = form.querySelector('p');
    note.className = 'form-message';
    note.textContent = `Thank you - the next insight will find its way to ${email.value}.`;
  });
}

// --- Engagement bar: Like / Comment / Follow / Share -----------------------
const likeBtn = document.querySelector('[data-action="like"]');
if (likeBtn) {
  const slug = likeBtn.dataset.slug;
  const countEl = likeBtn.querySelector('[data-like-count]');
  const likedKey = `liked:${slug}`;
  const alreadyLiked = localStorage.getItem(likedKey) === '1';
  if (alreadyLiked) likeBtn.classList.add('is-active');

  // Try to fetch the real shared count from the backend; fall back to
  // showing nothing (button still works, just without a visible number)
  // if the function isn't deployed/reachable yet.
  fetch(`/.netlify/functions/like?slug=${encodeURIComponent(slug)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (data && typeof data.count === 'number' && countEl) {
        countEl.textContent = data.count > 0 ? data.count : '';
      }
    })
    .catch(() => {});

  likeBtn.addEventListener('click', () => {
    if (localStorage.getItem(likedKey) === '1') return; // one like per visitor
    localStorage.setItem(likedKey, '1');
    likeBtn.classList.add('is-active');

    fetch(`/.netlify/functions/like?slug=${encodeURIComponent(slug)}`, { method: 'POST' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && typeof data.count === 'number' && countEl) {
          countEl.textContent = data.count;
        } else if (countEl && !countEl.textContent) {
          countEl.textContent = '1'; // backend unavailable - show a local-only count
        }
      })
      .catch(() => {
        if (countEl && !countEl.textContent) countEl.textContent = '1';
      });
  });
}

const commentBtn = document.querySelector('[data-action="comment"]');
if (commentBtn) {
  commentBtn.addEventListener('click', () => {
    const target = document.querySelector('#comments');
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

const followBtn = document.querySelector('[data-action="follow"]');
if (followBtn) {
  followBtn.addEventListener('click', () => {
    window.location.href = '/#newsletter';
  });
}

const shareBtn = document.querySelector('[data-action="share"]');
if (shareBtn) {
  shareBtn.addEventListener('click', async () => {
    const shareData = {
      title: shareBtn.dataset.title || document.title,
      url: window.location.href,
    };
    if (navigator.share) {
      try {
        await navigator.share(shareData);
      } catch (err) {
        // user cancelled the share sheet - no action needed
      }
    } else if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(shareData.url);
        const label = shareBtn.querySelector('span:not(.engage-count)');
        if (label) {
          const original = label.textContent;
          label.textContent = 'Copied!';
          setTimeout(() => { label.textContent = original; }, 1800);
        }
      } catch (err) {
        // clipboard write failed silently - nothing more we can do here
      }
    }
  });
}

// --- Interactive Knowledge Cards (Glossary) --------------------------------
// Term triggers (<button class="gterm" data-gterm="slug">) are rendered
// server-side by lib/glossary.py so the actual term text is always present
// in the HTML search engines see - this script only adds the interactive
// preview/modal behavior on top. Definitions live in one shared JSON file
// (assets/glossary.json) fetched once and cached for the whole page.
(function () {
  const triggers = document.querySelectorAll('.gterm');
  if (!triggers.length) return;

  let dataPromise = null;
  function loadGlossaryData() {
    if (!dataPromise) {
      dataPromise = fetch('/assets/glossary.json')
        .then((r) => (r.ok ? r.json() : {}))
        .catch(() => ({}));
    }
    return dataPromise;
  }

  const escapeHtml = (s) => String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // --- Desktop hover/focus preview (lazy-populated on first interaction) --
  function ensurePreview(button, entry) {
    if (button.querySelector('.gterm-preview')) return;
    const preview = document.createElement('span');
    preview.className = 'gterm-preview';
    preview.setAttribute('role', 'tooltip');
    const short = entry.definition.length > 140
      ? entry.definition.slice(0, 137).trim() + '\u2026'
      : entry.definition;
    preview.innerHTML = `<b>${escapeHtml(entry.icon || '')} ${escapeHtml(entry.term)}</b>${escapeHtml(short)}`;
    button.appendChild(preview);
  }

  triggers.forEach((button) => {
    const slug = button.dataset.gterm;
    let primed = false;
    const prime = () => {
      if (primed) return;
      primed = true;
      loadGlossaryData().then((data) => {
        const entry = data[slug];
        if (entry) ensurePreview(button, entry);
      });
    };
    button.addEventListener('mouseenter', prime, { passive: true });
    button.addEventListener('focus', prime);
  });

  // --- Full modal, opened on click/tap/Enter/Space on any device ----------
  let activeModal = null;
  let lastFocusedTrigger = null;

  function closeModal() {
    if (!activeModal) return;
    activeModal.remove();
    document.removeEventListener('keydown', onModalKeydown);
    activeModal = null;
    if (lastFocusedTrigger) lastFocusedTrigger.focus();
  }

  function onModalKeydown(event) {
    if (!activeModal) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeModal();
      return;
    }
    if (event.key === 'Tab') {
      const focusable = activeModal.querySelectorAll('button, a[href]');
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  function openModal(button, entry, slug) {
    closeModal();
    lastFocusedTrigger = button;

    const backdrop = document.createElement('div');
    backdrop.className = 'gterm-backdrop';

    const titleId = `gterm-title-${slug}`;
    const guideHtml = entry.guideUrl
      ? `<a class="gterm-modal-guide" href="${escapeHtml(entry.guideUrl)}">Read Full Guide &rarr;</a>`
      : '';

    backdrop.innerHTML = `
      <div class="gterm-modal" role="dialog" aria-modal="true" aria-labelledby="${titleId}">
        <div class="gterm-modal-inner">
          <button type="button" class="gterm-modal-close" aria-label="Close definition">&times;</button>
          <span class="gterm-modal-icon" aria-hidden="true">${escapeHtml(entry.icon || '\ud83d\udcd6')}</span>
          <h2 id="${titleId}">${escapeHtml(entry.term)}</h2>
          <p>${escapeHtml(entry.definition)}</p>
          ${guideHtml}
        </div>
      </div>`;

    backdrop.addEventListener('mousedown', (event) => {
      if (event.target === backdrop) closeModal();
    });
    backdrop.querySelector('.gterm-modal-close').addEventListener('click', closeModal);

    document.body.appendChild(backdrop);
    activeModal = backdrop;
    document.addEventListener('keydown', onModalKeydown);
    backdrop.querySelector('.gterm-modal-close').focus();
  }

  triggers.forEach((button) => {
    button.addEventListener('click', () => {
      const slug = button.dataset.gterm;
      loadGlossaryData().then((data) => {
        const entry = data[slug];
        if (entry) openModal(button, entry, slug);
      });
    });
  });
})();
