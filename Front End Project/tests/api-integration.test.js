import test from "node:test";
import assert from "node:assert/strict";

import {
  ApiError,
  buildUrl,
  createApiClient,
  normalizeBaseUrl,
} from "../src/lib/api.js";
import {
  librarySlugs,
  toUiCategory,
  toUiTag,
  toUiUser,
  toUiWallpaper,
  toUiWallpaperDetail,
  toWallpaperQuery,
} from "../src/lib/adapters.js";
import { createSession, signInErrorMessage } from "../src/lib/session.js";
import { downloadFromUrl, downloadWallpaper } from "../src/lib/download.js";
import { loadGoogleIdentity, resetGoogleLoader } from "../src/lib/google.js";

const jsonResponse = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  text: async () => (body === undefined ? "" : JSON.stringify(body)),
});

const apiWallpaper = {
  slug: "altai-mountains",
  title: "Altai Mountains",
  description: "A quiet ridge line.",
  category: { name: "Nature", slug: "nature" },
  tags: [
    { name: "Mountains", slug: "mountains" },
    { name: "Cold", slug: "cold" },
  ],
  url: "https://cdn.example/altai.jpg",
  thumbnail_url: "https://cdn.example/altai-thumb.jpg",
  image_source: "external",
  orientation: "landscape",
  width: 2560,
  height: 1600,
  published_at: "2026-01-05T10:00:00Z",
  download_count: 12,
};

test("base URLs are trimmed and query params are serialised without empties", () => {
  assert.equal(normalizeBaseUrl(" http://api.test/// "), "http://api.test");
  assert.equal(
    buildUrl("http://api.test/", "/api/v1/wallpapers/", {
      search: "quiet ridge",
      page: 2,
      category: "",
      tag: ["mountains", "cold"],
      missing: null,
    }),
    "http://api.test/api/v1/wallpapers/?search=quiet+ridge&page=2&tag=mountains&tag=cold",
  );
});

test("the client sends JSON, bearer tokens, and parses envelopes", async () => {
  const calls = [];
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ count: 0, next: null, previous: null, results: [] });
    },
  });

  const envelope = await client.listWallpapers({ search: "sea" });

  assert.deepEqual(envelope, { results: [], count: 0, truncated: false });
  assert.equal(
    calls[0].url,
    "http://api.test/api/v1/wallpapers/?search=sea&page=1&page_size=60",
  );
  assert.equal(calls[0].options.headers.Authorization, undefined);

  await client.getMe("access-token");
  assert.equal(calls[1].options.headers.Authorization, "Bearer access-token");
  assert.equal(calls[1].options.credentials, "omit");
});

test("listAll follows next links and stops at the documented page-size cap", async () => {
  const urls = [];
  const pages = [
    { count: 3, next: "http://api.test/page=2", results: [apiWallpaper, apiWallpaper] },
    { count: 3, next: null, results: [apiWallpaper] },
  ];
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async (url) => {
      urls.push(url);
      return jsonResponse(pages.shift());
    },
  });

  const { results, count, truncated } = await client.listWallpapers();

  assert.equal(results.length, 3);
  assert.equal(count, 3);
  assert.equal(truncated, false);
  assert.match(urls[0], /page=1&page_size=60/);
  assert.match(urls[1], /page=2&page_size=60/);
});

test("the page cap is enforced and reported when more pages exist", async () => {
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async () => jsonResponse({
      count: 120,
      next: "http://api.test/page=2",
      results: [apiWallpaper],
    }),
  });

  const result = await client.listWallpapers(undefined, { maxPages: 1 });

  assert.equal(result.results.length, 1);
  assert.equal(result.count, 120);
  assert.equal(result.truncated, true);
});

test("API errors become ApiError with status and a readable message", async () => {
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async () =>
      jsonResponse({ detail: "Authentication credentials were not provided." }, 401),
  });

  await assert.rejects(client.getMe("expired"), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 401);
    assert.equal(
      error.message,
      "Authentication credentials were not provided.",
    );
    return true;
  });
});

