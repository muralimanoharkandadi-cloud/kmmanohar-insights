let searchIndex = [];

async function loadSearch() {
    const response = await fetch("/search-index.json");
    searchIndex = await response.json();
}

function createCard(article) {

    const image = article.image || "";
    const published = (article.published || "").substring(0, 10);
    const labels = (article.labels || []).join(" • ");

    return `
<article class="post-card">

<a href="${article.slug}/">
<img src="${image}" class="post-image" alt="${article.title}">
</a>

<h2>
<a href="${article.slug}/">
${article.title}
</a>
</h2>

<div class="post-meta">
📅 ${published}
</div>

<p class="post-summary">
${article.summary}
</p>

<p class="post-meta">
${labels}
</p>

<a class="read-more" href="${article.slug}/">
Read More →
</a>

</article>
`;
}

function renderResults(results) {

    const container = document.getElementById("articles");
    if (!container) return;

    if (results.length === 0) {
        container.innerHTML = "<p>No articles found.</p>";
        return;
    }

    container.innerHTML = results.map(createCard).join("");
}

function searchArticles() {

    const q = document
        .getElementById("search")
        .value
        .toLowerCase()
        .trim();

    if (!q) {
        renderResults(searchIndex);
        return;
    }

    const results = searchIndex.filter(article =>
        (article.title || "").toLowerCase().includes(q) ||
        (article.summary || "").toLowerCase().includes(q) ||
        (article.labels || []).join(" ").toLowerCase().includes(q)
    );

    renderResults(results);
}

loadSearch().then(() => renderResults(searchIndex));