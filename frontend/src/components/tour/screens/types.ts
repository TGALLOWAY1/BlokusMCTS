import type { TourStage } from '../tourTypes';

/** Common props passed to every tour screen. */
export interface ScreenProps {
  stage: TourStage;
  /** Pre-formatted "Step N of M" label for the screen header. */
  stepLabel: string;
  /** Marks the tour complete — used by the final Play CTA. */
  onComplete?: () => void;
}
