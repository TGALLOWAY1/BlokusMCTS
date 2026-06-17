import { useEffect, useState } from 'react';
import { API_BASE } from '../constants/gameConstants';
import { type ChampionMetadata } from '../utils/championConfig';

export interface ChampionState {
  isLoading: boolean;
  /** True only when a validated champion exists (HTTP 200). */
  available: boolean;
  /** Human-readable reason the champion is unavailable (404 / network / etc). */
  error: string | null;
  champion: ChampionMetadata | null;
}

/**
 * Fetches the validated champion from the registry-backed GET /api/champion.
 *
 * Gracefully distinguishes the cases the demo must handle:
 *   - 200  -> a validated champion is available (`available: true`).
 *   - 404  -> no validated champion has been promoted yet (friendly message).
 *   - else -> backend unavailable / unexpected error.
 */
export const useChampion = (): ChampionState => {
  const [state, setState] = useState<ChampionState>({
    isLoading: true,
    available: false,
    error: null,
    champion: null,
  });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/champion`);
        if (resp.status === 404) {
          let detail = 'No validated champion has been promoted yet.';
          try {
            const body = await resp.json();
            if (body?.message) detail = String(body.message);
            else if (body?.detail) detail = String(body.detail);
          } catch {
            /* keep default */
          }
          if (!cancelled) {
            setState({ isLoading: false, available: false, error: detail, champion: null });
          }
          return;
        }
        if (!resp.ok) {
          throw new Error(`Champion service error (${resp.status})`);
        }
        const champion = (await resp.json()) as ChampionMetadata;
        if (!cancelled) {
          setState({ isLoading: false, available: true, error: null, champion });
        }
      } catch (err) {
        if (!cancelled) {
          setState({
            isLoading: false,
            available: false,
            error:
              err instanceof Error
                ? `Could not reach the champion service: ${err.message}`
                : 'Could not reach the champion service.',
            champion: null,
          });
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
};
