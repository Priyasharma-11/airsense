import type { Metadata, Viewport } from "next";
import { Inter, Sora } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const sora = Sora({ subsets: ["latin"], variable: "--font-sora", display: "swap", weight: ["500", "600", "700"] });

export const metadata: Metadata = {
  title: { default: "AirSense - Air-quality intelligence for Pune", template: "%s · AirSense" },
  description: "Monitor, analyse and forecast PM2.5 across Pune with open data and machine learning.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f6f8fa" }, { media: "(prefers-color-scheme: dark)", color: "#070d16" }],
};

// Applies the stored/system theme before first paint to avoid a flash of the wrong theme.
const themeScript = `try{var t=localStorage.getItem('airsense-theme')||'system';var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);if(d)document.documentElement.classList.add('dark')}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${sora.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
