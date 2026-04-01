import type { Metadata } from "next";
import "./globals.css";
import { ClientBootstrap } from "./components/client-bootstrap";

export const metadata: Metadata = {
  title: "股票投研交易助手",
  description: "面向个人投资者的本地化股票分析、推荐、回测与交易辅助系统",
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
        {children}
      </body>
    </html>
  );
}
