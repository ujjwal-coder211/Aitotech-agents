import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Enterprise Dashboard",
  description: "20-25 एजेंट वाली AI business enterprise का control panel",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
