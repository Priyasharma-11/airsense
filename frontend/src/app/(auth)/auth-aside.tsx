"use client";

import { motion } from "framer-motion";
import { Activity, MapPinned, ShieldCheck } from "lucide-react";
import { categoryColor, fmt, shortStation } from "@/lib/format";
import { useCurrent } from "@/lib/hooks";

export function AuthAside() {
  const { data } = useCurrent();
  const top = data?.stations.filter((s) => s.pm25 !== null).sort((a, b) => (b.pm25 ?? 0) - (a.pm25 ?? 0)).slice(0, 4) ?? [];
  return (
    <aside className="relative hidden overflow-hidden bg-[#050b14] lg:block">
      <div className="bg-grid absolute inset-0 opacity-60" />
      <div className="absolute -right-32 -top-32 size-[520px] rounded-full bg-brand-500/25 blur-[120px]" />
      <div className="absolute -bottom-40 left-10 size-[420px] rounded-full bg-sky-500/20 blur-[120px]" />
      <div className="relative flex h-full flex-col justify-between p-12 text-white">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-brand-400">Environmental intelligence</p>
          <h2 className="mt-4 max-w-md font-display text-[34px] font-semibold leading-[1.12] tracking-tight">
            See tomorrow&apos;s air before you breathe it.
          </h2>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-slate-300">
            24-hour PM2.5 forecasts for Pune&apos;s monitoring network, with calibrated uncertainty and plain-language explanations.
          </p>
        </div>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="rounded-[20px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur">
          <div className="flex items-center justify-between text-[12px] text-slate-400">
            <span>Most polluted stations right now</span>
            <span className="tabular">{data ? fmt.dateTime(data.summary.observed_at) : "loading…"}</span>
          </div>
          <ul className="mt-3 space-y-2.5">
            {top.map((s) => (
              <li key={s.station.id} className="flex items-center gap-3">
                <span className="size-2 rounded-full" style={{ background: categoryColor(s.category) }} />
                <span className="flex-1 truncate text-[14px] text-slate-200">{shortStation(s.station.name)}</span>
                <span className="font-display text-[15px] font-semibold tabular">{fmt.num(s.pm25)}</span>
                <span className="w-14 text-right text-[11px] text-slate-400">µg/m³</span>
              </li>
            ))}
            {!data && [0, 1, 2, 3].map((i) => <li key={i} className="h-5 rounded bg-white/5" />)}
          </ul>
        </motion.div>
        <div className="grid grid-cols-3 gap-4 text-[12.5px] text-slate-300">
          <div className="flex items-center gap-2"><Activity className="size-4 text-brand-400" /> Real station data</div>
          <div className="flex items-center gap-2"><MapPinned className="size-4 text-brand-400" /> 10 monitors</div>
          <div className="flex items-center gap-2"><ShieldCheck className="size-4 text-brand-400" /> No fake numbers</div>
        </div>
      </div>
    </aside>
  );
}
