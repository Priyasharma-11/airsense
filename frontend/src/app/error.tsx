"use client";

import { AlertTriangle } from "lucide-react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="grid min-h-[60dvh] place-items-center px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto grid size-12 place-items-center rounded-full bg-red-50 text-danger dark:bg-red-950/40"><AlertTriangle className="size-6" /></div>
        <h1 className="mt-4 font-display text-xl font-semibold">Something went wrong</h1>
        <p className="mt-2 text-sm text-muted">An unexpected error occurred while rendering this page.{error.digest && <> Reference: <code>{error.digest}</code></>}</p>
        <button onClick={reset} className="mt-5 rounded-[10px] bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Try again</button>
      </div>
    </div>
  );
}
