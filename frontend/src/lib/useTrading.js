import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export function useInterval(callback, delay) {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  }, [callback]);
  useEffect(() => {
    if (delay == null) return undefined;
    const id = setInterval(() => saved.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

export function useTrading(accountId) {
  const [disclaimer, setDisclaimer] = useState(null);
  const [strategies, setStrategies] = useState(null);
  const [status, setStatus] = useState({ session: null, account_type: null });
  const [tradeData, setTradeData] = useState({ trades: [], stats: null });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadStatic = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([
        api.authed("/trading/disclaimer"),
        api.authed("/trading/strategies"),
      ]);
      setDisclaimer(d);
      setStrategies(s);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const loadLive = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([
        api.authed("/trading/status"),
        api.authed("/trading/trades?limit=50"),
      ]);
      setStatus(s);
      setTradeData(t);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadStatic();
  }, [loadStatic]);

  useEffect(() => {
    loadLive();
  }, [loadLive, accountId]);

  useInterval(loadLive, 2000);

  const run = useCallback(async (task) => {
    setBusy(true);
    setError("");
    try {
      await task();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, []);

  const acknowledge = useCallback(
    () =>
      run(async () => {
        await api.authed("/trading/acknowledge", {
          method: "POST",
          body: { version: disclaimer.version },
        });
        await loadStatic();
      }),
    [run, disclaimer, loadStatic]
  );

  const start = useCallback(
    (body) =>
      run(async () => {
        await api.authed("/trading/start", { method: "POST", body });
        await loadLive();
      }),
    [run, loadLive]
  );

  const stop = useCallback(
    () =>
      run(async () => {
        await api.authed("/trading/stop", { method: "POST" });
        await loadLive();
      }),
    [run, loadLive]
  );

  return {
    disclaimer,
    strategies,
    session: status.session,
    trades: tradeData.trades,
    stats: tradeData.stats,
    error,
    busy,
    acknowledge,
    start,
    stop,
  };
}