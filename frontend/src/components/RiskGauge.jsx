// Semicircular 0..100 risk gauge rendered as inline SVG.
export default function RiskGauge({ value = 0, size = 96 }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const r = size / 2 - 8;
  const cx = size / 2;
  const cy = size / 2;
  const circ = Math.PI * r; // half circle length
  const dash = (v / 100) * circ;

  // Color ramp green -> yellow -> orange -> red.
  const color =
    v < 33 ? "var(--normal)" : v < 60 ? "var(--watch)" : v < 80 ? "var(--warning)" : "var(--critical)";

  return (
    <svg width={size} height={size / 2 + 18} viewBox={`0 0 ${size} ${size / 2 + 18}`}>
      <path
        d={`M ${8} ${cy} A ${r} ${r} 0 0 1 ${size - 8} ${cy}`}
        fill="none" stroke="var(--border)" strokeWidth="8" strokeLinecap="round"
      />
      <path
        d={`M ${8} ${cy} A ${r} ${r} 0 0 1 ${size - 8} ${cy}`}
        fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`}
      />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="22" fontWeight="700" fill="var(--text)">
        {Math.round(v)}
      </text>
      <text x={cx} y={cy + 12} textAnchor="middle" fontSize="9" fill="var(--text-dim)">
        RISK SCORE
      </text>
    </svg>
  );
}
