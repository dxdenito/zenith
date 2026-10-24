import { useEffect, useRef, useState } from "react";
import { api, wsUrl } from "./api";

const KEEP = 300;

function merge(current = [], incoming = []) {
  const byEpoch = new Map();
  for (const t of current) byEpoch.set(t.epoch, t);
  for (const t of incoming) byEpoch.set(t.epoch, t);
  return [...byEpoch.values()].sort((a, b) => a.epoch - b.epoch).slice(-KEEP);
}

export function useLiveTicks(symbols) {
  const [ticks, setTicks] = useState({});
  const [status, setStatus] = useState("connecting");
  const latest = useRef({});
  const key = symbols.join(",");

  latest.current = ticks;

  useEffect(() => {
    if (!key) {
      setStatus("idle");
      return undefined;
    }
    const list = key.split(",");
    let closed = false;
    let socket = null;
    let timer = null;
    let delay = 1000;

    function loadHistory(symbol) {
      api
        .ticks(symbol, KEEP)
        .then((rows) => {
          if (!closed) setTicks((prev) => ({ ...prev, [symbol]: merge(prev[symbol], rows) }));
        })
        .catch(() => {});
    }

    list.forEach(loadHistory);

    const retry = setInterval(() => {
      list.forEach((symbol) => {
        if ((latest.current[symbol]?.length ?? 0) < 20) loadHistory(symbol);
      });
    }, 8000);

    function open() {
      setStatus("connecting");
      socket = new WebSocket(wsUrl("/markets/stream"));
      socket.onopen = () => {
        delay = 1000;
        setStatus("live");
        socket.send(JSON.stringify({ symbols: list }));
      };
      socket.onmessage = (event) => {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }
        if (msg.type !== "tick") return;
        const tick = { epoch: msg.epoch, quote: msg.quote, digit: msg.digit };
        setTicks((prev) => ({ ...prev, [msg.symbol]: merge(prev[msg.symbol], [tick]) }));
      };
      socket.onclose = async (event) => {
        if (closed) return;
        setStatus("offline");
        if (event.code === 1008) {
          try {
            await api.me();
          } catch {
            return;
          }
        }
        timer = setTimeout(open, delay);
        delay = Math.min(delay * 2, 10000);
      };
    }

    open();

    return () => {
      closed = true;
      clearTimeout(timer);
      clearInterval(retry);
      if (socket) socket.close();
    };
  }, [key]);

  return { ticks, status };
}