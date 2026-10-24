import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "./AuthContext";

const AccountContext = createContext(null);

export function AccountProvider({ children }) {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(false);

  const apply = useCallback((data) => {
    setAccounts(data.accounts);
    setActiveId(data.active_id);
  }, []);

  const refresh = useCallback(async () => {
    try {
      apply(await api.accounts());
    } catch {
      setAccounts([]);
      setActiveId(null);
    }
  }, [apply]);

  useEffect(() => {
    if (!user) {
      setAccounts([]);
      setActiveId(null);
      return;
    }
    setLoading(true);
    refresh().finally(() => setLoading(false));
  }, [user, refresh]);

  const switchTo = useCallback(
    async (id) => {
      apply(await api.switchAccount(id));
    },
    [apply]
  );

  const active = useMemo(() => accounts.find((a) => a.id === activeId) ?? null, [accounts, activeId]);

  const value = useMemo(
    () => ({ accounts, active, loading, refresh, switchTo }),
    [accounts, active, loading, refresh, switchTo]
  );

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccounts() {
  return useContext(AccountContext);
}