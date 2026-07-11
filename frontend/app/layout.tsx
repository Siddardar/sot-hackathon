import type { Metadata } from "next";
import { Inter, Fraunces } from "next/font/google";
import { GlassBackdrop } from "./components/GlassBackdrop";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Glasshouse — Your words say more than you meant",
  description:
    "Glasshouse analyzes your LLM conversations and surfaces what an AI could infer about you — income, health, relationships — so you stay in control of what you give away.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background font-sans text-ink">
        <GlassBackdrop />
        {children}
      </body>
    </html>
  );
}
