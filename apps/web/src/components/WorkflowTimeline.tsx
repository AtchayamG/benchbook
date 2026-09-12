import React from 'react';
import type { JobState } from '../types/benchbook';

interface WorkflowTimelineProps {
  currentState: JobState;
}

const STAGES: { key: JobState; label: string }[] = [
  { key: 'intake', label: '1. Intake' },
  { key: 'diagnosis', label: '2. Diagnosis' },
  { key: 'parts_lookup', label: '3. Parts' },
  { key: 'estimate_pending', label: '4. Estimate' },
  { key: 'customer_approved', label: '5. Approved' },
  { key: 'parts_ready', label: '6. Supplier' },
  { key: 'repair_queue', label: '7. Queue' },
  { key: 'repair_in_progress', label: '8. Bench' },
  { key: 'repair_completed', label: '9. Completed' },
  { key: 'ready_for_pickup', label: '10. Pickup' },
  { key: 'follow_up', label: '11. Settlement' },
  { key: 'closed', label: '12. Closed' },
];

export const WorkflowTimeline: React.FC<WorkflowTimelineProps> = ({ currentState }) => {
  const currentIndex = STAGES.findIndex((s) => s.key === currentState);

  return (
    <div className="card mb-4">
      <div className="card-body py-3">
        <div className="timeline">
          {STAGES.map((stage, idx) => {
            let statusClass = '';
            if (stage.key === currentState) {
              statusClass = 'active';
            } else if (currentIndex > -1 && idx < currentIndex) {
              statusClass = 'completed';
            }

            return (
              <React.Fragment key={stage.key}>
                <div className={`timeline-step ${statusClass}`}>
                  <span className="timeline-dot">
                    {idx < currentIndex ? '✓' : idx + 1}
                  </span>
                  <span>{stage.label}</span>
                </div>
                {idx < STAGES.length - 1 && <div className="timeline-line" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
};
