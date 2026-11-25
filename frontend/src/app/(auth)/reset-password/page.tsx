"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { Button, ButtonLink, EmptyState, Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/hooks";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [error, setError] = useState<string>();
  const m = useMutation({ mutationFn: (pw: string) => api.resetPassword(token, pw) });

  if (!token) {
    return <EmptyState title="Missing reset token" description="Open the link from your email, or request a new one."
      action={<ButtonLink href="/forgot-password" variant="secondary" size="sm">Request a new link</ButtonLink>} />;
  }
  if (m.isSuccess) {
    return (
      <div className="text-center">
        <CheckCircle2 className="mx-auto size-12 text-brand-500" />
        <h1 className="mt-4 font-display text-2xl font-semibold text-fg">Password updated</h1>
        <p className="mt-2 text-sm text-muted">{m.data.message}</p>
        <ButtonLink href="/login" className="mt-6">Sign in</ButtonLink>
      </div>
    );
  }

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const pw = String(fd.get("password") ?? "");
    const confirm = String(fd.get("confirm") ?? "");
    if (pw.length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return setError("Password must have 8+ characters, a letter and a number.");
    if (pw !== confirm) return setError("Passwords do not match.");
    setError(undefined);
    m.mutate(pw);
  }

  return (
    <div>
      <h1 className="font-display text-[28px] font-semibold tracking-tight text-fg">Choose a new password</h1>
      <p className="mt-2 text-sm text-muted">This link can be used once.</p>
      <form onSubmit={submit} noValidate className="mt-8 space-y-4">
        <Field label="New password" htmlFor="password" error={error}>
          <Input id="password" name="password" type="password" autoComplete="new-password" invalid={!!error} autoFocus />
        </Field>
        <Field label="Confirm password" htmlFor="confirm">
          <Input id="confirm" name="confirm" type="password" autoComplete="new-password" />
        </Field>
        {m.error && <p role="alert" className="text-[13px] text-danger">{errorMessage(m.error)}</p>}
        <Button type="submit" className="w-full" size="lg" loading={m.isPending}>Update password</Button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return <Suspense><ResetForm /></Suspense>;
}
