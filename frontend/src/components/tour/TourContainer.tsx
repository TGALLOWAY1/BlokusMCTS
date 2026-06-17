import React from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import type { TourDirection } from './tourTypes';

/**
 * Animated host that cross-fades / slides between screens. Honours
 * `prefers-reduced-motion`: when reduced motion is requested the screens swap
 * with a plain fade and no horizontal travel.
 */
export const TourContainer: React.FC<{
  stepKey: string;
  direction: TourDirection;
  children: React.ReactNode;
}> = ({ stepKey, direction, children }) => {
  const reduce = useReducedMotion();

  const variants = reduce
    ? {
        enter: { opacity: 0 },
        center: { opacity: 1 },
        exit: { opacity: 0 },
      }
    : {
        enter: (dir: TourDirection) => ({ opacity: 0, x: dir * 48 }),
        center: { opacity: 1, x: 0 },
        exit: (dir: TourDirection) => ({ opacity: 0, x: dir * -48 }),
      };

  return (
    <div className="relative h-full overflow-hidden">
      <AnimatePresence mode="wait" custom={direction} initial={false}>
        <motion.div
          key={stepKey}
          custom={direction}
          variants={variants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: reduce ? 0.15 : 0.28, ease: 'easeOut' }}
          className="h-full overflow-y-auto px-1 pb-2"
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
