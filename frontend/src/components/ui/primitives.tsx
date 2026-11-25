"use client";

import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import React, { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { ApiError } from "@/lib/api";
import { categoryColor, cn } from "@/lib/format";

/* ------------------------------------------------------------------ Button */
type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";
const variants: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-[0_1px_0_rgb(255_255_255/0.15)_inset,0_1px_2px_rgb(0_0_0/0.12)]",
  secondary: "bg-subtle text-fg hover:bg-inset border border-line",
  outline: "border border-line-strong text-fg hover:bg-subtle",
  ghost: "text-muted hover:text-fg hover:bg-subtle",
  danger: "bg-danger text-white hover:brightness-110",
};
const sizes: Record<Size, string> = { sm: "h-8 px-3 text-[13px] gap-1.5", md: "h-10 px-4 text-sm gap-2", lg: "h-12 px-6 text-[15px] gap-2" };

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button ref={ref} disabled={disabled || loading}
      className={cn("inline-flex items-center justify-center rounded-[10px] font-medium transition-all duration-150",
        "active:scale-[0.98] disabled:opacity-55 disabled:pointer-events-none select-none whitespace-nowrap",
        variants[variant], sizes[size], className)} {...rest}>
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

export function ButtonLink({ href, variant = "primary", size = "md", className, children, icon }: {
  href: string; variant?: Variant; size?: Size; className?: string; children: ReactNode; icon?: ReactNode;
}) {
  return (
    <Link href={href} className={cn("inline-flex items-center justify-center rounded-[10px] font-medium transition-all",
      "active:scale-[0.98]", variants[variant], sizes[size], className)}>
      {children}{icon}
    </Link>
  );
}

/* ------------------------------------------------------------------ Card */
export function Card({ className, children, as: As = "section", ...rest }: { className?: string; children: ReactNode; as?: "section" | "div" | "article" } & Record<string, unknown>) {
  return <As className={cn("rounded-[16px] border border-line bg-elevated shadow-card", className)} {...rest}>{children}</As>;
}

