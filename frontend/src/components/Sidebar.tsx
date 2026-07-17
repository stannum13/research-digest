import { useState } from "react";
import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Archive,
  Atom,
  Bookmark,
  Brain,
  FlaskConical,
  Network,
  Newspaper,
  Search,
  Signal,
} from "lucide-react";

import { useSynthesisSelection } from "../context/SynthesisSelectionContext";
import { useDigestStatus } from "../hooks/useDigestApi";
import { formatDigestDate, formatTimeAgo } from "../lib/format";
import { notebookEase } from "../lib/motion";

const navItems = [
  { to: "/", label: "Feed", icon: Newspaper },
  { to: "/saved", label: "Saved", icon: Bookmark },
  { to: "/quantum", label: "Quantum", icon: Atom },
  { to: "/ml", label: "ML", icon: FlaskConical },
  { to: "/ai", label: "AI", icon: Brain },
  { to: "/archive", label: "Archive", icon: Archive },
  { to: "/search", label: "Search", icon: Search },
  { to: "/synthesis", label: "Synthesis", icon: Network },
];

export function Sidebar() {
  const { data: status } = useDigestStatus();
  const { selectedCount } = useSynthesisSelection();

  return (
    <>
      <aside className="fixed left-0 top-0 z-30 hidden h-screen w-[264px] flex-col bg-[var(--bg-sidebar)] px-5 py-6 text-[var(--text-light-2)] md:flex">
        <div className="mb-10">
          <div className="mb-5 font-serif text-3xl text-[var(--text-light)]">Marginalia</div>
          <div className="font-mono text-xs uppercase text-[var(--text-light-2)]">{formatDigestDate()}</div>
        </div>

        <nav className="space-y-1">
          {navItems.map((item) => (
            <SidebarLink key={item.to} {...item} count={item.to === "/synthesis" ? selectedCount : undefined} />
          ))}
        </nav>

        <div className="mt-auto rounded-lg border border-[var(--border-dark)] bg-[rgba(255,250,243,0.04)] p-4">
          <div className="mb-3 flex items-center gap-2 font-mono text-xs uppercase">
            <motion.span
              className={`h-2.5 w-2.5 rounded-full ${
                status?.status === "failed" ? "bg-[var(--accent-rose)]" : "bg-[var(--accent-sage)]"
              }`}
              animate={{ scale: [1, 1.4, 1], opacity: [1, 0.45, 1] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: notebookEase }}
            />
            {status?.status ?? "idle"}
          </div>
          <div className="text-sm text-[var(--text-light)]">Last updated</div>
          <div className="font-mono text-xs">{formatTimeAgo(status?.last_run_at)}</div>
          {status?.error_message ? <p className="mt-3 text-xs text-[var(--accent-rose)]">{status.error_message}</p> : null}
        </div>
      </aside>

      <header className="fixed left-0 right-0 top-0 z-30 border-b border-[var(--border-dark)] bg-[var(--bg-sidebar)] px-4 py-3 text-[var(--text-light)] md:hidden">
        <div className="mb-3 flex items-center justify-between">
          <div className="font-serif text-2xl">Marginalia</div>
          <div className="flex items-center gap-2 font-mono text-[11px] text-[var(--text-light-2)]">
            <Signal size={14} aria-hidden="true" />
            {status?.status ?? "idle"}
          </div>
        </div>
        <nav className="scrollbar-soft flex gap-2 overflow-x-auto pb-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-2 font-mono text-[11px] ${
                  isActive ? "bg-[var(--accent-clay)] text-[var(--bg-card)]" : "bg-[var(--bg-sidebar-2)] text-[var(--text-light-2)]"
                }`
              }
            >
              <Icon size={14} aria-hidden="true" />
              {label}
              {to === "/synthesis" && selectedCount > 0 ? (
                <span className="rounded-full bg-[rgba(255,250,243,0.15)] px-1.5 text-[10px]">{selectedCount}</span>
              ) : null}
            </NavLink>
          ))}
        </nav>
      </header>
    </>
  );
}

type SidebarLinkProps = {
  to: string;
  label: string;
  icon: typeof Newspaper;
  count?: number;
};

function SidebarLink({ to, label, icon: Icon, count }: SidebarLinkProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <NavLink
      to={to}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 overflow-hidden rounded-md px-3 py-3 font-mono text-sm transition ${
          isActive ? "text-[var(--text-light)]" : "text-[var(--text-light-2)]"
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <motion.span
              layoutId="navIndicator"
              className="absolute left-0 top-2 h-7 w-1 rounded-r-full bg-[var(--accent-clay)]"
            />
          ) : null}
          <motion.span
            className="absolute inset-0 origin-left bg-[var(--bg-sidebar-2)]"
            initial={false}
            animate={{ scaleX: hovered || isActive ? 1 : 0 }}
            transition={{ duration: 0.18, ease: notebookEase }}
          />
          <Icon className="relative" size={16} aria-hidden="true" />
          <span className="relative">{label}</span>
          {count && count > 0 ? (
            <span className="relative ml-auto rounded-full bg-[rgba(255,250,243,0.12)] px-2 py-0.5 text-[10px] text-[var(--text-light)]">
              {count}
            </span>
          ) : null}
        </>
      )}
    </NavLink>
  );
}
