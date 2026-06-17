import React from 'react';
import { ArrowLeft, ArrowRight, Gamepad2 } from 'lucide-react';

/**
 * Fixed footer navigation: Back / Next, or a final "Play the Champion" CTA on
 * the last step. Buttons are real <button>/<a> semantics with disabled states
 * so keyboard + screen-reader users get correct affordances.
 */
export const TourNav: React.FC<{
  canPrev: boolean;
  canNext: boolean;
  isLastStep: boolean;
  onPrev: () => void;
  onNext: () => void;
  onFinish: () => void;
}> = ({ canPrev, canNext, isLastStep, onPrev, onNext, onFinish }) => {
  return (
    <nav
      aria-label="Tour navigation"
      className="flex items-center justify-between gap-3 border-t border-charcoal-700 bg-charcoal-900/90 px-4 py-3 backdrop-blur-sm"
    >
      <button
        type="button"
        onClick={onPrev}
        disabled={!canPrev}
        className="inline-flex items-center gap-2 rounded-full border border-charcoal-600 px-4 py-2 text-sm font-semibold text-gray-300 transition-colors enabled:hover:border-gray-400 enabled:hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
      >
        <ArrowLeft size={16} /> Back
      </button>

      {isLastStep ? (
        <button
          type="button"
          onClick={onFinish}
          className="inline-flex items-center gap-2 rounded-full border border-neon-green bg-neon-green/15 px-6 py-2 text-sm font-bold text-neon-green transition-transform hover:scale-105 active:scale-95"
        >
          <Gamepad2 size={16} /> Play the Champion
        </button>
      ) : (
        <button
          type="button"
          onClick={onNext}
          disabled={!canNext}
          className="inline-flex items-center gap-2 rounded-full border border-neon-blue bg-neon-blue/15 px-6 py-2 text-sm font-bold text-neon-blue transition-transform enabled:hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next <ArrowRight size={16} />
        </button>
      )}
    </nav>
  );
};
