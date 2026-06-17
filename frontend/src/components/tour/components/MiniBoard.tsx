import React from 'react';

/**
 * Lightweight, responsive SVG illustration of a Blokus board. Purely
 * decorative/illustrative — it never calls the engine. Cells and highlights are
 * passed in so the same component can show a corner start, a diagonal-only
 * placement, or legal/illegal contact examples.
 */
export interface BoardCell {
  x: number;
  y: number;
  color: 'red' | 'blue' | 'green' | 'yellow';
}

export interface BoardMark {
  x: number;
  y: number;
  kind: 'legal' | 'illegal';
}

const COLOR_HEX: Record<BoardCell['color'], string> = {
  red: '#FF4D4D',
  blue: '#00F0FF',
  green: '#00FF9D',
  yellow: '#FFE600',
};

export const MiniBoard: React.FC<{
  size?: number;
  cells?: BoardCell[];
  marks?: BoardMark[];
  /** Highlight the four starting corners. */
  showCorners?: boolean;
  className?: string;
  ariaLabel?: string;
}> = ({
  size = 20,
  cells = [],
  marks = [],
  showCorners = false,
  className = '',
  ariaLabel = 'Blokus board illustration',
}) => {
  const unit = 10;
  const dim = size * unit;
  const corners: Array<[number, number]> = [
    [0, 0],
    [size - 1, 0],
    [0, size - 1],
    [size - 1, size - 1],
  ];

  return (
    <svg
      viewBox={`0 0 ${dim} ${dim}`}
      className={`h-auto w-full max-w-full ${className}`}
      role="img"
      aria-label={ariaLabel}
    >
      <rect x={0} y={0} width={dim} height={dim} rx={6} fill="#1E1E1E" stroke="#3E3E42" />
      {/* grid */}
      {Array.from({ length: size + 1 }).map((_, i) => (
        <g key={`g${i}`} stroke="#2c2c2e" strokeWidth={0.5}>
          <line x1={i * unit} y1={0} x2={i * unit} y2={dim} />
          <line x1={0} y1={i * unit} x2={dim} y2={i * unit} />
        </g>
      ))}
      {showCorners &&
        corners.map(([cx, cy], i) => (
          <rect
            key={`c${i}`}
            x={cx * unit + 1}
            y={cy * unit + 1}
            width={unit - 2}
            height={unit - 2}
            fill="none"
            stroke="#8B5CF6"
            strokeWidth={1.2}
            strokeDasharray="2 1.5"
          />
        ))}
      {cells.map((c, i) => (
        <rect
          key={`p${i}`}
          x={c.x * unit + 0.6}
          y={c.y * unit + 0.6}
          width={unit - 1.2}
          height={unit - 1.2}
          rx={1.5}
          fill={COLOR_HEX[c.color]}
          opacity={0.92}
        />
      ))}
      {marks.map((m, i) => (
        <g key={`m${i}`}>
          <rect
            x={m.x * unit + 0.6}
            y={m.y * unit + 0.6}
            width={unit - 1.2}
            height={unit - 1.2}
            rx={1.5}
            fill="none"
            stroke={m.kind === 'legal' ? '#00FF9D' : '#FF4D4D'}
            strokeWidth={1.4}
          />
          {m.kind === 'illegal' && (
            <>
              <line
                x1={m.x * unit + 2}
                y1={m.y * unit + 2}
                x2={m.x * unit + unit - 2}
                y2={m.y * unit + unit - 2}
                stroke="#FF4D4D"
                strokeWidth={1.2}
              />
              <line
                x1={m.x * unit + unit - 2}
                y1={m.y * unit + 2}
                x2={m.x * unit + 2}
                y2={m.y * unit + unit - 2}
                stroke="#FF4D4D"
                strokeWidth={1.2}
              />
            </>
          )}
        </g>
      ))}
    </svg>
  );
};
