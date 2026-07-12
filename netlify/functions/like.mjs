// Netlify Function: like counter backed by Netlify Blobs (no external
// service/account needed - Blobs is built into Netlify itself).
//
// GET  /.netlify/functions/like?slug=some-article  -> { count }
// POST /.netlify/functions/like?slug=some-article  -> { count } (incremented by 1)

import { getStore } from "@netlify/blobs";

export default async (req) => {
  const url = new URL(req.url);
  const slug = url.searchParams.get("slug");

  if (!slug) {
    return new Response(JSON.stringify({ error: "missing slug parameter" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const store = getStore("article-likes");
  const key = slug;

  try {
    if (req.method === "POST") {
      const current = (await store.get(key, { type: "json" })) || { count: 0 };
      const updated = { count: current.count + 1 };
      await store.setJSON(key, updated);
      return new Response(JSON.stringify(updated), {
        status: 200,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }

    // GET - just read the current count
    const current = (await store.get(key, { type: "json" })) || { count: 0 };
    return new Response(JSON.stringify(current), {
      status: 200,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
};

export const config = {
  path: "/.netlify/functions/like",
};
