import type { Metadata } from "next";
import "./globals.css";
import "./shell-v2.css";
import { AppShell } from "./components/app-shell";
import { ClientBootstrap } from "./components/client-bootstrap";

export const metadata: Metadata = {
  title: "AIStock Research · 智能投研终端",
  description: "A股研究、风险识别、候选池分析与可复现策略验证",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icon-512.svg",
    apple: "/icon-192.svg"
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <ClientBootstrap />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
