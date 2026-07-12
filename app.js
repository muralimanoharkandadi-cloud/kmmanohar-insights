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
