import { useCallback, useEffect, useRef, useState } from "react";

export function useQuota(api, enabled = true) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [pending, setPending] = useState(false);
  const changing = useRef(false);
  const generation = useRef(0);
  const refresh = useCallback(async (signal) => {
    if (changing.current) return;
    const current = ++generation.current;
    try {
      const result = await api("quota", { signal });
      if (!signal?.aborted && current === generation.current) { setData(result); setFailed(false); }
    } catch (error) {
      if (!signal?.aborted && current === generation.current && error.name !== "AbortError") setFailed(true);
    }
  }, [api]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    refresh(controller.signal);
    const timer = setInterval(() => refresh(controller.signal), 30000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [enabled, refresh]);
  const change = useCallback(async (path, method, body) => {
    if (changing.current) return null;
    changing.current = true;
    ++generation.current;
    setPending(true);
    try {
      const result = await api(`quota/${path}`, { method, body });
      setData(result);
      setFailed(false);
      return result;
    } finally { changing.current = false; setPending(false); }
  }, [api]);
  return { data, failed, pending, refresh,
    consume: (credit_id) => change("consume", "POST", { credit_id }),
    policy: (exhausted_policy) => change("policy", "PUT", { exhausted_policy }) };
}
