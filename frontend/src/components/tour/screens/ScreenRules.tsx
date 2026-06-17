import React from 'react';
import { Check, X } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { MiniBoard, type BoardCell, type BoardMark } from '../components/MiniBoard';
import type { ScreenProps } from './types';

/* A red corner piece, with one legal (diagonal) and one illegal (edge) extension. */
const CELLS: BoardCell[] = [
  { x: 0, y: 0, color: 'red' },
  { x: 1, y: 0, color: 'red' },
  { x: 0, y: 1, color: 'red' },
];
const MARKS: BoardMark[] = [
  { x: 2, y: 1, kind: 'legal' }, // diagonal touch to (1,0)
  { x: 2, y: 0, kind: 'illegal' }, // edge touch to (1,0)
];

const RULES: Array<{ n: string; text: React.ReactNode }> = [
  { n: '20×20', text: 'Four players share one 20×20 board, each with the same 21 polyomino pieces.' },
  { n: '1', text: 'Your very first piece must cover your starting corner.' },
  { n: '◇', text: 'Every later piece must touch one of your pieces corner-to-corner (diagonally).' },
  { n: '✕', text: 'Your pieces may never touch your own colour edge-to-edge.' },
  { n: 'Σ', text: 'Score by squares placed: you want your pieces down and your opponents blocked.' },
];

export const ScreenRules: React.FC<ScreenProps> = ({ stage, stepLabel }) => (
  <ScreenShell
    stage={stage}
    stepLabel={stepLabel}
    intro="Blokus is a four-player territory game. The rules take thirty seconds — the strategy takes a lot longer."
  >
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-2xl border border-charcoal-700 bg-charcoal-800/60 p-4">
        <div className="mx-auto max-w-[320px]">
          <MiniBoard
            cells={CELLS}
            marks={MARKS}
            showCorners
            ariaLabel="Board showing a red corner piece with a legal diagonal extension and an illegal edge extension"
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-4 text-xs">
          <span className="inline-flex items-center gap-1.5 text-neon-green">
            <Check size={14} /> Diagonal touch — legal
          </span>
          <span className="inline-flex items-center gap-1.5 text-neon-red">
            <X size={14} /> Edge touch — illegal
          </span>
        </div>
        <p className="mt-2 text-center text-[11px] uppercase tracking-widest text-gray-500">
          Dashed squares = the four starting corners
        </p>
      </div>

      <ul className="space-y-3">
        {RULES.map((r, i) => (
          <li
            key={i}
            className="flex items-start gap-3 rounded-xl border border-charcoal-700 bg-charcoal-800/40 p-3"
          >
            <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-neon-cyan/10 font-mono text-sm font-bold text-neon-cyan">
              {r.n}
            </span>
            <span className="text-sm leading-relaxed text-gray-300">{r.text}</span>
          </li>
        ))}
      </ul>
    </div>
  </ScreenShell>
);
