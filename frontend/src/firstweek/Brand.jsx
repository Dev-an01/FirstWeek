import { Layers } from 'lucide-react';

export function Brand() {
  return (
    <span className="fw-brand">
      <Layers aria-hidden="true" size={25} strokeWidth={1.7} />
      FirstWeek<span className="fw-brand-dot">.</span>
    </span>
  );
}
