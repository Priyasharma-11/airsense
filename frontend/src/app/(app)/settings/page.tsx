"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, SlidersHorizontal, Trash2, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { StationSelect } from "@/components/aq/widgets";
import { ThemeToggle } from "@/components/layout/brand";
import { useTheme } from "@/components/providers";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button, Card, CardHeader, ErrorState, Field, Input, PageHeader, Skeleton, Toggle } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { errorMessage, useMe, usePreferences, useStations } from "@/lib/hooks";
import type { Preferences, User } from "@/lib/types";

export default function SettingsPage() {
  const me = useMe();
  const prefsQ = usePreferences();
  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" description="Personalise thresholds, default station and notifications." />
      <div className="space-y-4">
        <Card>
          <CardHeader title="Air-quality preferences" icon={<SlidersHorizontal className="size-4" />} subtitle="Used across the dashboard, forecasts and new alert rules" />
          {prefsQ.error ? <ErrorState compact error={prefsQ.error} onRetry={() => prefsQ.refetch()} /> :
            !prefsQ.data ? <div className="px-5 pb-5"><Skeleton className="h-40" /></div> :
              <PreferencesForm key={JSON.stringify(prefsQ.data)} initial={prefsQ.data} />}
        </Card>
        {me.data && <ProfileForm key={me.data.full_name} user={me.data} />}
        <PasswordForm />
        <DangerZone />
      </div>
    </div>
  );
}

function PreferencesForm({ initial }: { initial: Preferences }) {
  const qc = useQueryClient();
  const stations = useStations();
  const { theme, setTheme } = useTheme();
  const [prefs, setPrefs] = useState(initial);
  const save = useMutation({
    mutationFn: (p: Preferences) => api.savePreferences(p),
    onSuccess: (p) => { qc.setQueryData(["preferences"], p); qc.invalidateQueries({ queryKey: ["forecast"] }); setTheme(p.theme); toast.success("Preferences saved"); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="space-y-4 px-5 pb-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Default station" htmlFor="pref-station"><StationSelect id="pref-station" stations={stations.data} value={prefs.default_station_id ?? undefined} onChange={(id) => setPrefs({ ...prefs, default_station_id: id })} className="w-full" /></Field>
        <Field label="Personal PM2.5 threshold (µg/m³)" htmlFor="pref-thr" hint="NAAQS 24-h standard is 60; WHO guideline is 15">
          <Input id="pref-thr" type="number" min={1} max={500} value={prefs.pm25_threshold} onChange={(e) => setPrefs({ ...prefs, pm25_threshold: Number(e.target.value) })} />
        </Field>
      </div>
      <div className="divide-y divide-line border-y border-line">
        <Toggle id="sens" label="I belong to a sensitive group" description="Children, older adults, people with asthma, COPD or heart disease" checked={prefs.sensitive_group}
          onChange={(v) => setPrefs({ ...prefs, sensitive_group: v, pm25_threshold: v && prefs.pm25_threshold > 45 ? 45 : prefs.pm25_threshold })} />
        <Toggle id="inapp" label="In-app notifications" checked={prefs.notify_in_app} onChange={(v) => setPrefs({ ...prefs, notify_in_app: v })} />
        <Toggle id="email" label="E-mail notifications" description="Requires SMTP to be configured on the server" checked={prefs.notify_email} onChange={(v) => setPrefs({ ...prefs, notify_email: v })} />
      </div>
      <div className="flex items-center justify-between">
        <div><p className="text-sm font-medium">Appearance</p><p className="text-[13px] text-muted">Light, dark or follow your system</p></div>
        <ThemeToggle />
      </div>
      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={() => {
          if (!(prefs.pm25_threshold > 0 && prefs.pm25_threshold <= 500)) return toast.error("Threshold must be between 1 and 500 µg/m³.");
          save.mutate({ ...prefs, theme });
        }}>Save preferences</Button>
      </div>
    </div>
  );
}

function ProfileForm({ user }: { user: User }) {
  const qc = useQueryClient();
  const [name, setName] = useState(user.full_name);
  const save = useMutation({ mutationFn: () => api.updateMe(name), onSuccess: (u) => { qc.setQueryData(["me"], u); toast.success("Profile updated"); }, onError: (e) => toast.error(errorMessage(e)) });
  return (
    <Card>
      <CardHeader title="Profile" icon={<UserRound className="size-4" />} subtitle={user.email} />
      <form className="flex flex-col gap-3 px-5 pb-5 sm:flex-row sm:items-end" onSubmit={(e) => { e.preventDefault(); if (name.trim().length >= 2) save.mutate(); else toast.error("Name must be at least 2 characters."); }}>
        <div className="flex-1"><Field label="Full name" htmlFor="name"><Input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></Field></div>
        <Button type="submit" variant="secondary" loading={save.isPending}>Update</Button>
      </form>
    </Card>
  );
}

function PasswordForm() {
  const [err, setErr] = useState<string>();
  const change = useMutation({
    mutationFn: (v: { cur: string; next: string }) => api.changePassword(v.cur, v.next),
    onSuccess: () => { toast.success("Password changed"); setErr(undefined); },
    onError: (e) => setErr(errorMessage(e)),
  });
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const cur = String(fd.get("current") ?? ""), next = String(fd.get("next") ?? "");
    if (next.length < 8 || !/[A-Za-z]/.test(next) || !/\d/.test(next)) return setErr("New password must have 8+ characters, a letter and a number.");
    change.mutate({ cur, next }, { onSuccess: () => form.reset() });
  }
  return (
    <Card>
      <CardHeader title="Password" icon={<KeyRound className="size-4" />} />
      <form onSubmit={submit} className="grid gap-3 px-5 pb-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end" noValidate>
        <Field label="Current password" htmlFor="current"><Input id="current" name="current" type="password" autoComplete="current-password" /></Field>
        <Field label="New password" htmlFor="next"><Input id="next" name="next" type="password" autoComplete="new-password" /></Field>
        <Button type="submit" variant="secondary" loading={change.isPending}>Change</Button>
        {err && <p role="alert" className="text-[13px] text-danger sm:col-span-3">{err}</p>}
      </form>
    </Card>
  );
}

function DangerZone() {
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const del = useMutation({ mutationFn: api.deleteAccount, onSuccess: () => { qc.clear(); toast.success("Account deleted"); router.replace("/"); }, onError: (e) => toast.error(errorMessage(e)) });
  return (
    <>
      <Card className="border-red-200 dark:border-red-900/60">
        <CardHeader title="Delete account" icon={<Trash2 className="size-4" />} subtitle="Permanently removes your account, preferences, alert rules and alert history." />
        <div className="px-5 pb-5"><Button variant="danger" onClick={() => setOpen(true)}>Delete my account</Button></div>
      </Card>
      <ConfirmDialog open={open} onOpenChange={(o) => { setOpen(o); setText(""); }} title="Delete your account?" confirmLabel="Delete permanently"
        loading={del.isPending} onConfirm={() => (text === "DELETE" ? del.mutate() : toast.error("Type DELETE to confirm"))}
        description="This cannot be undone. Type DELETE to confirm.">
        <Input aria-label="Type DELETE to confirm" className="mt-4" value={text} onChange={(e) => setText(e.target.value)} placeholder="DELETE" />
      </ConfirmDialog>
    </>
  );
}
