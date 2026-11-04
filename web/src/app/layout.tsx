import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense, type ReactNode } from "react";
import { ToastFromQuery } from "@/components/ToastFromQuery";
import { ToastProvider } from "@/components/ui";
import "@/styles/globals.css";

// Self-hosted at build time by next/font — no request to Google from a learner's browser.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Nidan", template: "%s · Nidan" },
  description: "Practise clinical reasoning and track how you improve.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB" className={inter.variable}>
      <body>
        <ToastProvider>
          {children}
          <Suspense><ToastFromQuery /></Suspense>
        </ToastProvider>
      </body>
    </html>
  );
}
