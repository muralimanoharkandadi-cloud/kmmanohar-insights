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
