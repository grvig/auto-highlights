import { useEffect, useState } from "react";
import { api } from "./api";
import { formatWhen } from "./Demos";
import { message, useAsync } from "./hooks";
import { fileName } from "./Render";
import { Tabs } from "./Shell";
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
    <>
      <Tabs tabs={[{ id: "reels", label: "Reels" }]} current="reels" onSelect={() => {}} />
      <div className="toolbar">
        <button onClick={reels.reload}>Refresh</button>
        <span className="spacer" />
        {reels.data && <span className="muted">{reels.data.length}</span>}
      </div>
      <div className="body">
        {(error || reels.error) && <p className="error">{error ?? reels.error}</p>}
        {reels.data && !reels.data.length && <p className="empty">No reels</p>}
        <div aria-label="Reels">
          {reels.data?.map((reel) => (
            <div key={reel.path} className="reel">
              <Thumbnail reel={reel} />
              <div className="reel-body">
                <strong title={reel.path}>{fileName(reel.path)}</strong>
                <span className="muted">
                  {reel.player} · {formatWhen(reel.made)} · {reel.megabytes} MB
                </span>
                {reel.chapters && (
                  <details>
                    <summary>Chapters</summary>
                    <pre className="selectable">{reel.chapters}</pre>
                  </details>
                )}
                <div className="reel-actions">
                  <button className="primary" onClick={act(() => api.play(reel.path))}>
                    Play
                  </button>
                  <button onClick={act(() => api.showInFolder(reel.path))}>Show in folder</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
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
  return url ? <img className="thumb" src={url} alt="" /> : <div className="thumb" aria-hidden />;
}
