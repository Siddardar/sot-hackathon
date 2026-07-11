export function GlassBackdrop() {
  // Fixed, non-interactive glazing layer that sits behind all page content.
  return (
    <div
      aria-hidden
      className="glass-backdrop pointer-events-none fixed inset-0 -z-10"
    />
  );
}
