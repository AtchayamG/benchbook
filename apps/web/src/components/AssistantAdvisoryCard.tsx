import React from 'react';
import type { AssistantProvenance } from '../types/benchbook';

interface AssistantAdvisoryCardProps {
  title: string;
  provenance: AssistantProvenance;
  children: React.ReactNode;
}

export const AssistantAdvisoryCard: React.FC<AssistantAdvisoryCardProps> = ({
  title,
  provenance,
  children,
}) => {
  return (
    <div className="assistant-advisory-box">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--indigo-600)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          🤖 {title}
        </span>
        <span style={{ fontSize: '0.7rem', backgroundColor: '#e0e7ff', color: '#4338ca', padding: '0.15rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
          Advisory Only — Technician Sign-off Required
        </span>
      </div>

      <div style={{ fontSize: '0.875rem', color: 'var(--slate-800)' }}>
        {children}
      </div>

      <div className="provenance-tag">
        <span>Engine: {provenance.engine}</span>
        <span>•</span>
        <span>Model: {provenance.model}</span>
        <span>•</span>
        <span>Generated: {new Date(provenance.generated_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
};
