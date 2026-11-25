"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { useTheme } from "@/components/providers";
import { cn } from "@/lib/format";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden>
      <defs>
        <linearGradient id="as-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2dd4b4" />
          <stop offset="1" stopColor="#0a7f8f" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#as-g)" />
      <path d="M7 19.5c2.4 0 2.4-2.5 4.8-2.5s2.4 2.5 4.8 2.5 2.4-2.5 4.8-2.5 2.4 2.5 3.6 2.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
      <path d="M7 13.5c2.4 0 2.4-2.5 4.8-2.5s2.4 2.5 4.8 2.5 2.4-2.5 4.8-2.5 2.4 2.5 3.6 2.5" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ href = "/", inverted }: { href?: string; inverted?: boolean }) {
  return (
    <Link href={href} className="flex items-center gap-2.5" aria-label="AirSense home">
      <LogoMark />
      <span className={cn("font-display text-[17px] font-semibold tracking-tight", inverted ? "text-white" : "text-fg")}>
        Air<span className="text-brand-500">Sense</span>
      </span>
    </Link>
  );
}

export function ThemeToggle({ compact }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();
  const opts = [
    { v: "light" as const, icon: Sun, label: "Light theme" },
    { v: "dark" as const, icon: Moon, label: "Dark theme" },
    { v: "system" as const, icon: Monitor, label: "System theme" },
  ];
  if (compact) {
    const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
    const Icon = opts.find((o) => o.v === theme)!.icon;
    return (
      <button onClick={() => setTheme(next)} aria-label={`Theme: ${theme}. Switch to ${next}`}
        className="grid size-9 place-items-center rounded-[10px] text-muted transition hover:bg-subtle hover:text-fg">
        <Icon className="size-[18px]" />
      </button>
    );
  }
  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-[10px] border border-line bg-subtle p-0.5">
      {opts.map(({ v, icon: Icon, label }) => (
        <button key={v} role="radio" aria-checked={theme === v} aria-label={label} onClick={() => setTheme(v)}
          className={cn("grid size-7 place-items-center rounded-[8px] transition", theme === v ? "bg-elevated text-fg shadow-sm" : "text-faint hover:text-fg")}>
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}
