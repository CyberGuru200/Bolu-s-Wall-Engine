/**
 * In-memory application session for allauth Headless JWT tokens.
 *
 * Tokens are deliberately NOT written to localStorage/sessionStorage: a page
 * reload signs the user out, and an XSS cannot read persistable credentials.
 * The trade-off is documented in docs/PHASE5_API_INTEGRATION.md; in-memory
 * values are still readable by same-page JavaScript, so this is not a claim of
 * perfect safety.
 */

import { ApiError } from "./api.js";
import { librarySlugs, toUiUser } from "./adapters.js";

export const ANONYMOUS_STATE = Object.freeze({
  status: "anonymous", // anonymous | authenticating | authenticated
  user: null,
  accessToken: null,
  refreshToken: null,
  sessionToken: null,
  error: null,
});

export function signInErrorMessage(error) {
  if (!(error instanceof ApiError)) {
    return "Google sign-in failed. Please try again.";
  }
  if (error.status === 400) {
    return "Google could not verify that sign-in. Please try again.";
  }
  if (error.status === 401) {
    const flows = error.data?.data?.flows || [];
    const pending = flows.some(
      (flow) => flow.id === "provider_signup" && flow.is_pending,
    );
    if (pending) {
      return "An account with this email already exists. Sign in with the method used for that account.";
    }
    return "Sign-in was not accepted. Please try again.";
  }
  if (error.status === 403) {
    return "New accounts are not being accepted right now.";
  }
  return error.message;
}

export function createSession({ api, onChange = () => {} } = {}) {
  let state = { ...ANONYMOUS_STATE };
  let refreshInFlight = null;
  const listeners = new Set();

  function update(patch) {
    state = { ...state, ...patch };
    for (const listener of listeners) listener();
    onChange(state);
  }

  function clear(error = null) {
    update({ ...ANONYMOUS_STATE, error });
  }

  async function loadProfile(token, fallback) {
    try {
      return toUiUser(await api.getMe(token), fallback);
    } catch {
      return toUiUser(null, fallback);
    }
  }

  async function signInWithGoogle({ idToken, clientId }) {
    if (!idToken || !clientId) {
      update({ error: "Google sign-in is not configured." });
      return null;
    }
    update({ status: "authenticating", error: null });
    try {
      const response = await api.loginWithGoogle({ idToken, clientId });
      const meta = response?.meta || {};
      if (!meta.access_token || !meta.refresh_token) {
        throw new ApiError("The sign-in response did not include tokens.");
      }
      const basic = response?.data?.user || {};
      const fallback = {
        name: basic.display || basic.username || "",
        email: basic.email || "",
      };
      update({
        accessToken: meta.access_token,
        refreshToken: meta.refresh_token,
        sessionToken: meta.session_token || null,
      });
      const user = await loadProfile(meta.access_token, fallback);
      update({ status: "authenticated", user });
      return state;
    } catch (error) {
      clear(signInErrorMessage(error));
      return null;
    }
  }

  async function refreshAccess() {
    if (!state.refreshToken) {
      throw new ApiError("Your session has expired. Sign in again.", {
        status: 401,
      });
    }
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      try {
        const response = await api.refreshToken(state.refreshToken);
        const data = response?.data || {};
        if (!data.access_token) {
          throw new ApiError("The refresh response did not include a token.");
        }
        update({
          accessToken: data.access_token,
          refreshToken: data.refresh_token || state.refreshToken,
        });
        return state.accessToken;
      } catch {
        clear("Your session expired. Please sign in again.");
        throw new ApiError("Your session expired. Please sign in again.", {
          status: 401,
        });
      } finally {
        refreshInFlight = null;
      }
    })();
    return refreshInFlight;
  }

  /** Run an authenticated call; retry exactly once after a successful refresh. */
  async function authorized(call) {
    if (!state.accessToken) {
      throw new ApiError("Sign in to use your library.", { status: 401 });
    }
    try {
      return await call(state.accessToken);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401 && state.refreshToken) {
        const token = await refreshAccess();
        return call(token);
      }
      throw error;
    }
  }

  async function loadLibrary() {
    return authorized(async (token) => {
      const [likes, saves] = await Promise.all([
        api.listLikes(token),
        api.listSaved(token),
      ]);
      return {
        liked: librarySlugs(likes),
        saved: librarySlugs(saves),
      };
    });
  }

  async function setLike(slug, liked) {
    return authorized(async (token) => {
      if (liked) {
        await api.unlike(token, slug);
        return { active: false, item: null };
      }
      const response = await api.like(token, slug);
      return { active: true, item: response };
    });
  }

  async function setSave(slug, saved) {
    return authorized(async (token) => {
      if (saved) {
        await api.unsave(token, slug);
        return { active: false, item: null };
      }
      const response = await api.save(token, slug);
      return { active: true, item: response };
    });
  }

  async function signOut() {
    const sessionToken = state.sessionToken;
    try {
      if (sessionToken) await api.logout(sessionToken);
    } catch {
      // allauth answers 401 after destroying the session; the local session is
      // cleared either way, so the user-visible result is the same.
    } finally {
      clear(null);
    }
  }

  return {
    getState: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    signInWithGoogle,
    refreshAccess,
    authorized,
    loadLibrary,
    setLike,
    setSave,
    signOut,
  };
}
