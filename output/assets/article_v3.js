document.addEventListener("DOMContentLoaded", () => {

    // -----------------------------
    // Smooth Scroll
    // -----------------------------
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener("click", e => {
            const target = document.querySelector(link.getAttribute("href"));
            if (!target) return;

            e.preventDefault();

            target.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        });
    });

    // -----------------------------
    // Reading Progress Bar
    // -----------------------------
    const progress = document.createElement("div");

    progress.id = "reading-progress";

    progress.style.cssText = `
        position:fixed;
        top:0;
        left:0;
        height:4px;
        width:0%;
        background:#1e73be;
        z-index:99999;
        transition:width .1s linear;
    `;

    document.body.appendChild(progress);

    window.addEventListener("scroll", () => {

        const total =
            document.documentElement.scrollHeight -
            window.innerHeight;

        const percent =
            (window.scrollY / total) * 100;

        progress.style.width = percent + "%";
    });

    // -----------------------------
    // Back To Top
    // -----------------------------
    const topButton = document.createElement("button");

    topButton.innerHTML = "↑";

    topButton.id = "backToTop";

    topButton.style.cssText = `
        position:fixed;
        right:24px;
        bottom:24px;
        width:48px;
        height:48px;
        border:none;
        border-radius:50%;
        background:#1e73be;
        color:#fff;
        font-size:22px;
        cursor:pointer;
        display:none;
        z-index:9999;
        box-shadow:0 6px 20px rgba(0,0,0,.25);
    `;

    document.body.appendChild(topButton);

    window.addEventListener("scroll", () => {

        topButton.style.display =
            window.scrollY > 500
            ? "block"
            : "none";
    });

    topButton.addEventListener("click", () => {

        window.scrollTo({

            top:0,

            behavior:"smooth"

        });

    });

});