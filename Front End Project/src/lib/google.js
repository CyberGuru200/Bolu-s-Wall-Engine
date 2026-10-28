/**
 * Google Identity Services loader.
 *
 * Only the public OAuth client id is used here. The client secret never leaves
 * the Django backend. The GIS script is loaded on demand so anonymous browsing
 * never depends on Google being reachable.
 */

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let scriptPromise = null;

export function loadGoogleIdentity(documentRef = globalThis.document) {
  if (globalThis.google?.accounts?.id) {
    return Promise.resolve(globalThis.google.accounts.id);
  }
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve, reject) => {
    if (!documentRef) {
      reject(new Error("Google Identity Services is unavailable."));
      return;
    }
    const existing = documentRef.querySelector(`script[src="${SCRIPT_SRC}"]`);
    const script = existing || documentRef.createElement("script");
    const settle = () => {
      if (globalThis.google?.accounts?.id) {
        resolve(globalThis.google.accounts.id);
      } else {
        reject(new Error("Google Identity Services did not initialise."));
      }
    };
    script.addEventListener("load", settle, { once: true });
    script.addEventListener("error", () => {
      script.remove();
      scriptPromise = null;
      reject(new Error("Google Identity Services could not be loaded."));
    }, { once: true });
    if (!existing) {
      script.src = SCRIPT_SRC;
      script.async = true;
      script.defer = true;
      documentRef.head.append(script);
    }
  });
  return scriptPromise;
}

/** Exported for tests: reset the module-level script promise. */
export function resetGoogleLoader() {
  scriptPromise = null;
}
