import { useEffect, useRef, useState } from "react";
import { loadGoogleIdentity } from "../lib/google.js";

export default function GoogleSignIn({ clientId, onCredential, onError, busy }) {
  const mount = useRef(null);
  const credentialHandler = useRef(onCredential);
  const errorHandler = useRef(onError);
  const [state, setState] = useState(clientId ? "loading" : "unconfigured");

  credentialHandler.current = onCredential;
  errorHandler.current = onError;

  useEffect(() => {
    if (!clientId) {
      setState("unconfigured");
      return undefined;
    }
    let cancelled = false;
    setState("loading");
    loadGoogleIdentity()
      .then((googleId) => {
        if (cancelled || !mount.current) return;
        googleId.initialize({
          client_id: clientId,
          auto_select: false,
          cancel_on_tap_outside: true,
          callback: (response) => {
            if (response?.credential) {
              credentialHandler.current?.(response.credential);
            } else {
              errorHandler.current?.(
                "Google did not return a sign-in credential. Try again.",
              );
            }
          },
        });
        mount.current.replaceChildren();
        googleId.renderButton(mount.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "pill",
          logo_alignment: "left",
          width: 280,
        });
        setState("ready");
      })
      .catch((error) => {
        if (!cancelled) setState(error.message || "Google sign-in is unavailable.");
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  if (state === "unconfigured") {
    return (
      <p className="detail-note" role="status">
        Google sign-in isn’t configured yet. Set{" "}
        <code>VITE_GOOGLE_CLIENT_ID</code> for this app and the matching{" "}
        <code>GOOGLE_OAUTH_CLIENT_ID</code>/
        <code>GOOGLE_OAUTH_CLIENT_SECRET</code> on the backend to enable it.
      </p>
    );
  }

  return (
    <div role="status" aria-live="polite">
      {busy ? (
        <p className="detail-note">Signing you in…</p>
      ) : state === "loading" ? (
        <p className="detail-note">Loading Google sign-in…</p>
      ) : state === "ready" ? null : (
        <p className="detail-note">{state}</p>
      )}
      <div
        ref={mount}
        style={{
          display: state === "ready" && !busy ? "flex" : "none",
          justifyContent: "center",
          margin: "16px 0",
        }}
      />
    </div>
  );
}
