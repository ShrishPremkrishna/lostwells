"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
];

// uidesign.md §4.1: a dark "field-survey" strip across the top — wordmark left,
// nav right, a 1px accent bottom border, no shadow, zero radius.
export function TopBar() {
  const pathname = usePathname();
  return (
    <header
      className="relative z-40 flex h-12 shrink-0 items-center justify-between border-b px-5"
      style={{
        background: "var(--color-ink)",
        borderColor: "rgba(74,124,89,0.4)",
      }}
    >
      <Link href="/" className="flex items-center gap-2.5">
        <span className="h-2.5 w-2.5" style={{ background: "var(--color-accent)" }} />
        <span className="font-display text-[17px] leading-none text-[#f5f5f5]">
          Finding the Lost Wells of Appalachia
        </span>
      </Link>

      <nav className="flex items-center gap-1 text-[11px] uppercase tracking-[0.08em]">
        {NAV.map((n) => {
          const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              className="px-3 py-1.5 transition-colors"
              style={{
                color: active ? "#f5f5f5" : "var(--color-mid)",
                background: active ? "var(--color-accent)" : "transparent",
              }}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
