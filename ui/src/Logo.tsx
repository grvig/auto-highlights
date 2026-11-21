// The app's mark, the same drawing as scripts/make_icon.py (a 64-unit grid).
export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" fill="var(--accent)" />
      <g fill="var(--accent-text)">
        <rect x="30" y="6" width="4" height="10" />
        <rect x="30" y="48" width="4" height="10" />
        <rect x="6" y="30" width="10" height="4" />
        <rect x="48" y="30" width="10" height="4" />
        <polygon points="25,21 25,43 43,32" />
      </g>
    </svg>
  );
}