test("library writes use the documented payload and slug paths", async () => {
  const calls = [];
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return options.method === "DELETE"
        ? jsonResponse(undefined, 204)
        : jsonResponse({ wallpaper: apiWallpaper, liked_at: "2026-01-01T00:00:00Z" }, 201);
    },
  });

  await client.like("token", "altai-mountains");
  await client.unlike("token", "altai-mountains");
  await client.save("token", "altai-mountains");
  await client.unsave("token", "altai-mountains");

  assert.equal(calls[0].url, "http://api.test/api/v1/library/likes/");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    wallpaper: "altai-mountains",
  });
  assert.equal(
    calls[1].url,
    "http://api.test/api/v1/library/likes/altai-mountains/",
  );
  assert.equal(calls[1].options.method, "DELETE");
  assert.equal(
    calls[3].url,
    "http://api.test/api/v1/library/saved/altai-mountains/",
  );
});

test("unreachable APIs and timeouts surface as ApiError, not raw fetch errors", async () => {
  const offline = createApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async () => {
      throw new TypeError("Failed to fetch");
    },
  });
  await assert.rejects(offline.listCategories(), (error) => {
    assert.ok(error instanceof ApiError);
    assert.match(error.message, /unreachable/i);
    return true;
  });
});

test("wallpaper adapter flattens nested category/tags and keeps the slug as id", () => {
  const ui = toUiWallpaper(apiWallpaper);

  assert.equal(ui.id, "altai-mountains");
  assert.equal(ui.category, "Nature");
  assert.equal(ui.categorySlug, "nature");
  assert.deepEqual(ui.tags, ["Mountains", "Cold"]);
  assert.deepEqual(ui.tagSlugs, ["mountains", "cold"]);
  assert.equal(ui.url, "https://cdn.example/altai-thumb.jpg");
  assert.equal(ui.fullUrl, "https://cdn.example/altai.jpg");
  assert.equal(ui.width, 2560);
  assert.equal(ui.source, undefined);
});

test("detail adapter exposes real provenance only and never fabricates artists", () => {
  const detail = toUiWallpaperDetail({
    ...apiWallpaper,
    source_url: "https://example.com/original",
    license: { name: "CC BY 4.0", url: "https://example.com/license", status: "documented" },
  });

  assert.equal(detail.source.author, undefined);
  assert.equal(detail.source.collection, undefined);
  assert.equal(detail.source.licenseFile, undefined);
  assert.equal(detail.source.license, "CC BY 4.0");
  assert.equal(detail.source.licenseStatus, "documented");
  assert.equal(detail.source.sourceUrl, "https://example.com/original");
  assert.equal(detail.url, "https://cdn.example/altai.jpg");
});

test("category, tag, user, and library adapters map real response fields", () => {
  assert.deepEqual(
    {
      ...toUiCategory({
        name: "Nature",
        slug: "nature",
        description: "",
        image_url: null,
        wallpaper_count: 9,
      }),
    },
    {
      id: "nature",
      name: "Nature",
      slug: "nature",
      description: "",
      imageUrl: "",
      count: 9,
    },
  );
  assert.equal(toUiTag({ name: "Cold", slug: "cold", wallpaper_count: 2 }).count, 2);
  assert.equal(
    toUiUser({
      id: 4,
      username: "bolu",
      email: "bolu@example.com",
      display_name: "Bolu Adeyemi",
      likes_count: 2,
      saved_count: 1,
    }).firstName,
    "Bolu",
  );
  assert.deepEqual(
    librarySlugs({
      results: [
        { wallpaper: { slug: "a" }, liked_at: "2026-01-01" },
        { wallpaper: { slug: "b" }, liked_at: "2026-01-02" },
      ],
    }),
    ["a", "b"],
  );
});

