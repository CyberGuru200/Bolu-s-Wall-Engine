/**
 * Runtime wiring for the optional API mode.
 *
 * With no VITE_API_BASE_URL the app keeps using its bundled catalogue and
 * browser-local likes/saves exactly as before. Setting the variable switches
 * to the Django API; a failed request then surfaces an error instead of
 * silently falling back, so production problems are never hidden.
 */

import { apiBaseUrlFromEnv, createApiClient } from "./api.js";
import { createSession } from "./session.js";

const env = import.meta.env || {};
export const apiBaseUrl = apiBaseUrlFromEnv(env);
export const googleClientId = (env.VITE_GOOGLE_CLIENT_ID || "").trim();
export const apiMode = Boolean(apiBaseUrl);

export const apiClient = apiMode ? createApiClient({ baseUrl: apiBaseUrl }) : null;

export const sessionStore = apiClient
  ? createSession({ api: apiClient })
  : null;
