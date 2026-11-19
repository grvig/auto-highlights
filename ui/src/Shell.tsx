import type { ReactNode } from "react";

export type View = "new" | "reels" | "settings" | "ready";

const PAGES: { view: View; label: string }[] = [
  { view: "new", label: "New reel" },
  { view: "reels", label: "Your reels" },
  { view: "settings", label: "Settings" },
];

interface Props {
  view: View;
  onNavigate: (view: View) => void;
  status: ReactNode;
  children: ReactNode;
}

export function Shell({ view, onNavigate, status, children }: Props) {
  return (
    <div className="shell">
      <nav className="nav" aria-label="Main">
        <div className="brand">
          auto-<span>highlights</span>
        </div>
        {PAGES.map((page) => (
          <button
            key={page.view}
            aria-current={view === page.view ? "page" : undefined}
            onClick={() => onNavigate(page.view)}
          >
            {page.label}
          </button>
        ))}
        <div className="status">{status}</div>
      </nav>
      <main className="content">{children}</main>
    </div>
  );
}
