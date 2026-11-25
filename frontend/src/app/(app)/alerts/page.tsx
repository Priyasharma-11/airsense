"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, BellOff, CheckCheck, Eye, Plus, Radar, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { StationSelect } from "@/components/aq/widgets";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, Field, Input, PageHeader, Segmented, Select, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { categoryColor, cn, fmt, shortStation } from "@/lib/format";
import { errorMessage, useStations } from "@/lib/hooks";
import type { Alert, AlertRule } from "@/lib/types";

export default function AlertsPage() {
  const qc = useQueryClient();
  const stations = useStations();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<{ kind: "rule"; item: AlertRule } | { kind: "alert"; item: Alert } | null>(null);

  const alerts = useQuery({ queryKey: ["alerts", filter, page], queryFn: () => api.alerts({ unread_only: filter === "unread", page, page_size: 10 }) });
  const rules = useQuery({ queryKey: ["rules"], queryFn: api.rules });
  const invalidate = () => { qc.invalidateQueries({ queryKey: ["alerts"] }); qc.invalidateQueries({ queryKey: ["unread"] }); };

  const evaluate = useMutation({
    mutationFn: api.evaluate,
    onSuccess: (r) => { invalidate(); toast.success(r.alerts_created ? `${r.alerts_created} new alert${r.alerts_created > 1 ? "s" : ""} from ${r.rules_evaluated} rule(s)` : `Checked ${r.rules_evaluated} rule(s) - no new alerts`); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const readAll = useMutation({ mutationFn: api.readAll, onSuccess: (r) => { invalidate(); toast.success(r.message); } });
  const markRead = useMutation({ mutationFn: api.markRead, onSuccess: invalidate });
  const toggleRule = useMutation({
    mutationFn: (r: AlertRule) => api.updateRule(r.id, { is_active: !r.is_active }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["rules"] }); toast.success(`Rule ${r.is_active ? "enabled" : "paused"}`); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const del = useMutation({
    mutationFn: async () => {
      if (!confirm) return;
      if (confirm.kind === "rule") await api.deleteRule(confirm.item.id);
      else await api.deleteAlert(confirm.item.id);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules"] }); invalidate(); toast.success(confirm?.kind === "rule" ? "Alert rule deleted" : "Alert deleted"); setConfirm(null); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div>
      <PageHeader title="Alerts & notifications" description="Rules fire when the forecast probability of exceeding your threshold passes your confidence level, or when an observation already exceeds it."
        actions={<Button onClick={() => evaluate.mutate()} loading={evaluate.isPending} icon={<Radar className="size-4" />} disabled={!rules.data?.length}>Check rules now</Button>} />

      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          <NewRuleCard stations={stations.data} onCreated={() => qc.invalidateQueries({ queryKey: ["rules"] })} />
          <Card>
            <CardHeader title="Your rules" subtitle={rules.data ? `${rules.data.length} of 20` : undefined} icon={<Bell className="size-4" />} />
            {rules.isLoading ? <div className="space-y-2 px-5 pb-5">{[0, 1].map((i) => <Skeleton key={i} className="h-16" />)}</div> :
              rules.error ? <ErrorState compact error={rules.error} onRetry={() => rules.refetch()} /> :
                rules.data?.length ? (
                  <ul className="space-y-2 px-4 pb-4">
                    {rules.data.map((r) => (
                      <li key={r.id} className={cn("rounded-[12px] border border-line p-3 transition", !r.is_active && "opacity-60")}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-[13.5px] font-semibold text-fg">{r.name}</p>
                            <p className="text-[12px] text-muted">{shortStation(r.station.name)}</p>
                          </div>
                          <div className="flex shrink-0 gap-1">
                            <button onClick={() => toggleRule.mutate(r)} aria-label={r.is_active ? `Pause ${r.name}` : `Enable ${r.name}`} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-subtle hover:text-fg">
                              {r.is_active ? <Bell className="size-4" /> : <BellOff className="size-4" />}
                            </button>
                            <button onClick={() => setConfirm({ kind: "rule", item: r })} aria-label={`Delete ${r.name}`} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-red-50 hover:text-danger dark:hover:bg-red-950/40"><Trash2 className="size-4" /></button>
                          </div>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <Badge>&gt; {r.threshold} µg/m³</Badge><Badge>next {r.lookahead_hours} h</Badge><Badge>≥ {Math.round(r.min_probability * 100)}% likely</Badge>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : <EmptyState title="No rules yet" description="Create your first rule above to start receiving alerts." icon={<Bell className="size-5" />} />}
          </Card>
        </div>

        <Card>
          <CardHeader title="Alert history" icon={<Bell className="size-4" />}
            action={<div className="flex items-center gap-2">
              <Segmented size="sm" label="Filter" value={filter} onChange={(v) => { setFilter(v); setPage(1); }} options={[{ value: "all", label: "All" }, { value: "unread", label: "Unread" }]} />
              <Button size="sm" variant="secondary" onClick={() => readAll.mutate()} loading={readAll.isPending} icon={<CheckCheck className="size-3.5" />}>Mark all read</Button>
            </div>} />
          {alerts.isLoading ? <div className="space-y-2 px-5 pb-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div> :
            alerts.error ? <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} /> :
              !alerts.data?.items.length ? (
                <EmptyState title={filter === "unread" ? "You're all caught up" : "No alerts yet"} icon={<Bell className="size-5" />}
                  description={filter === "unread" ? "No unread alerts." : rules.data?.length ? "Run “Check rules now” to evaluate your rules against the latest forecast." : "Create a rule, then check it against the latest forecast."} />
              ) : (
                <>
                  <ul className="space-y-2 px-4 pb-2">
                    <AnimatePresence initial={false}>
                      {alerts.data.items.map((a) => (
                        <motion.li key={a.id} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                          className={cn("group relative rounded-[14px] border p-4 pl-5", a.is_read ? "border-line" : "border-line-strong bg-subtle/60")}>
                          <span className="absolute inset-y-3 left-0 w-1 rounded-full" style={{ background: categoryColor(a.severity) }} />
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                {!a.is_read && <span className="size-2 rounded-full bg-brand-500" aria-label="Unread" />}
                                <p className="text-[14px] font-semibold text-fg">{a.title}</p>
                                <Badge tone={a.kind === "forecast_exceedance" ? "info" : "warning"}>{a.kind === "forecast_exceedance" ? "Forecast" : "Observed"}</Badge>
                              </div>
                              <p className="mt-1 text-[13px] leading-relaxed text-muted">{a.message}</p>
                              <p className="mt-2 text-[11.5px] text-faint">Created {fmt.dateTime(a.created_at)} · for {fmt.dateTime(a.target_time)}</p>
                            </div>
                            <div className="flex shrink-0 gap-1 opacity-100 md:opacity-0 md:transition md:group-hover:opacity-100 md:focus-within:opacity-100">
                              {!a.is_read && <button onClick={() => markRead.mutate(a.id)} aria-label="Mark as read" className="grid size-8 place-items-center rounded-lg text-muted hover:bg-elevated hover:text-fg"><Eye className="size-4" /></button>}
                              <button onClick={() => setConfirm({ kind: "alert", item: a })} aria-label="Delete alert" className="grid size-8 place-items-center rounded-lg text-muted hover:bg-red-50 hover:text-danger dark:hover:bg-red-950/40"><Trash2 className="size-4" /></button>
                            </div>
                          </div>
                        </motion.li>
                      ))}
                    </AnimatePresence>
                  </ul>
                  <div className="flex items-center justify-between px-5 pb-4 pt-2 text-[13px] text-muted">
                    <span>{alerts.data.total} alert{alerts.data.total === 1 ? "" : "s"}</span>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                      <span className="tabular">{page} / {alerts.data.pages}</span>
                      <Button size="sm" variant="secondary" disabled={page >= alerts.data.pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
                    </div>
                  </div>
                </>
              )}
        </Card>
      </div>

      <ConfirmDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)} loading={del.isPending} onConfirm={() => del.mutate()}
        title={confirm?.kind === "rule" ? "Delete alert rule?" : "Delete alert?"} confirmLabel="Delete"
        description={confirm?.kind === "rule" ? <>“{confirm.item.name}” will stop monitoring {shortStation(confirm.item.station.name)}. Past alerts are kept.</> : "This alert will be removed from your history."} />
    </div>
  );
}

function NewRuleCard({ stations, onCreated }: { stations: ReturnType<typeof useStations>["data"]; onCreated: () => void }) {
  const [station, setStation] = useState<number>();
  const [name, setName] = useState("");
  const [threshold, setThreshold] = useState(60);
  const [lookahead, setLookahead] = useState(24);
  const [prob, setProb] = useState(0.5);
  const [error, setError] = useState<string>();
  const sid = station ?? stations?.find((s) => s.used_in_model)?.id;
  const m = useMutation({
    mutationFn: () => api.createRule({ station_id: sid!, name: name.trim() || `PM2.5 > ${threshold}`, threshold, lookahead_hours: lookahead, min_probability: prob, is_active: true }),
    onSuccess: () => { onCreated(); setName(""); toast.success("Alert rule created"); },
    onError: (e) => setError(errorMessage(e)),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!sid) return setError("Choose a station.");
    if (!(threshold > 0 && threshold <= 500)) return setError("Threshold must be between 1 and 500 µg/m³.");
    setError(undefined);
    m.mutate();
  }
  return (
    <Card>
      <CardHeader title="New alert rule" icon={<Plus className="size-4" />} />
      <form onSubmit={submit} className="space-y-3 px-5 pb-5" noValidate>
        <Field label="Station" htmlFor="rule-station"><StationSelect id="rule-station" stations={stations} value={sid} onChange={setStation} className="w-full" /></Field>
        <Field label="Name (optional)" htmlFor="rule-name"><Input id="rule-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="e.g. Kids' school run" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Threshold (µg/m³)" htmlFor="rule-thr"><Input id="rule-thr" type="number" min={1} max={500} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} /></Field>
          <Field label="Look-ahead" htmlFor="rule-la">
            <Select id="rule-la" value={lookahead} onChange={(e) => setLookahead(Number(e.target.value))} className="w-full">
              {[3, 6, 12, 24].map((h) => <option key={h} value={h}>Next {h} h</option>)}
            </Select>
          </Field>
        </div>
        <Field label={`Minimum confidence: ${Math.round(prob * 100)}%`} htmlFor="rule-p" hint="Lower = earlier warnings but more false alarms">
          <input id="rule-p" type="range" min={0.1} max={0.9} step={0.05} value={prob} onChange={(e) => setProb(Number(e.target.value))} className="w-full accent-[var(--brand-600)]" />
        </Field>
        {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
        <Button type="submit" className="w-full" loading={m.isPending}>Create rule</Button>
      </form>
    </Card>
  );
}
