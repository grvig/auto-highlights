import type { ReactNode } from "react";
import { Logo } from "./Logo";
import { UpdateButton } from "./Update";

export type View = "new" | "reels" | "settings" | "ready";

const PAGES: { view: View; label: string; icon: ReactNode }[] = [
  {
    view: "new",
    label: "New reel",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2.5" y="4.5" width="15" height="11" />
        <path d="M8.5 7.5v5l4-2.5z" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    view: "reels",
    label: "Reels",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M3 5h14M3 10h14M3 15h14" />
      </svg>
    ),
  },
  {
    view: "settings",
    label: "Settings",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M3 6h8M15 6h2M3 14h2M9 14h8" />
        <rect x="11" y="4" width="4" height="4" />
        <rect x="5" y="12" width="4" height="4" />
      </svg>
    ),
  },
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
      <nav className="rail" aria-label="Main">
        <div className="rail-logo" title="auto-highlights">
          <Logo size={24} />
        </div>
        {PAGES.map((page) => (
          <button
            key={page.view}
            title={page.label}
            aria-label={page.label}
            aria-current={view === page.view ? "page" : undefined}
            onClick={() => onNavigate(page.view)}
          >
            {page.icon}
          </button>
        ))}
        <div className="rail-end">
          <UpdateButton />
          {status}
        </div>
      </nav>
      <main className="content">{children}</main>
    </div>
  );
}

/** Text tabs across the top of a page. */
export function Tabs<T extends string>({
  tabs,
  current,
  onSelect,
  enabled = () => true,
}: {
  tabs: readonly { id: T; label: string }[];
  current: T;
  onSelect: (id: T) => void;
  enabled?: (id: T) => boolean;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={tab.id === current}
          disabled={!enabled(tab.id)}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