export function CardHeader({ title, subtitle, action, icon }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 px-5 pt-5 pb-3">
      <div className="flex min-w-[min(100%,240px)] flex-1 items-start gap-3">
        {icon && <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-[10px] bg-brand-50 text-brand-600">{icon}</div>}
        <div className="min-w-0">
          <h2 className="font-display text-[15px] font-semibold tracking-tight text-fg">{title}</h2>
          {subtitle && <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Badge */
export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral" | "brand" | "success" | "warning" | "danger" | "info"; className?: string }) {
  const tones = {
    neutral: "bg-subtle text-muted border-line",
    brand: "bg-brand-50 text-brand-700 border-brand-100 dark:text-brand-400",
    success: "bg-green-50 text-green-700 border-green-200 dark:bg-green-950/40 dark:text-green-400 dark:border-green-900",
    warning: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900",
    danger: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900",
    info: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11.5px] font-medium", tones[tone], className)}>{children}</span>;
}

export function AqiBadge({ category, size = "sm" }: { category: string | null | undefined; size?: "sm" | "md" }) {
  if (!category) return <Badge>No data</Badge>;
  const c = categoryColor(category);
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full font-semibold", size === "sm" ? "px-2 py-0.5 text-[11.5px]" : "px-3 py-1 text-[13px]")}
      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 30%, transparent)` }}>
      <span className="size-1.5 rounded-full" style={{ background: c }} aria-hidden />{category}
    </span>
  );
}

/* ------------------------------------------------------------------ Form controls */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return <input ref={ref} aria-invalid={invalid || undefined}
      className={cn("h-10 w-full rounded-[10px] border bg-elevated px-3 text-sm text-fg placeholder:text-faint transition",
        "border-line-strong hover:border-faint focus:border-brand-500 focus:shadow-[var(--ring)] focus:outline-none",
        invalid && "border-danger focus:border-danger", className)} {...rest} />;
  });

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...rest }, ref) {
  return (
    <select ref={ref} className={cn("h-10 rounded-[10px] border border-line-strong bg-elevated px-3 pr-8 text-sm text-fg",
      "focus:border-brand-500 focus:shadow-[var(--ring)] focus:outline-none cursor-pointer appearance-none",
      "bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%237a8898%22 stroke-width=%222.5%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:12px] bg-[right_10px_center] bg-no-repeat",
      className)} {...rest}>{children}</select>
  );
});

export function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-fg">{label}</label>
      {children}
      {error ? <p role="alert" className="text-[12.5px] text-danger">{error}</p> : hint ? <p className="text-[12.5px] text-faint">{hint}</p> : null}
    </div>
  );
}

export function Toggle({ checked, onChange, label, description, id }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string; id: string }) {
  return (
    <div className="flex items-start justify-between gap-6 py-3">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-fg">{label}</label>
        {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
      </div>
      <button id={id} role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cn("relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors", checked ? "bg-brand-600" : "bg-inset border border-line-strong")}>
        <span className={cn("absolute top-0.5 size-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[22px]" : "translate-x-0.5")} />
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ Segmented control */
export function Segmented<T extends string | number>({ value, onChange, options, label, size = "md" }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string; size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[10px] border border-line bg-subtle p-0.5">
      {options.map((o) => (
        <button key={String(o.value)} role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={cn("rounded-[8px] font-medium transition-all", size === "sm" ? "px-2.5 py-1 text-[12px]" : "px-3 py-1.5 text-[13px]",
            o.value === value ? "bg-elevated text-fg shadow-sm" : "text-muted hover:text-fg")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ States */
export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={cn("skeleton", className)} style={style} aria-hidden />;
}

const BAR_HEIGHTS = [38, 52, 46, 61, 72, 58, 66, 80, 74, 62, 55, 68, 77, 59, 48, 53, 64, 44];
export function ChartSkeleton({ height = 280 }: { height?: number }) {
  return (
    <div className="px-5 pb-5" role="status" aria-label="Loading chart">
      <div className="flex items-end gap-2" style={{ height }}>
        {BAR_HEIGHTS.map((h, i) => <Skeleton key={i} className="flex-1" style={{ height: `${h}%` }} />)}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center text-center", compact ? "gap-2 p-4" : "gap-3 p-10")}>
      <div className="grid size-10 place-items-center rounded-full bg-red-50 text-danger dark:bg-red-950/40"><AlertTriangle className="size-5" /></div>
      <div>
        <p className="text-sm font-semibold text-fg">{e?.status === 0 ? "Connection problem" : "Couldn't load this data"}</p>
        <p className="mt-1 max-w-sm text-[13px] text-muted">{e?.message ?? "Something went wrong."}</p>
        {e?.requestId && <p className="mt-1 font-mono text-[11px] text-faint">ref {e.requestId}</p>}
      </div>
      {onRetry && <Button size="sm" variant="secondary" onClick={onRetry} icon={<RefreshCw className="size-3.5" />}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ title, description, action, icon }: { title: string; description?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <div className="grid size-12 place-items-center rounded-2xl border border-line bg-subtle text-faint">{icon ?? <Inbox className="size-5" />}</div>
      <div>
        <p className="text-sm font-semibold text-fg">{title}</p>
        {description && <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ Stat tile */
export function Stat({ label, value, unit, hint, accent, icon }: { label: string; value: ReactNode; unit?: string; hint?: ReactNode; accent?: string; icon?: ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-[16px] border border-line bg-elevated p-4 shadow-card">
      {accent && <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: accent }} />}
      <div className="flex items-center justify-between">
        <p className="text-[12.5px] font-medium text-muted">{label}</p>
        {icon && <span className="text-faint">{icon}</span>}
      </div>
      <p className="mt-2 font-display text-[28px] font-semibold leading-none tracking-tight text-fg tabular">
        {value}{unit && <span className="ml-1 text-[13px] font-medium text-faint">{unit}</span>}
      </p>
      {hint && <div className="mt-2 text-[12.5px] text-muted">{hint}</div>}
    </div>
  );
}

export function PageHeader({ title, description, actions, eyebrow }: { title: string; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && <div className="mb-2">{eyebrow}</div>}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-fg md:text-[28px]">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
