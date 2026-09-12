import React, { useState } from 'react';
import type { AuditEvent } from '../types/benchbook';

interface AuditEventStreamProps {
  events: AuditEvent[];
}

export const AuditEventStream: React.FC<AuditEventStreamProps> = ({ events }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!events || events.length === 0) {
    return (
      <div style={{ color: 'var(--slate-500)', fontSize: '0.85rem', fontStyle: 'italic', padding: '1rem 0' }}>
        No audit events recorded yet.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {events.map((evt) => {
        const isExpanded = expandedId === evt.event_id;
        const timeFormatted = new Date(evt.created_at).toLocaleString();

        let actorBadgeClass = 'badge-intake';
        if (evt.actor_type === 'technician') actorBadgeClass = 'badge-repair_in_progress';
        if (evt.actor_type === 'customer') actorBadgeClass = 'badge-customer_approved';
        if (evt.actor_type === 'system') actorBadgeClass = 'badge-closed';

        return (
          <div
            key={evt.event_id}
            style={{
              border: '1px solid var(--slate-200)',
              borderRadius: '6px',
              padding: '0.75rem 1rem',
              backgroundColor: '#ffffff',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span className={`badge ${actorBadgeClass}`}>{evt.actor_type}</span>
                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{evt.action}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>
                  ({evt.from_state} → {evt.to_state})
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '0.725rem', color: 'var(--slate-400)' }}>
                  v{evt.version_before} → v{evt.version_after}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>{timeFormatted}</span>
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : evt.event_id)}
                  className="btn btn-secondary"
                  style={{ padding: '0.15rem 0.4rem', fontSize: '0.7rem' }}
                >
                  {isExpanded ? 'Hide' : 'Details'}
                </button>
              </div>
            </div>

            {isExpanded && (
              <div
                style={{
                  marginTop: '0.5rem',
                  padding: '0.5rem',
                  backgroundColor: 'var(--slate-50)',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontFamily: 'monospace',
                }}
              >
                <div>Actor Name: {evt.actor_name}</div>
                {evt.idempotency_key && <div>Idempotency Key: {evt.idempotency_key}</div>}
                <pre style={{ marginTop: '0.25rem', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(evt.payload, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
