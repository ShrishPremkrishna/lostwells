import type { Metadata } from "next";
import { Playfair_Display, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// uidesign.md §3: Playfair Display (editorial headers), Inter (functional body),
// JetBrains Mono (coordinates / IDs / agent feed — "makes data feel like data").
const display = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Finding the Lost Wells of Appalachia",
  description:
    "We ran a U-Net over historical USGS topographic maps and found 36,919 undocumented orphaned oil & gas wells across Appalachia — then ranked them by who lives on top of them and mapped a path to plug them.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
