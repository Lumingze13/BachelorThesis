/* Minimal marks only — no decorative illustration. */
const { useId } = React;

/* Brand mark: a simple, reliable concentric-circle glyph */
function BrandMark({ size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10.5" stroke="currentColor" strokeOpacity=".22" strokeWidth="1"/>
      <circle cx="12" cy="12" r="6" stroke="currentColor" strokeOpacity=".4" strokeWidth="1"/>
      <circle cx="12" cy="12" r="2.2" fill="var(--accent)"/>
    </svg>
  );
}

/* Monogram — the only "avatar" graphic. A solid colored disc with initials.
   Renders identically everywhere; nothing speculative. */
function Monogram({ initials = "—", color = "#b5552f", size = 320 }) {
  return (
    <div
      className="monogram"
      style={{
        width: size,
        height: size,
        background: color,
        fontSize: Math.round(size * 0.34),
      }}
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}

/* Small monogram for chat header / messages */
function MiniAvatar({ initials, color, size = 30 }) {
  return <Monogram initials={initials} color={color} size={size}/>;
}

Object.assign(window, { BrandMark, Monogram, MiniAvatar });
