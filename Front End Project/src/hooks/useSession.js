import { useEffect, useState } from "react";
import { ANONYMOUS_STATE } from "../lib/session.js";

/** Subscribe a component to the in-memory session store. */
export default function useSession(store) {
  const [state, setState] = useState(store ? store.getState() : ANONYMOUS_STATE);

  useEffect(() => {
    if (!store) return undefined;
    setState(store.getState());
    return store.subscribe(() => setState(store.getState()));
  }, [store]);

  return state;
}
