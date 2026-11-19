import { useEffect } from "react";
import { api } from "./api";
import { useAsync } from "./hooks";
import type { Analysis } from "./types";

interface Props {
  paths: string[];
  steamid: string | null;
  onPick: (steamid: string, name: string) => void;
  onBack: () => void;
  onNext: () => void;
}

export function PlayerStep({ paths, steamid, onPick, onBack, onNext }: Props) {
  const analysis = useAsync<Analysis>(() => api.analyze(paths), [paths.join("|")]);

  // Whoever is signed in to Steam on this PC is the usual answer.
  useEffect(() => {
    const you = analysis.data?.players.find((p) => p.you);
    if (steamid === null && you) onPick(you.steamid, you.name);
  }, [analysis.data, steamid, onPick]);

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Whose plays?</h1>
          <p className="muted">
            {analysis.data ? matchLine(analysis.data) : `Reading ${paths.length === 1 ? "the demo" : `${paths.length} demos`}…`}
          </p>
        </div>
      </header>
      {analysis.loading && (
        <p className="notice">The first read of a demo takes a little while; after that it is remembered.</p>
      )}
      {analysis.error && <p className="notice fail">{analysis.error}</p>}
      {analysis.data && (
        <table className="table">
          <thead>
            <tr>
              <th />
              <th>Player</th>
              <th className="num">Matches</th>
              <th className="num">Kills</th>
              <th className="num">Deaths</th>
            </tr>
          </thead>
          <tbody>
            {analysis.data.players.map((player) => (
              <tr key={player.steamid} className={player.steamid === steamid ? "picked" : ""}>
                <td>
                  <input
                    type="radio"
                    name="player"
                    aria-label={player.name}
                    checked={player.steamid === steamid}
                    onChange={() => onPick(player.steamid, player.name)}
                  />
                </td>
                <td>
                  {player.name}
                  {player.you && <span className="badge">You</span>}
                </td>
                <td className="num">{player.matches}</td>
                <td className="num">{player.kills}</td>
                <td className="num">{player.deaths}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <footer className="page-foot">
        <button onClick={onBack}>Back</button>
        <button className="primary" disabled={!steamid || !analysis.data} onClick={onNext}>
          Find plays
        </button>
      </footer>
    </section>
  );
}

function matchLine(analysis: Analysis): string {
  return analysis.matches.map((m) => `${m.map.replace(/^de_/, "")} · ${m.rounds} rounds`).join("  |  ");
}
