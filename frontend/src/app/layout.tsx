import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { AuthMenu } from "@/components/AuthMenu";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Orbiter",
  description: "Review large GitHub pull requests without losing your place.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex h-full flex-col font-sans">
        <nav className="flex h-11 shrink-0 items-center border-b border-border px-4">
          <Link href="/" className="font-semibold">
            Orbiter
          </Link>
          <div className="ml-auto">
            <AuthMenu />
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
