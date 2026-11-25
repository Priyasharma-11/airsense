"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { Button, Field, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/format";
import { errorMessage } from "@/lib/hooks";

const passwordRules = [
  { test: (p: string) => p.length >= 8, label: "8+ characters" },
  { test: (p: string) => /[A-Za-z]/.test(p), label: "A letter" },
  { test: (p: string) => /\d/.test(p), label: "A number" },
];

const schema = z.object({
  full_name: z.string().trim().min(2, "Enter your name (at least 2 characters).").max(120),
  email: z.email("Enter a valid email address."),
  password: z.string().refine((p) => passwordRules.every((r) => r.test(p)), "Password must have 8+ characters, a letter and a number."),
});

export default function RegisterPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [pw, setPw] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const m = useMutation({
    mutationFn: async (v: z.infer<typeof schema>) => {
      await api.register(v.email, v.full_name, v.password);
      await api.login(v.email, v.password);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me"] });
      toast.success("Account created - welcome to AirSense");
      router.replace("/dashboard");
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) setErrors({ email: e.message });
    },
  });

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const parsed = schema.safeParse({ full_name: fd.get("full_name"), email: fd.get("email"), password: fd.get("password") });
    if (!parsed.success) {
      setErrors(Object.fromEntries(parsed.error.issues.map((i) => [String(i.path[0]), i.message])));
      return;
    }
    setErrors({});
    m.mutate(parsed.data);
  }

  return (
    <div>
      <h1 className="font-display text-[28px] font-semibold tracking-tight text-fg">Create your account</h1>
      <p className="mt-2 text-sm text-muted">Free, private and built on open data. Set alerts for the stations you care about.</p>
      <form onSubmit={submit} noValidate className="mt-8 space-y-4">
        <Field label="Full name" htmlFor="full_name" error={errors.full_name}>
          <Input id="full_name" name="full_name" autoComplete="name" invalid={!!errors.full_name} autoFocus />
        </Field>
        <Field label="Email" htmlFor="email" error={errors.email}>
          <Input id="email" name="email" type="email" autoComplete="email" invalid={!!errors.email} />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password}>
          <Input id="password" name="password" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} invalid={!!errors.password} aria-describedby="pw-rules" />
        </Field>
        <ul id="pw-rules" className="flex flex-wrap gap-2" aria-label="Password requirements">
          {passwordRules.map((r) => {
            const ok = r.test(pw);
            return (
              <li key={r.label} className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[12px]", ok ? "border-brand-100 bg-brand-50 text-brand-700 dark:text-brand-400" : "border-line text-faint")}>
                <Check className={cn("size-3", ok ? "opacity-100" : "opacity-30")} />{r.label}
              </li>
            );
          })}
        </ul>
        {m.error && !(m.error instanceof ApiError && m.error.status === 409) && (
          <p role="alert" className="rounded-[10px] border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">{errorMessage(m.error)}</p>
        )}
        <Button type="submit" className="w-full" size="lg" loading={m.isPending}>Create account</Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">Already have an account? <Link href="/login" className="font-medium text-brand-600 hover:underline">Sign in</Link></p>
    </div>
  );
}
