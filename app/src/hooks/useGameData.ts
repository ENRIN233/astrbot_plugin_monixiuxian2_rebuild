import { useState, useEffect } from 'react';

const cache: Record<string, unknown> = {};

export function useGameData<T = unknown>(name: string): { data: T | null; loading: boolean; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (cache[name]) {
      setData(cache[name] as T);
      setLoading(false);
      return;
    }
    fetch(`./data/${name}.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(json => {
        cache[name] = json;
        if (!cancelled) { setData(json); setLoading(false); }
      })
      .catch(err => {
        if (!cancelled) { setError(err.message); setLoading(false); }
      });
    return () => { cancelled = true; };
  }, [name]);

  return { data, loading, error };
}
