/** Shown in place of the answer while the assistant works: animated dots plus the current stage. */
export function Thinking({ stage }: { stage?: string }) {
  return (
    <div className="thinking" role="status" aria-live="polite">
      <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>
      <span className="thinking-label">{stage || "Working"}</span>
    </div>
  );
}
