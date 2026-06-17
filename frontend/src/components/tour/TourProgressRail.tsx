import React, { useEffect, useRef } from 'react';
import type { TourStage } from './tourTypes';
import { ACCENTS } from './components/accents';

/**
 * Horizontal stage chips + a step counter + progress dots. The chip strip scrolls
 * horizontally on mobile and auto-centres the active chip. Chips are buttons so
 * any stage is reachable directly (used heavily in overview mode).
 */
export const TourProgressRail: React.FC<{
  stages: TourStage[];
  activeIndex: number;
  onSelect: (index: number) => void;
}> = ({ stages, activeIndex, onSelect }) => {
  const railRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
  }, [activeIndex]);

  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">
          Step {activeIndex + 1} of {stages.length}
        </span>
        {/* progress dots */}
        <div className="flex items-center gap-1.5" aria-hidden="true">
          {stages.map((s, i) => (
            <span
              key={s.id}
              className={`h-1.5 rounded-full transition-all ${
                i === activeIndex
                  ? `w-5 ${ACCENTS[s.accent].dot}`
                  : i < activeIndex
                    ? 'w-1.5 bg-gray-500'
                    : 'w-1.5 bg-charcoal-600'
              }`}
            />
          ))}
        </div>
      </div>

      <div
        ref={railRef}
        className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {stages.map((stage, i) => {
          const accent = ACCENTS[stage.accent];
          const active = i === activeIndex;
          const Icon = stage.icon;
          return (
            <button
              key={stage.id}
              ref={active ? activeRef : undefined}
              type="button"
              onClick={() => onSelect(i)}
              aria-current={active ? 'step' : undefined}
              className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                active
                  ? `${accent.border} ${accent.bgSoft} ${accent.text}`
                  : 'border-charcoal-600 text-gray-400 hover:border-charcoal-500 hover:text-gray-200'
              }`}
            >
              <span className="font-mono text-[10px] opacity-70">{i + 1}</span>
              <Icon size={13} />
              {stage.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
