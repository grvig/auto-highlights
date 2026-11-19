import { useEffect, useState } from "react";
import { api } from "./api";
import { formatWhen } from "./Demos";
import { message, useAsync } from "./hooks";
import { fileName } from "./Render";
import type { Reel } from "./types";

export function ReelsPage() {
  const reels = useAsync(() => api.reels(), []);
  const [error, setError] = useState<string | null>(null);

  const act = (action: () => Promise<unknown>) => async () => {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <section className="page">
      <header className="page-head">
        <h1>Your reels</h1>
        <button onClick={reels.reload}>Refresh</button>
      </header>
      {(error || reels.error) && <p className="notice fail">{error ?? reels.error}</p>}
      {reels.data && !reels.data.length && <p className="notice">No reels yet. Make one from New reel.</p>}
      <ul className="reels" aria-label="Reels">
        {reels.data?.map((reel) => (
          <li key={reel.path} className="reel">
            <Thumbnail reel={reel} />
            <div className="reel-body">
              <strong title={reel.path}>{fileName(reel.path)}</strong>
              <span className="muted small">
                {reel.player} · {formatWhen(reel.made)} · {reel.megabytes} MB
              </span>
              <div className="reel-actions">
                <button className="primary" onClick={act(() => api.play(reel.path))}>
                  Play
                </button>
                <button onClick={act(() => api.showInFolder(reel.path))}>Show in folder</button>
              </div>
              {reel.chapters && (
                <details>
                  <summary className="muted small">Chapters for the video description</summary>
                  <pre className="selectable">{reel.chapters}</pre>
                </details>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Thumbnail({ reel }: { reel: Reel }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    if (reel.thumbnail) {
      api.thumbnail(reel.thumbnail).then(
        (answer) => current && setUrl(answer),
        () => current && setUrl(null),
      );
    }
    return () => {
      current = false;
    };
  }, [reel.thumbnail]);
  return url ? <img className="thumb" src={url} alt="" /> : <div className="thumb empty" aria-hidden />;
}
