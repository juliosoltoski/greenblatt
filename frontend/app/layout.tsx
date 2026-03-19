import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Greenblatt",
  description: "Research platform for value screening, backtesting, templates, and recurring workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
