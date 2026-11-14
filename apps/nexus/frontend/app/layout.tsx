import type { Metadata, Viewport } from "next";
import { JetBrains_Mono, Space_Grotesk, Vazirmatn } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

const sans = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

const persian = Vazirmatn({
  subsets: ["arabic"],
  variable: "--font-fa",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ADAN NEXUS | CONNECT",
  description:
    "Connectivity Intelligence and Subscription Management Platform. Source registry, configuration provenance, health testing and subscription exports.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#080A0B",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <body className={`${sans.variable} ${mono.variable} ${persian.variable} font-sans`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