test("UI state maps only to documented query parameters", () => {
  assert.deepEqual(
    toWallpaperQuery({
      search: "  quiet ridge  ",
      categorySlug: "nature",
      tagSlugs: ["mountains", "cold"],
      orientation: "landscape",
      sort: "title",
    }),
    {
      search: "quiet ridge",
      category: "nature",
      tag: ["mountains", "cold"],
      orientation: "landscape",
      ordering: "title",
    },
  );
  assert.deepEqual(toWallpaperQuery({ sort: "collection" }), {});
  assert.equal(toWallpaperQuery({ search: "x".repeat(120) }).search.length, 100);
});

function fakeApi(overrides = {}) {
  return {
    loginWithGoogle: async () => ({
      meta: { access_token: "access-1", refresh_token: "refresh-1", session_token: "session-1" },
      data: { user: { display: "Bolu", email: "bolu@example.com", username: "bolu" } },
    }),
    getMe: async () => ({
      id: 1,
      username: "bolu",
      email: "bolu@example.com",
      display_name: "Bolu",
      likes_count: 0,
      saved_count: 0,
    }),
    refreshToken: async () => ({
      data: { access_token: "access-2", refresh_token: "refresh-2" },
    }),
    logout: async () => ({}),
    listLikes: async () => ({
      count: 1,
      next: null,
      results: [{ wallpaper: { slug: "altai-mountains" }, liked_at: "2026-01-01" }],
    }),
    listSaved: async () => ({ count: 0, next: null, results: [] }),
    like: async () => ({ wallpaper: { slug: "altai-mountains" }, liked_at: "2026-01-01" }),
    unlike: async () => ({}),
    save: async () => ({ wallpaper: { slug: "altai-mountains" }, saved_at: "2026-01-01" }),
    unsave: async () => ({}),
    ...overrides,
  };
}

test("Google ID token exchange produces app tokens and a profile", async () => {
  const store = createSession({ api: fakeApi() });
  const state = await store.signInWithGoogle({
    idToken: "google-id-token",
    clientId: "client-id.apps.googleusercontent.com",
  });

  assert.equal(state.status, "authenticated");
  assert.equal(state.accessToken, "access-1");
  assert.equal(state.refreshToken, "refresh-1");
  assert.equal(state.sessionToken, "session-1");
  assert.equal(state.user.displayName, "Bolu");
  assert.equal(JSON.stringify(state).includes("google-id-token"), false);
});

test("missing Google configuration never calls the API", async () => {
  let called = false;
  const store = createSession({
    api: fakeApi({
      loginWithGoogle: async () => {
        called = true;
      },
    }),
  });

  const state = await store.signInWithGoogle({ idToken: "id", clientId: "" });

  assert.equal(called, false);
  assert.equal(state, null);
  assert.equal(store.getState().status, "anonymous");
  assert.match(store.getState().error, /not configured/i);
});

test("account-linking conflicts and provider failures produce clear errors", () => {
  assert.match(
    signInErrorMessage(
      new ApiError("", {
        status: 401,
        data: { data: { flows: [{ id: "provider_signup", is_pending: true }] } },
      }),
    ),
    /account with this email/i,
  );
  assert.match(
    signInErrorMessage(new ApiError("", { status: 403 })),
    /not being accepted/i,
  );
  assert.match(
    signInErrorMessage(new ApiError("", { status: 400 })),
    /verify/i,
  );
});

test("an expired access token is refreshed once, then the call is retried", async () => {
  let refreshed = 0;
  let meCalls = 0;
  const api = fakeApi({
    getMe: async (token) => {
      meCalls += 1;
      if (token === "access-1") throw new ApiError("expired", { status: 401 });
      return { id: 1, username: "bolu", display_name: "Bolu", email: "" };
    },
    refreshToken: async (refreshToken) => {
      refreshed += 1;
      assert.equal(refreshToken, "refresh-1");
      return { data: { access_token: "access-2", refresh_token: "refresh-2" } };
    },
  });
  const store = createSession({ api });
  await store.signInWithGoogle({ idToken: "id", clientId: "client" });

  const profile = await store.authorized((token) => api.getMe(token));

  assert.equal(profile.username, "bolu");
  assert.equal(refreshed, 1);
  // 1: profile fetch during sign-in, 2: expired call, 3: retry after refresh.
  assert.equal(meCalls, 3);
  assert.equal(store.getState().refreshToken, "refresh-2");
});

