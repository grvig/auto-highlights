import { useEffect, useState } from "react";
import { api } from "./api";

/** A small mark in the rail when a newer release is out; opens its page. */
export function UpdateButton() {
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    api.checkUpdate().then(
      (found) => current && found.available && setVersion(found.version ?? null),
      () => {},
    );
    return () => {
      current = false;
    };
  }, []);
  if (!version) return null;
  const label = `Version ${version} is available`;
  return (
    <button className="update" title={label} aria-label={label} onClick={() => api.openReleases()}>
      <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M10 15V5M5 10l5-5 5 5" />
      </svg>
    </button>
  );
}
