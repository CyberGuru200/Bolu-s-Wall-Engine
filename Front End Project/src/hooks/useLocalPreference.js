import { useEffect, useState } from "react";

export default function useLocalPreference(key, fallback, validate) {
  const [initial] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      const value = raw === null ? fallback : JSON.parse(raw);
      return { value: validate(value) ? value : fallback, unavailable: false };
    } catch {
      return { value: fallback, unavailable: true };
    }
  });
  const [value, setValue] = useState(initial.value);
  const [unavailable, setUnavailable] = useState(initial.unavailable);

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      setUnavailable(true);
    }
  }, [key, value]);

  return [value, setValue, unavailable];
}
