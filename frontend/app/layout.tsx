import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Greenblatt Web App",
  description: "Deployable web scaffold for the Greenblatt screening platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
