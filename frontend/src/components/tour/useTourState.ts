/**
 * Tour navigation state: a pure reducer plus a thin React hook that wires it to
 * `localStorage` for completion persistence.
 *
 * Design goals:
 *   - The reducer is pure and exported so it can be unit-tested in isolation.
 *   - First-time visitors start in `guided` mode; returning (completed) visitors
 *     start in `overview` mode.
 *   - Completion is persisted under a single, stable key.
 *   - No global app state — the tour is self-contained.
 */
import { useCallback, useReducer, useState } from 'react';
import type {
  SwipeIntent,
  TourActionType,
  TourMode,
  TourState,
} from './tourTypes';

/** localStorage flag set once a visitor finishes (or skips) the tour. */
export const TOUR_COMPLETED_KEY = 'mcts-laboratory-tour-completed';

/* ------------------------------------------------------------------ */
/*  Persistence helpers (pure, SSR/Node safe)                          */
/* ------------------------------------------------------------------ */

export function readTourCompleted(): boolean {
  try {
    return globalThis.localStorage?.getItem(TOUR_COMPLETED_KEY) === 'true';
  } catch {
    return false;
  }
}

export function writeTourCompleted(completed: boolean): void {
  try {
    if (completed) {
      globalThis.localStorage?.setItem(TOUR_COMPLETED_KEY, 'true');
    } else {
      globalThis.localStorage?.removeItem(TOUR_COMPLETED_KEY);
    }
  } catch {
    /* storage unavailable (private mode / SSR) — degrade silently */
  }
}

/** Returning visitors land in overview; first-timers get the guided walk. */
export function initialMode(completed = readTourCompleted()): TourMode {
  return completed ? 'overview' : 'guided';
}

const clamp = (n: number, count: number): number =>
  Math.max(0, Math.min(count - 1, n));

/* ------------------------------------------------------------------ */
/*  Pure reducer                                                       */
/* ------------------------------------------------------------------ */

export function tourReducer(state: TourState, action: TourActionType): TourState {
  switch (action.type) {
    case 'NEXT': {
      const stepIndex = clamp(state.stepIndex + 1, state.stepCount);
      if (stepIndex === state.stepIndex) return state;
      return { ...state, stepIndex, direction: 1 };
    }
    case 'PREV': {
      const stepIndex = clamp(state.stepIndex - 1, state.stepCount);
      if (stepIndex === state.stepIndex) return state;
      return { ...state, stepIndex, direction: -1 };
    }
    case 'GOTO': {
      const stepIndex = clamp(action.index, state.stepCount);
      if (stepIndex === state.stepIndex) return state;
      return {
        ...state,
        stepIndex,
        direction: stepIndex > state.stepIndex ? 1 : -1,
      };
    }
    case 'RESTART':
      return { ...state, stepIndex: 0, direction: -1, mode: 'guided' };
    case 'SET_MODE':
      if (action.mode === state.mode) return state;
      return { ...state, mode: action.mode };
    default:
      return state;
  }
}

/* ------------------------------------------------------------------ */
/*  Swipe decision (pure, unit-tested)                                 */
/* ------------------------------------------------------------------ */

/**
 * Interpret a horizontal drag. A left swipe (negative dx) advances to the next
 * screen; a right swipe goes back. Vertical-dominant or short gestures are
 * ignored so the tour does not hijack page scrolling.
 */
export function decideSwipe(
  dx: number,
  dy: number,
  threshold = 60,
): SwipeIntent {
  if (Math.abs(dx) < threshold) return 'none';
  if (Math.abs(dx) <= Math.abs(dy)) return 'none';
  return dx < 0 ? 'next' : 'prev';
}

/* ------------------------------------------------------------------ */
/*  React hook                                                         */
/* ------------------------------------------------------------------ */

export interface UseTourState {
  state: TourState;
  /** True at first render iff the visitor had already completed the tour. */
  wasCompleted: boolean;
  next: () => void;
  prev: () => void;
  goto: (index: number) => void;
  /** Reset to step 0 + guided mode and clear the completion flag. */
  restart: () => void;
  setMode: (mode: TourMode) => void;
  /** Persist completion (used by Finish + Skip). */
  finish: () => void;
  /** Whether Back is available. */
  canPrev: boolean;
  /** Whether Next is available (false on the last step). */
  canNext: boolean;
  /** True when on the final step. */
  isLastStep: boolean;
}

export function useTourState(stepCount: number): UseTourState {
  // Read completion once so the value is stable across the render lifetime.
  const [wasCompleted] = useState(readTourCompleted);

  const [state, dispatch] = useReducer(tourReducer, undefined, () => ({
    stepIndex: 0,
    stepCount,
    mode: initialMode(wasCompleted),
    direction: 1 as const,
  }));

  const next = useCallback(() => dispatch({ type: 'NEXT' }), []);
  const prev = useCallback(() => dispatch({ type: 'PREV' }), []);
  const goto = useCallback((index: number) => dispatch({ type: 'GOTO', index }), []);
  const setMode = useCallback((mode: TourMode) => dispatch({ type: 'SET_MODE', mode }), []);
  const finish = useCallback(() => writeTourCompleted(true), []);
  const restart = useCallback(() => {
    writeTourCompleted(false);
    dispatch({ type: 'RESTART' });
  }, []);

  return {
    state,
    wasCompleted,
    next,
    prev,
    goto,
    restart,
    setMode,
    finish,
    canPrev: state.stepIndex > 0,
    canNext: state.stepIndex < state.stepCount - 1,
    isLastStep: state.stepIndex === state.stepCount - 1,
  };
}