test("a failed refresh clears the session instead of looping", async () => {
  const api = fakeApi({
    getMe: async () => {
      throw new ApiError("expired", { status: 401 });
    },
    refreshToken: async () => {
      throw new ApiError("invalid refresh", { status: 401 });
    },
  });
  const store = createSession({ api });
  await store.signInWithGoogle({ idToken: "id", clientId: "client" });

  await assert.rejects(store.authorized((token) => api.getMe(token)), {
    status: 401,
  });
  assert.equal(store.getState().status, "anonymous");
  assert.equal(store.getState().accessToken, null);
  assert.match(store.getState().error, /expired/i);
});

test("anonymous library actions are rejected before any request", async () => {
  let called = false;
  const store = createSession({
    api: fakeApi({
      like: async () => {
        called = true;
      },
    }),
  });

  await assert.rejects(store.setLike("altai-mountains", false), {
    status: 401,
  });
  assert.equal(called, false);
});

test("library calls reflect server responses and sign-out clears tokens", async () => {
  const calls = [];
  const api = fakeApi({
    unlike: async (_token, slug) => {
      calls.push(["unlike", slug]);
      return {};
    },
    like: async (_token, slug) => {
      calls.push(["like", slug]);
      return { wallpaper: { slug }, liked_at: "2026-01-01" };
    },
    logout: async () => {
      throw new ApiError("session already destroyed", { status: 401 });
    },
  });
  const store = createSession({ api });
  await store.signInWithGoogle({ idToken: "id", clientId: "client" });

  const library = await store.loadLibrary();
  assert.deepEqual(library.liked, ["altai-mountains"]);

  const removed = await store.setLike("altai-mountains", true);
  assert.deepEqual(removed, { active: false, item: null });
  assert.deepEqual(calls, [["unlike", "altai-mountains"]]);

  await store.signOut();
  assert.equal(store.getState().status, "anonymous");
  assert.equal(store.getState().accessToken, null);
});

test("downloads use the URL supplied by the API, not a proxy", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalDocument = globalThis.document;
  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;
  const links = [];
  const fetched = [];

  t.after(() => {
    globalThis.fetch = originalFetch;
    globalThis.document = originalDocument;
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
  });

  globalThis.fetch = async (url) => {
    fetched.push(url);
    return {
      ok: true,
      blob: async () => ({ size: 12, type: "image/png" }),
    };
  };
  URL.createObjectURL = () => "blob:test";
  URL.revokeObjectURL = () => {};
  globalThis.document = {
    createElement: () => {
      const link = { click() {}, remove() {} };
      links.push(link);
      return link;
    },
    body: { append() {} },
  };

  await downloadFromUrl("https://cdn.example/returned.png", "Altai Mountains");

  assert.deepEqual(fetched, ["https://cdn.example/returned.png"]);
  assert.equal(links.length, 1);
  assert.equal(links[0].download, "altai-mountains.png");
  assert.equal(links[0].href, "blob:test");

  globalThis.fetch = async () => ({ ok: false, status: 403 });
  await assert.rejects(downloadWallpaper({ url: "https://cdn.example/x.jpg", title: "X" }));
});

test("a non-image download response is rejected", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });
  globalThis.fetch = async () => ({
    ok: true,
    blob: async () => ({ size: 10, type: "text/html" }),
  });

  await assert.rejects(
    downloadFromUrl("https://cdn.example/page.html", "Not an image"),
    /unavailable/i,
  );
});

test("Google Identity Services is loaded lazily and cached", async (t) => {
  const original = globalThis.google;
  t.after(() => {
    globalThis.google = original;
    resetGoogleLoader();
  });

  const fake = { accounts: { id: { initialize() {}, renderButton() {} } } };
  globalThis.google = fake;

  assert.equal(await loadGoogleIdentity(), fake.accounts.id);
});
