import type { ReactNode } from "react";
import { AuthAside } from "./auth-aside";
import { Logo } from "@/components/layout/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1.05fr]">
      <div className="flex flex-col px-5 py-6 sm:px-10">
        <Logo />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[400px]">{children}</div>
        </div>
        <p className="text-[12px] text-faint">Data: CPCB · MPCB · IITM via OpenAQ (CC BY 4.0)</p>
      </div>
      <AuthAside />
    </div>
  );
}
