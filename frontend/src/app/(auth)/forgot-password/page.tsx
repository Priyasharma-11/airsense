"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, MailCheck } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { Button, ButtonLink, Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/hooks";

export default function ForgotPasswordPage() {
  const [error, setError] = useState<string>();
  const m = useMutation({ mutationFn: (email: string) => api.forgotPassword(email) });

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = new FormData(e.currentTarget).get("email");
    const r = z.email().safeParse(email);
    if (!r.success) return setError("Enter a valid email address.");
    setError(undefined);
    m.mutate(r.data);
  }

  if (m.isSuccess) {
    return (
      <div className="text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-600"><MailCheck className="size-6" /></div>
        <h1 className="mt-5 font-display text-2xl font-semibold text-fg">Check your inbox</h1>
        <p className="mt-2 text-sm text-muted">{m.data.message} The link expires in 30 minutes.</p>
        {m.data.dev_reset_token && (
          <div className="mt-5 rounded-[12px] border border-amber-200 bg-amber-50 p-3 text-left text-[12.5px] text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
            <p className="font-semibold">Development mode - e-mail delivery is not configured.</p>
            <Link className="mt-1 inline-block font-medium underline" href={`/reset-password?token=${encodeURIComponent(m.data.dev_reset_token)}`}>Open the reset link</Link>
          </div>
        )}
        <ButtonLink href="/login" variant="secondary" className="mt-6">Back to sign in</ButtonLink>
      </div>
    );
  }

  return (
    <div>
      <Link href="/login" className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg"><ArrowLeft className="size-3.5" /> Back to sign in</Link>
      <h1 className="font-display text-[28px] font-semibold tracking-tight text-fg">Reset your password</h1>
      <p className="mt-2 text-sm text-muted">Enter the email you registered with and we&apos;ll send a secure, single-use reset link.</p>
      <form onSubmit={submit} noValidate className="mt-8 space-y-4">
        <Field label="Email" htmlFor="email" error={error}>
          <Input id="email" name="email" type="email" autoComplete="email" invalid={!!error} autoFocus />
        </Field>
        {m.error && <p role="alert" className="text-[13px] text-danger">{errorMessage(m.error)}</p>}
        <Button type="submit" className="w-full" size="lg" loading={m.isPending}>Send reset link</Button>
      </form>
    </div>
  );
}
