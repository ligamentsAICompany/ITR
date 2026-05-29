import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ITR AI System",
  description: "Deterministic ITR classification and agent clarification UI",
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
