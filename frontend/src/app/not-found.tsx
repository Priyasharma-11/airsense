import Link from "next/link";

export default function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center px-6">
      <div className="text-center">
        <p className="font-display text-[64px] font-semibold leading-none text-brand-500">404</p>
        <h1 className="mt-3 font-display text-2xl font-semibold">This page drifted away</h1>
        <p className="mt-2 text-muted">The page you&apos;re looking for doesn&apos;t exist or was moved.</p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/" className="rounded-[10px] bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Home</Link>
          <Link href="/dashboard" className="rounded-[10px] border border-line-strong px-4 py-2 text-sm font-medium hover:bg-subtle">Dashboard</Link>
        </div>
      </div>
    </div>
  );
}
