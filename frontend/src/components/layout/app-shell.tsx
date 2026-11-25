"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bell, BookOpen, BrainCircuit, ChartNoAxesCombined, LayoutDashboard, LogOut, Map, Menu, Settings, Sparkles, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Logo, ThemeToggle } from "@/components/layout/brand";
import { Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { cn, fmt } from "@/lib/format";
import { useCurrent, useLogout, useMe } from "@/lib/hooks";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/analytics", label: "Analytics", icon: ChartNoAxesCombined },
  { href: "/forecast", label: "Forecast", icon: Sparkles },
  { href: "/models", label: "Model Lab", icon: BrainCircuit },
  { href: "/map", label: "Geospatial", icon: Map },
  { href: "/alerts", label: "Alerts", icon: Bell },
];
const SECONDARY = [
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
];

function NavLinks({ onNavigate, unread }: { onNavigate?: () => void; unread: number }) {
  const path = usePathname();
  const item = (n: (typeof NAV)[number]) => {
    const active = path === n.href || path.startsWith(`${n.href}/`);
    return (
      <Link key={n.href} href={n.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
        className={cn("group relative flex items-center gap-3 rounded-[10px] px-3 py-2 text-[13.5px] font-medium transition",
          active ? "bg-elevated text-fg shadow-sm ring-1 ring-line" : "text-muted hover:bg-elevated/60 hover:text-fg")}>
        <n.icon className={cn("size-[18px]", active ? "text-brand-600" : "text-faint group-hover:text-muted")} />
        {n.label}
        {n.href === "/alerts" && unread > 0 && (
          <span className="ml-auto rounded-full bg-danger px-1.5 text-[11px] font-semibold text-white tabular">{unread > 99 ? "99+" : unread}</span>
        )}
      </Link>
    );
  };
  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-1">
      <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-faint">Workspace</p>
      {NAV.map(item)}
      <p className="px-3 pb-1 pt-5 text-[11px] font-semibold uppercase tracking-wider text-faint">Account</p>
      {SECONDARY.map(item)}
    </nav>
  );
}

function DataFreshness() {
  const { data } = useCurrent();
  if (!data?.summary.observed_at) return <Skeleton className="h-14" />;
  return (
    <div className="rounded-[12px] border border-line bg-elevated p-3 text-[12px]">
      <div className="flex items-center gap-2 font-medium text-fg">
        <span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-brand-400 opacity-60" /><span className="relative size-2 rounded-full bg-brand-500" /></span>
        Latest observation
      </div>
      <p className="mt-1 text-muted tabular">{fmt.dateTime(data.summary.observed_at)}</p>
      <p className="mt-0.5 text-faint">{data.summary.stations_reporting}/{data.summary.stations_total} stations · OpenAQ</p>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const path = usePathname();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const unread = useQuery({ queryKey: ["unread"], queryFn: api.unreadCount, enabled: !!me.data, refetchInterval: 120_000 });

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [me.error, router, path]);

  const sidebar = (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between px-1 pb-2"><Logo href="/dashboard" /></div>
      <NavLinks unread={unread.data?.unread ?? 0} onNavigate={() => setOpen(false)} />
      <DataFreshness />
    </div>
  );

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[256px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-elevated focus:px-3 focus:py-2">Skip to content</a>
      <aside className="sticky top-0 hidden h-dvh border-r border-line bg-subtle/60 lg:block">{sidebar}</aside>

      <AnimatePresence>
        {open && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
            <motion.aside className="fixed inset-y-0 left-0 z-50 w-[272px] border-r border-line bg-bg lg:hidden" initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: "spring", damping: 30, stiffness: 300 }}>
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="absolute right-3 top-5 grid size-8 place-items-center rounded-lg text-muted hover:bg-subtle"><X className="size-4" /></button>
              {sidebar}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-bg/80 px-4 backdrop-blur-xl md:px-6">
          <button onClick={() => setOpen(true)} aria-label="Open menu" className="grid size-9 place-items-center rounded-[10px] text-muted hover:bg-subtle lg:hidden"><Menu className="size-5" /></button>
          <div className="lg:hidden"><Logo href="/dashboard" /></div>
          <div className="ml-auto flex items-center gap-1.5">
            <ThemeToggle compact />
            <Link href="/alerts" aria-label={`Alerts (${unread.data?.unread ?? 0} unread)`} className="relative grid size-9 place-items-center rounded-[10px] text-muted hover:bg-subtle hover:text-fg">
              <Bell className="size-[18px]" />
              {(unread.data?.unread ?? 0) > 0 && <span className="absolute right-2 top-2 size-2 rounded-full bg-danger ring-2 ring-bg" />}
            </Link>
            <div className="mx-1 h-6 w-px bg-line" />
            {me.data ? (
              <div className="flex items-center gap-2.5">
                <div className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 text-[12px] font-semibold text-white" aria-hidden>
                  {me.data.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
                </div>
                <div className="hidden leading-tight md:block">
                  <p className="text-[13px] font-medium text-fg">{me.data.full_name}</p>
                  <p className="text-[11.5px] text-faint">{me.data.email}</p>
                </div>
                <button onClick={() => logout.mutate()} aria-label="Sign out" className="ml-1 grid size-9 place-items-center rounded-[10px] text-muted hover:bg-subtle hover:text-fg"><LogOut className="size-[17px]" /></button>
              </div>
            ) : <Skeleton className="h-8 w-32" />}
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-6 md:py-8">
          {me.data ? children : (
            <div className="space-y-4" role="status" aria-label="Loading">
              <Skeleton className="h-9 w-64" /><div className="grid gap-4 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div><Skeleton className="h-80" />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
