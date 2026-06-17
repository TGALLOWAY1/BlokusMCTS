import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  TOUR_COMPLETED_KEY,
  decideSwipe,
  initialMode,
  readTourCompleted,
  tourReducer,
  useTourState,
  writeTourCompleted,
} from '../useTourState';
import type { TourState } from '../tourTypes';

const base = (over: Partial<TourState> = {}): TourState => ({
  stepIndex: 0,
  stepCount: 8,
  mode: 'guided',
  direction: 1,
  ...over,
});

describe('tourReducer', () => {
  it('NEXT advances and sets forward direction', () => {
    const s = tourReducer(base(), { type: 'NEXT' });
    expect(s.stepIndex).toBe(1);
    expect(s.direction).toBe(1);
  });

  it('NEXT clamps at the last step (no overflow)', () => {
    const s = tourReducer(base({ stepIndex: 7 }), { type: 'NEXT' });
    expect(s.stepIndex).toBe(7);
  });

  it('PREV goes back and sets backward direction', () => {
    const s = tourReducer(base({ stepIndex: 3 }), { type: 'PREV' });
    expect(s.stepIndex).toBe(2);
    expect(s.direction).toBe(-1);
  });

  it('PREV clamps at zero', () => {
    const s = tourReducer(base({ stepIndex: 0 }), { type: 'PREV' });
    expect(s.stepIndex).toBe(0);
  });

  it('GOTO clamps and derives direction from the jump', () => {
    expect(tourReducer(base({ stepIndex: 1 }), { type: 'GOTO', index: 5 }).stepIndex).toBe(5);
    expect(tourReducer(base({ stepIndex: 1 }), { type: 'GOTO', index: 5 }).direction).toBe(1);
    expect(tourReducer(base({ stepIndex: 5 }), { type: 'GOTO', index: 1 }).direction).toBe(-1);
    expect(tourReducer(base({ stepIndex: 0 }), { type: 'GOTO', index: 99 }).stepIndex).toBe(7);
    expect(tourReducer(base({ stepIndex: 0 }), { type: 'GOTO', index: -3 }).stepIndex).toBe(0);
  });

  it('RESTART resets to step 0 and forces guided mode', () => {
    const s = tourReducer(base({ stepIndex: 6, mode: 'overview' }), { type: 'RESTART' });
    expect(s.stepIndex).toBe(0);
    expect(s.mode).toBe('guided');
  });

  it('SET_MODE switches mode without moving the step', () => {
    const s = tourReducer(base({ stepIndex: 4 }), { type: 'SET_MODE', mode: 'overview' });
    expect(s.mode).toBe('overview');
    expect(s.stepIndex).toBe(4);
  });
});

describe('decideSwipe', () => {
  it('left swipe -> next', () => expect(decideSwipe(-90, 5)).toBe('next'));
  it('right swipe -> prev', () => expect(decideSwipe(90, 5)).toBe('prev'));
  it('short swipe is ignored', () => expect(decideSwipe(-20, 0)).toBe('none'));
  it('vertical-dominant swipe is ignored', () => expect(decideSwipe(-70, 120)).toBe('none'));
});

describe('completion persistence', () => {
  beforeEach(() => localStorage.clear());

  it('round-trips the completion flag under the documented key', () => {
    expect(readTourCompleted()).toBe(false);
    writeTourCompleted(true);
    expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
    expect(readTourCompleted()).toBe(true);
    writeTourCompleted(false);
    expect(readTourCompleted()).toBe(false);
  });

  it('initialMode reflects completion', () => {
    expect(initialMode(false)).toBe('guided');
    expect(initialMode(true)).toBe('overview');
  });
});

describe('useTourState', () => {
  beforeEach(() => localStorage.clear());

  it('first-time visitor starts in guided mode at step 0', () => {
    const { result } = renderHook(() => useTourState(8));
    expect(result.current.state.mode).toBe('guided');
    expect(result.current.state.stepIndex).toBe(0);
  });

  it('returning (completed) visitor starts in overview mode', () => {
    writeTourCompleted(true);
    const { result } = renderHook(() => useTourState(8));
    expect(result.current.state.mode).toBe('overview');
    expect(result.current.wasCompleted).toBe(true);
  });

  it('next / prev / goto move through steps and expose nav flags', () => {
    const { result } = renderHook(() => useTourState(8));

    expect(result.current.canPrev).toBe(false);
    act(() => result.current.next());
    expect(result.current.state.stepIndex).toBe(1);
    expect(result.current.canPrev).toBe(true);

    act(() => result.current.goto(7));
    expect(result.current.state.stepIndex).toBe(7);
    expect(result.current.isLastStep).toBe(true);
    expect(result.current.canNext).toBe(false);

    act(() => result.current.prev());
    expect(result.current.state.stepIndex).toBe(6);
  });

  it('finish persists completion; restart clears it and resets to guided step 0', () => {
    const { result } = renderHook(() => useTourState(8));
    act(() => result.current.goto(5));

    act(() => result.current.finish());
    expect(readTourCompleted()).toBe(true);

    act(() => {
      result.current.setMode('overview');
      result.current.restart();
    });
    expect(readTourCompleted()).toBe(false);
    expect(result.current.state.stepIndex).toBe(0);
    expect(result.current.state.mode).toBe('guided');
  });
});
