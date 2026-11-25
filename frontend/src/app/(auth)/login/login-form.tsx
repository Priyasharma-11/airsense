"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { Button, Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/hooks";

const schema = z.object({ email: z.email("Enter a valid email address."), password: z.string().min(1, "Enter your password.") });

function safeNext(n: string | null): string {
  return n && n.startsWith("/") && !n.startsWith("//") ? n : "/dashboard";
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const m = useMutation({
    mutationFn: (v: { email: string; password: string }) => api.login(v.email, v.password),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me"] });
      toast.success("Welcome back");
      router.replace(safeNext(params.get("next")));
    },
  });

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const parsed = schema.safeParse({ email: fd.get("email"), password: fd.get("password") });
    if (!parsed.success) {
      setErrors(Object.fromEntries(parsed.error.issues.map((i) => [String(i.path[0]), i.message])));
      return;
    }
    setErrors({});
    m.mutate(parsed.data);
  }

  return (
    <div>
      <h1 className="font-display text-[28px] font-semibold tracking-tight text-fg">Sign in</h1>
      <p className="mt-2 text-sm text-muted">Welcome back. Pick up where the air left off.</p>
      <form onSubmit={submit} noValidate className="mt-8 space-y-4">
        <Field label="Email" htmlFor="email" error={errors.email}>
          <Input id="email" name="email" type="email" autoComplete="email" placeholder="you@example.com" invalid={!!errors.email} autoFocus />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password}>
          <Input id="password" name="password" type="password" autoComplete="current-password" invalid={!!errors.password} />
        </Field>
        <div className="flex justify-end">
          <Link href="/forgot-password" className="text-[13px] font-medium text-brand-600 hover:underline">Forgot password?</Link>
        </div>
        {m.error && <p role="alert" className="rounded-[10px] border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">{errorMessage(m.error)}</p>}
        <Button type="submit" className="w-full" size="lg" loading={m.isPending} icon={!m.isPending && <ArrowRight className="size-4" />}>Sign in</Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        New to AirSense? <Link href="/register" className="font-medium text-brand-600 hover:underline">Create an account</Link>
      </p>
    </div>
  );
}
