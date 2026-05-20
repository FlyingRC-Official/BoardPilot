"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/ask", label: "Ask" },
  { href: "/sources", label: "Sources" },
  { href: "/eval", label: "Eval" },
  { href: "/review", label: "Review" }
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">B</span>
        <span>BoardPilot</span>
      </div>
      <nav className="nav" aria-label="Primary navigation">
        {links.map((link) => (
          <Link key={link.href} href={link.href} className={pathname.startsWith(link.href) ? "active" : ""}>
            {link.label}
          </Link>
        ))}
      </nav>
      <p className="sidebar-note">
        Private hardware support RAG. Evidence is saved before answers are generated, and low-confidence responses move to review.
      </p>
    </aside>
  );
}

