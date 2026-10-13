import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "WattWise · Home energy", description: "Plan, review, and approve simulated EV charging with real MCP optimization." };
export default function Layout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
