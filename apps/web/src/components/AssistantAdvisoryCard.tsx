import React from 'react';
import type { AdviceProvenance, AssistantProvenance } from '../types/benchbook';

interface AssistantAdvisoryCardProps {
  title: string;
  provenance: AdviceProvenance | AssistantProvenance;
  isStale?: boolean;
  children: React.ReactNode;
}

export const AssistantAdvisoryCard: React.FC<AssistantAdvisoryCardProps> = ({
  title,
  provenance,
  isStale = false,
  children,
}) => {
  const isStrandsEngine = provenance.engine === 'strands';
  const hasAdviceProv = 'actual_sends' in provenance;
  const sends = hasAdviceProv ? (provenance as AdviceProvenance).actual_sends : undefined;
  const tools = hasAdviceProv ? (provenance as AdviceProvenance).actual_tools : undefined;
  const latency = hasAdviceProv ? (provenance as AdviceProvenance).latency_ms : undefined;
  const provider = hasAdviceProv ? (provenance as AdviceProvenance).provider : undefined;

  return (
    <div className="assistant-advisory-box" style={{ borderLeft: isStale ? '4px solid #f59e0b' : undefined }}>
      {isStale && (
        <div
          style={{
            backgroundColor: '#fef3c7',
            color: '#92400e',
            padding: '0.4rem 0.6rem',
            borderRadius: '4px',
            marginBottom: '0.6rem',
            fontSize: '0.75rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          ⚠️ <span>Caution: Job was modified after this advisory was generated. Suggest requesting fresh advice.</span>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--indigo-600)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          🤖 {title}
        </span>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <span
            style={{
              fontSize: '0.7rem',
              backgroundColor: isStrandsEngine ? '#dbeafe' : '#f1f5f9',
              color: isStrandsEngine ? '#1e40af' : '#475569',
              padding: '0.15rem 0.4rem',
              borderRadius: '4px',
              fontWeight: 600,
            }}
          >
            {isStrandsEngine ? (provider === 'offline_transport_test' ? 'Strands Agent (Offline Test)' : 'Strands Agent (Live Inference)') : 'Deterministic (Grounded Catalogue)'}
          </span>
          <span style={{ fontSize: '0.7rem', backgroundColor: '#e0e7ff', color: '#4338ca', padding: '0.15rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
            Advisory Only — Technician Sign-off Required
          </span>
        </div>
      </div>

      <div style={{ fontSize: '0.875rem', color: 'var(--slate-800)' }}>
        {children}
      </div>

      <div
        className="provenance-tag"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.4rem',
          alignItems: 'center',
          marginTop: '0.5rem',
          fontSize: '0.7rem',
          color: 'var(--slate-500)',
        }}
      >
        <span>Engine: <strong>{provenance.engine}</strong></span>
        {provider && <span>Provider: <strong>{provider}</strong></span>}
        <span>Model: <strong>{provenance.model}</strong></span>
        {sends !== undefined && <span>Sends: <strong>{sends}</strong></span>}
        {tools !== undefined && <span>Tools: <strong>{tools}</strong></span>}
        {latency !== undefined && <span>Latency: <strong>{latency}ms</strong></span>}
        <span>Generated: {new Date(provenance.generated_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
};
