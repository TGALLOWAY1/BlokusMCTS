import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TourPage } from '../../../pages/TourPage';
import { TOUR_STAGES } from '../tourData';

/**
 * Lightweight wiring smoke test — not a per-screen visual test (screen
 * transitions run through AnimatePresence and navigation is covered by the
 * reducer/hook tests). Confirms the tour mounts on the first stage, renders a
 * chip for every stage, and exposes the footer Next control. Data hooks fall
 * back to demo data offline.
 */
const renderTour = () =>
  render(
    <MemoryRouter initialEntries={['/tour']}>
      <TourPage />
    </MemoryRouter>,
  );

describe('TourPage (smoke)', () => {
  beforeEach(() => {
    localStorage.clear();
    // Hooks fetch arena/champion data; offline fallback is expected in tests.
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
  });

  it('mounts on the first stage with the step counter', () => {
    renderTour();
    expect(screen.getByText('How Blokus works')).toBeTruthy();
    expect(screen.getByText('Step 1 of 8')).toBeTruthy();
  });

  it('renders a clickable chip for every stage (data-driven nav)', () => {
    renderTour();
    for (const stage of TOUR_STAGES) {
      // Chip accessible name includes its label; throws if missing.
      expect(screen.getByRole('button', { name: new RegExp(stage.label, 'i') })).toBeTruthy();
    }
  });

  it('exposes the footer Next control', () => {
    renderTour();
    expect(screen.getByRole('button', { name: /next/i })).toBeTruthy();
  });
});
