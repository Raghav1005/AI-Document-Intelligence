import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./providers";

export const metadata: Metadata = {
  title: "Local AI Platform",
  description: "Private, locally hosted document intelligence and chat.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider
          url={process.env.KEYCLOAK_PUBLIC_URL ?? "http://localhost:8080"}
          realm={process.env.KEYCLOAK_REALM ?? "local-ai"}
          clientId={process.env.KEYCLOAK_CLIENT_ID ?? "local-ai-frontend"}
        >
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
