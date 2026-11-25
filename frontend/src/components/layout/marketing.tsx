"use client";

import { Code2 } from "lucide-react";
import Link from "next/link";
import { Logo, ThemeToggle } from "@/components/layout/brand";
import { ButtonLink } from "@/components/ui/primitives";
import { cn } from "@/lib/format";
import { useMe } from "@/lib/hooks";

export function MarketingNav({ dark }: { dark?: boolean }) {
  const me = useMe();
  return (
    <header className={cn("sticky top-0 z-40 border-b backdrop-blur-xl", dark ? "border-white/10 bg-[#050b14]/70" : "border-line bg-bg/80")}>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 md:px-6">
        <Logo inverted={dark} />
        <nav aria-label="Primary" className={cn("hidden items-center gap-6 text-[13.5px] md:flex", dark ? "text-slate-300" : "text-muted")}>
          <Link href="/#capabilities" className="hover:text-brand-400">Capabilities</Link>
          <Link href="/#how" className="hover:text-brand-400">How it works</Link>
          <Link href="/#forecast" className="hover:text-brand-400">Live forecast</Link>
          <Link href="/methodology" className="hover:text-brand-400">Methodology</Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {!dark && <ThemeToggle compact />}
          {me.data ? (
            <ButtonLink href="/dashboard" size="sm">Open dashboard</ButtonLink>
          ) : (
            <>
              <Link href="/login" className={cn("hidden rounded-[10px] px-3 py-1.5 text-[13.5px] font-medium sm:block", dark ? "text-slate-200 hover:bg-white/10" : "text-fg hover:bg-subtle")}>Sign in</Link>
              <ButtonLink href="/register" size="sm">Get started</ButtonLink>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line bg-subtle/50">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 md:grid-cols-[1.4fr_1fr_1fr_1fr] md:px-6">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-[13px] leading-relaxed text-muted">
            Air-quality intelligence for Pune: monitoring, exploratory analysis and machine-learning PM2.5 forecasts built on open data.
          </p>
        </div>
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-faint">Product</p>
          <ul className="mt-3 space-y-2 text-[13.5px] text-muted">
            <li><Link href="/dashboard" className="hover:text-fg">Dashboard</Link></li>
            <li><Link href="/forecast" className="hover:text-fg">Forecasts</Link></li>
            <li><Link href="/map" className="hover:text-fg">Hotspot map</Link></li>
            <li><Link href="/alerts" className="hover:text-fg">Alerts</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-faint">Resources</p>
          <ul className="mt-3 space-y-2 text-[13.5px] text-muted">
            <li><Link href="/methodology" className="hover:text-fg">Methodology</Link></li>
            <li><a href="/docs" className="hover:text-fg">API reference</a></li>
            <li><a href="https://openaq.org" target="_blank" rel="noreferrer" className="hover:text-fg">OpenAQ</a></li>
            <li><a href="https://open-meteo.com" target="_blank" rel="noreferrer" className="hover:text-fg">Open-Meteo</a></li>
          </ul>
        </div>
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-faint">Data licence</p>
          <p className="mt-3 text-[13px] leading-relaxed text-muted">Measurements © CPCB / MPCB / IITM via OpenAQ (CC BY 4.0). Weather: ERA5 via Open-Meteo (CC BY 4.0).</p>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-5 text-[12.5px] text-faint md:flex-row md:px-6">
          <p>© AirSense · A portfolio project. Not an official air-quality advisory.</p>
          <a href="https://github.com" className="inline-flex items-center gap-1.5 hover:text-fg" target="_blank" rel="noreferrer"><Code2 className="size-4" /> Source</a>
        </div>
      </div>
    </footer>
  );
}
