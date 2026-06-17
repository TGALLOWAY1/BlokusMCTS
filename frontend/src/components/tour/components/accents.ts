/** Tailwind class fragments per neon accent, shared across tour components. */
import type { TourAccent } from '../tourTypes';

export interface AccentClasses {
  text: string;
  border: string;
  borderSoft: string;
  bgSoft: string;
  ring: string;
  dot: string;
  /** Raw hex (for inline SVG / charts). */
  hex: string;
}

export const ACCENTS: Record<TourAccent, AccentClasses> = {
  blue: {
    text: 'text-neon-blue',
    border: 'border-neon-blue',
    borderSoft: 'border-neon-blue/30',
    bgSoft: 'bg-neon-blue/10',
    ring: 'hover:border-neon-blue',
    dot: 'bg-neon-blue',
    hex: '#00F0FF',
  },
  cyan: {
    text: 'text-neon-cyan',
    border: 'border-neon-cyan',
    borderSoft: 'border-neon-cyan/30',
    bgSoft: 'bg-neon-cyan/10',
    ring: 'hover:border-neon-cyan',
    dot: 'bg-neon-cyan',
    hex: '#22D3EE',
  },
  violet: {
    text: 'text-neon-violet',
    border: 'border-neon-violet',
    borderSoft: 'border-neon-violet/30',
    bgSoft: 'bg-neon-violet/10',
    ring: 'hover:border-neon-violet',
    dot: 'bg-neon-violet',
    hex: '#8B5CF6',
  },
  green: {
    text: 'text-neon-green',
    border: 'border-neon-green',
    borderSoft: 'border-neon-green/30',
    bgSoft: 'bg-neon-green/10',
    ring: 'hover:border-neon-green',
    dot: 'bg-neon-green',
    hex: '#00FF9D',
  },
  red: {
    text: 'text-neon-red',
    border: 'border-neon-red',
    borderSoft: 'border-neon-red/30',
    bgSoft: 'bg-neon-red/10',
    ring: 'hover:border-neon-red',
    dot: 'bg-neon-red',
    hex: '#FF4D4D',
  },
};
