import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local AI Platform",
  description: "Private, locally hosted document intelligence and chat.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
