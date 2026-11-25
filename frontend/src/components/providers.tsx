"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { Toaster } from "sonner";
import { ApiError } from "@/lib/api";

type Theme = "light" | "dark" | "system";
const ThemeCtx = createContext<{ theme: Theme; resolved: "light" | "dark"; setTheme: (t: Theme) => void }>({
  theme: "system", resolved: "light", setTheme: () => {},
});
export const useTheme = () => useContext(ThemeCtx);

const THEME_KEY = "airsense-theme";
const THEME_EVENT = "airsense-theme-change";

function readStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system"; // storage blocked (private mode etc.)
  }
}

function subscribeTheme(cb: () => void) {
  window.addEventListener("storage", cb);
  window.addEventListener(THEME_EVENT, cb);
  return () => { window.removeEventListener("storage", cb); window.removeEventListener(THEME_EVENT, cb); };
}

function subscribeScheme(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useSyncExternalStore(subscribeTheme, readStoredTheme, () => "system" as Theme);
  const systemDark = useSyncExternalStore(subscribeScheme, () => window.matchMedia("(prefers-color-scheme: dark)").matches, () => false);
  const resolved: "light" | "dark" = theme === "system" ? (systemDark ? "dark" : "light") : theme;

  // Sync the external DOM with React state (the documented use of an effect)
  useEffect(() => { document.documentElement.classList.toggle("dark", resolved === "dark"); }, [resolved]);

  const setTheme = useCallback((t: Theme) => {
    try { localStorage.setItem(THEME_KEY, t); } catch { /* storage unavailable: theme applies for this page only */ }
    window.dispatchEvent(new Event(THEME_EVENT));
  }, []);
  return <ThemeCtx.Provider value={{ theme, resolved, setTheme }}>{children}</ThemeCtx.Provider>;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      },
    },
  }));
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        {children}
        <ToasterThemed />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

function ToasterThemed() {
  const { resolved } = useTheme();
  return <Toaster theme={resolved} position="bottom-right" richColors closeButton toastOptions={{ style: { borderRadius: 14 } }} />;
}
