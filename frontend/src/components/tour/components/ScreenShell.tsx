import React from 'react';
import type { TourStage } from '../tourTypes';
import { ACCENTS } from './accents';

/**
 * Consistent header + scroll body for every tour screen. Keeps spacing,
 * eyebrow, icon, and the "intro" line uniform so individual screens only worry
 * about their unique content.
 */
export const ScreenShell: React.FC<{
  stage: TourStage;
  stepLabel: string;
  intro: React.ReactNode;
  children: React.ReactNode;
}> = ({ stage, stepLabel, intro, children }) => {
  const accent = ACCENTS[stage.accent];
  const Icon = stage.icon;
  return (
    <div className="flex h-full flex-col">
      <header className="mb-5 shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${accent.bgSoft} ${accent.text}`}
          >
            <Icon size={18} />
          </span>
          <span className={`text-xs font-bold uppercase tracking-widest ${accent.text}`}>
            {stepLabel} · {stage.label}
          </span>
        </div>
        <h2 className="mt-3 text-2xl font-bold text-white sm:text-3xl">{stage.title}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-gray-400 sm:text-base">
          {intro}
        </p>
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
};
