/**
 * Shared types for the "Take the Tour" experience.
 *
 * The tour is data-driven: stages are described by metadata in `tourData.ts`
 * and the navigation state is owned by the pure reducer in `useTourState.ts`.
 */
import type { LucideIcon } from 'lucide-react';

/** Reuse the existing neon palette accents from the research UI. */
export type TourAccent = 'blue' | 'cyan' | 'violet' | 'green' | 'red';

/**
 * Guided mode walks one screen at a time with prominent Back/Next.
 * Overview mode is for returning visitors who want to jump around freely.
 */
export type TourMode = 'guided' | 'overview';

/** Forward (Next/jump-ahead) vs backward (Back/jump-back) — drives slide direction. */
export type TourDirection = 1 | -1;

/** Static description of a single tour stage (no React, fully serialisable). */
export interface TourStage {
  /** Stable id used for keys, aria, and the localStorage-free deep state. */
  id: string;
  /** Short chip label, e.g. "Rules". */
  label: string;
  /** One-line headline shown in the progress rail / screen header. */
  title: string;
  /** lucide-react icon for the chip + screen header. */
  icon: LucideIcon;
  /** Neon accent used for the chip + screen. */
  accent: TourAccent;
}

/** Navigation state owned by the reducer. */
export interface TourState {
  /** Active step index (0-based). */
  stepIndex: number;
  /** Total number of steps — set at init, used to clamp navigation. */
  stepCount: number;
  /** Current mode. */
  mode: TourMode;
  /** Direction of the last transition (for animation). */
  direction: TourDirection;
}

export type TourActionType =
  | { type: 'NEXT' }
  | { type: 'PREV' }
  | { type: 'GOTO'; index: number }
  | { type: 'RESTART' }
  | { type: 'SET_MODE'; mode: TourMode };

/** Result of interpreting a horizontal drag/swipe gesture. */
export type SwipeIntent = 'next' | 'prev' | 'none';
