/**
 * Small, dependency-free HTTP layer for the Django API.
 *
 * Every request is JSON, errors are normalised into ApiError, and pagination
 * envelopes are parsed here so components never touch raw fetch().
 */

export class ApiError extends Error {
  constructor(message, { status = 0, data = null, url = "" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.url = url;
  }
}

export function normalizeBaseUrl(value) {
  return (value || "").trim().replace(/\/+$/, "");
}

/** Read the Vite-injected base URL without hardcoding a production host. */
export function apiBaseUrlFromEnv(env) {
  return normalizeBaseUrl(env?.VITE_API_BASE_URL);
}

export function buildUrl(baseUrl, path, params) {
  const query = new URLSearchParams();
  for (const [key, raw] of Object.entries(params || {})) {
    if (raw === undefined || raw === null || raw === "") continue;
    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (value === undefined || value === null || value === "") continue;
      query.append(key, String(value));
    }
  }
  const suffix = query.toString();
  return `${normalizeBaseUrl(baseUrl)}${path}${suffix ? `?${suffix}` : ""}`;
}

function errorMessage(status, data, fallback) {
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.errors) && data.errors.length) {
      return data.errors
        .map((item) => item.message || item.code)
        .filter(Boolean)
        .join(" ");
    }
    const first = Object.values(data).find(
      (value) => Array.isArray(value) && value.length,
    );
    if (first) return String(first[0]);
  }
  if (status === 401) return "Your session has expired. Sign in again.";
  if (status === 403) return "You do not have permission to do that.";
  if (status === 404) return "That item could not be found.";
  if (status === 429) return "Too many requests. Try again shortly.";
  if (status >= 500) return "The server could not complete the request.";
  return fallback;
}

export function createApiClient({
  baseUrl = "",
  fetchImpl = (...args) => globalThis.fetch(...args),
  timeout = 15000,
} = {}) {
  const root = normalizeBaseUrl(baseUrl);

  async function request(path, options = {}) {
    const {
      method = "GET",
      query,
      body,
      token,
      headers = {},
      signal,
      timeoutMs = timeout,
    } = options;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const abort = () => controller.abort();
    if (signal) signal.addEventListener("abort", abort, { once: true });

    const requestHeaders = { Accept: "application/json", ...headers };
    if (body !== undefined) requestHeaders["Content-Type"] = "application/json";
    if (token) requestHeaders.Authorization = `Bearer ${token}`;

    const url = buildUrl(root, path, query);
    let response;
    try {
      response = await fetchImpl(url, {
        method,
        headers: requestHeaders,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
        credentials: "omit",
        mode: "cors",
      });
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new ApiError("The request timed out.", { url });
      }
      throw new ApiError(
        "The API is unreachable. Check that the backend is running.",
        { url },
      );
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener("abort", abort);
    }

    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text.slice(0, 200) };
      }
    }

    if (!response.ok) {
      throw new ApiError(
        errorMessage(response.status, data, `Request failed (${response.status}).`),
        { status: response.status, data, url },
      );
    }
    return data;
  }

  async function listAll(
    path,
    { query = {}, maxPages = 10, pageSize = 60, ...options } = {},
  ) {
    const collected = [];
    let pageNumber = 1;
    let total = 0;
    while (pageNumber <= maxPages) {
      const envelope = await request(path, {
        ...options,
        query: { ...query, page: pageNumber, page_size: pageSize },
      });
      const results = Array.isArray(envelope?.results) ? envelope.results : [];
      collected.push(...results);
      total = Number(envelope?.count) || collected.length;
      const hasNext = Boolean(envelope?.next) && results.length > 0;
      if (!hasNext || collected.length >= total) break;
      pageNumber += 1;
    }
    return { results: collected, count: total, truncated: collected.length < total };
  }

  return {
    request,
    listAll,
    getConfig: () => request("/_allauth/app/v1/config"),
    listCategories: () => listAll("/api/v1/categories/"),
    listTags: () => listAll("/api/v1/tags/"),
    listWallpapers: (query, options = {}) =>
      listAll("/api/v1/wallpapers/", { ...options, query }),
    listPopular: (query, options = {}) =>
      listAll("/api/v1/wallpapers/popular/", { ...options, query }),
    getWallpaper: (slug) =>
      request(`/api/v1/wallpapers/${encodeURIComponent(slug)}/`),
    trackDownload: (slug) =>
      request(`/api/v1/wallpapers/${encodeURIComponent(slug)}/download/`, {
        method: "POST",
      }),
    loginWithGoogle: ({ idToken, clientId }) =>
      request("/_allauth/app/v1/auth/provider/token", {
        method: "POST",
        body: {
          provider: "google",
          process: "login",
          token: { id_token: idToken, client_id: clientId },
        },
      }),
    refreshToken: (refreshToken) =>
      request("/_allauth/app/v1/tokens/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
      }),
    logout: (sessionToken) =>
      request("/_allauth/app/v1/auth/session", {
        method: "DELETE",
        headers: { "X-Session-Token": sessionToken },
      }),
    getMe: (token) => request("/api/v1/auth/me/", { token }),
    listLikes: (token) =>
      listAll("/api/v1/library/likes/", { token }),
    listSaved: (token) =>
      listAll("/api/v1/library/saved/", { token }),
    like: (token, slug) =>
      request("/api/v1/library/likes/", {
        method: "POST",
        token,
        body: { wallpaper: slug },
      }),
    unlike: (token, slug) =>
      request(`/api/v1/library/likes/${encodeURIComponent(slug)}/`, {
        method: "DELETE",
        token,
      }),
    save: (token, slug) =>
      request("/api/v1/library/saved/", {
        method: "POST",
        token,
        body: { wallpaper: slug },
      }),
    unsave: (token, slug) =>
      request(`/api/v1/library/saved/${encodeURIComponent(slug)}/`, {
        method: "DELETE",
        token,
      }),
  };
}
