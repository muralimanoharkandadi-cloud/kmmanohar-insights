// Netlify Scheduled Function - triggers a site rebuild once a day.
//
// This replaces the GitHub Actions cron approach, which was landing
// anywhere from on-time to ~10 hours late due to GitHub's shared runner
// queue being deprioritized under load during periods of high platform
// usage. Scheduled Functions run on Netlify's own infrastructure and are
// enabled by default on all plans, so timing should be far more reliable.
//
// Schedule is set in netlify.toml (functions."scheduled-rebuild".schedule)
// rather than inline here, to keep it in one config file alongside the
// rest of the build configuration.

const BUILD_HOOK_URL = "https://api.netlify.com/build_hooks/6a520db97eb3c3f311033e4b";

export default async (req) => {
  const { next_run } = await req.json();

  try {
    const response = await fetch(BUILD_HOOK_URL, { method: "POST" });
    console.log(`Triggered rebuild (status ${response.status}). Next run: ${next_run}`);
  } catch (err) {
    console.error("Failed to trigger rebuild:", err);
  }
};
