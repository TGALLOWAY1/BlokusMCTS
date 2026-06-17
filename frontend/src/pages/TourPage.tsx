import React, { useCallback, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FlaskConical, RotateCcw, X } from 'lucide-react';

import { useTourState, decideSwipe } from '../components/tour/useTourState';
import { TOUR_STAGES } from '../components/tour/tourData';
import { ModeToggle } from '../components/tour/ModeToggle';
import { TourProgressRail } from '../components/tour/TourProgressRail';
import { TourContainer } from '../components/tour/TourContainer';
import { TourNav } from '../components/tour/TourNav';
import type { ScreenProps } from '../components/tour/screens/types';

import { ScreenRules } from '../components/tour/screens/ScreenRules';
import { ScreenComplexity } from '../components/tour/screens/ScreenComplexity';
import { ScreenAgents } from '../components/tour/screens/ScreenAgents';
import { ScreenTechniques } from '../components/tour/screens/ScreenTechniques';
import { ScreenEvaluation } from '../components/tour/screens/ScreenEvaluation';
import { ScreenTrueSkill } from '../components/tour/screens/ScreenTrueSkill';
import { ScreenChampion } from '../components/tour/screens/ScreenChampion';
import { ScreenPlay } from '../components/tour/screens/ScreenPlay';

/** Screen components keyed by stage id (order mirrors TOUR_STAGES). */
const SCREENS: Record<string, React.FC<ScreenProps>> = {
  rules: ScreenRules,
  complexity: ScreenComplexity,
  agents: ScreenAgents,
  techniques: ScreenTechniques,
  evaluation: ScreenEvaluation,
  trueskill: ScreenTrueSkill,
  champion: ScreenChampion,
  play: ScreenPlay,
};

export const TourPage: React.FC = () => {
  const navigate = useNavigate();
  const tour = useTourState(TOUR_STAGES.length);
  const { state, next, prev, goto, restart, setMode, finish, canPrev, canNext, isLastStep } = tour;

  const stage = TOUR_STAGES[state.stepIndex];
  const Screen = SCREENS[stage.id];
  const stepLabel = `Step ${state.stepIndex + 1} of ${TOUR_STAGES.length}`;

  /* Finish the tour: persist completion and head to the playable demo. */
  const handleFinish = useCallback(() => {
    finish();
    navigate('/play');
  }, [finish, navigate]);

  const handleSkip = useCallback(() => {
    finish();
    navigate('/play');
  }, [finish, navigate]);

  /* Keyboard navigation: ← / → move between steps. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next, prev]);

  /* Touch swipe navigation (mobile). */
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    const t = e.changedTouches[0];
    touchStart.current = { x: t.clientX, y: t.clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    if (!touchStart.current) return;
    const t = e.changedTouches[0];
    const intent = decideSwipe(
      t.clientX - touchStart.current.x,
      t.clientY - touchStart.current.y,
    );
    touchStart.current = null;
    if (intent === 'next') next();
    else if (intent === 'prev') prev();
  };

  return (
    <div className="flex h-screen flex-col bg-charcoal-900 text-gray-200">
      {/* Header */}
      <header className="shrink-0 border-b border-charcoal-700 bg-charcoal-900/95 px-4 py-3 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3">
          <Link to="/" className="flex items-center gap-2 text-sm font-bold text-white">
            <FlaskConical size={18} className="text-neon-cyan" />
            MCTS Laboratory
          </Link>
          <span className="hidden text-xs uppercase tracking-widest text-gray-500 sm:inline">
            · Take the Tour
          </span>
          <div className="ml-auto flex items-center gap-2">
            <ModeToggle mode={state.mode} onChange={setMode} />
            <button
              type="button"
              onClick={restart}
              className="inline-flex items-center gap-1.5 rounded-full border border-charcoal-600 px-3 py-1.5 text-xs font-semibold text-gray-400 transition-colors hover:border-gray-400 hover:text-gray-200"
              title="Restart the tour"
            >
              <RotateCcw size={13} /> Restart
            </button>
            <button
              type="button"
              onClick={handleSkip}
              className="inline-flex items-center gap-1.5 rounded-full border border-charcoal-600 px-3 py-1.5 text-xs font-semibold text-gray-400 transition-colors hover:border-neon-red/60 hover:text-neon-red"
              title="Skip the tour"
            >
              <X size={13} /> Skip
            </button>
          </div>
        </div>
      </header>

      {/* Progress rail */}
      <div className="shrink-0 border-b border-charcoal-700 bg-charcoal-900/80 px-4 py-3">
        <div className="mx-auto max-w-5xl">
          <TourProgressRail stages={TOUR_STAGES} activeIndex={state.stepIndex} onSelect={goto} />
        </div>
      </div>

      {/* Screen host */}
      <main
        className="min-h-0 flex-1"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        <div className="mx-auto h-full max-w-5xl px-4 py-5">
          <TourContainer stepKey={stage.id} direction={state.direction}>
            <Screen stage={stage} stepLabel={stepLabel} onComplete={finish} />
          </TourContainer>
        </div>
      </main>

      {/* Screen-reader announcement of the active step */}
      <div aria-live="polite" className="sr-only">
        {stepLabel}: {stage.title}
      </div>

      {/* Footer nav */}
      <div className="shrink-0">
        <div className="mx-auto max-w-5xl">
          <TourNav
            canPrev={canPrev}
            canNext={canNext}
            isLastStep={isLastStep}
            onPrev={prev}
            onNext={next}
            onFinish={handleFinish}
          />
        </div>
      </div>
    </div>
  );
};

export default TourPage;
