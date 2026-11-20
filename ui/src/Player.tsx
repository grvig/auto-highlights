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
    <>
      <div className="toolbar">
        <button onClick={onBack}>Back</button>
        <button className="primary" disabled={!steamid || !analysis.data} onClick={onNext}>
          Next
        </button>
        <span className="spacer" />
        {analysis.data && <span className="muted">{matchLine(analysis.data)}</span>}
      </div>
      <div className="body">
        {analysis.error && <p className="error">{analysis.error}</p>}
        {analysis.loading && <p className="empty">Reading {paths.length === 1 ? "demo" : `${paths.length} demos`}…</p>}
        {analysis.data && (
          <table className="grid" aria-label="Players">
            <thead>
              <tr>
                <th />
                <th>Player</th>
                <th className="num">K</th>
                <th className="num">D</th>
                <th className="num">Matches</th>
              </tr>
            </thead>
            <tbody>
              {analysis.data.players.map((player) => (
                <tr
                  key={player.steamid}
                  className={`clickable${player.steamid === steamid ? " selected" : ""}`}
                  onClick={() => onPick(player.steamid, player.name)}
                >
                  <td className="check">
                    <input
                      type="radio"
                      name="player"
                      aria-label={player.name}
                      checked={player.steamid === steamid}
                      onChange={() => onPick(player.steamid, player.name)}
                    />
                  </td>
                  <td className="wide">
                    {player.name}
                    {player.you && <span className="you">YOU</span>}
                  </td>
                  <td className="num">{player.kills}</td>
                  <td className="num">{player.deaths}</td>
                  <td className="num">{player.matches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function matchLine(analysis: Analysis): string {
  return analysis.matches.map((m) => `${m.map} · ${m.rounds} rounds`).join("   ");
}
