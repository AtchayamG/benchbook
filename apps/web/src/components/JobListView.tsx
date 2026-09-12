import React, { useState } from 'react';
import type { Job, JobState } from '../types/benchbook';

interface JobListViewProps {
  jobs: Job[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  onOpenIntake: () => void;
  onSeedJobs: () => void;
  isLoading: boolean;
}

export const JobListView: React.FC<JobListViewProps> = ({
  jobs,
  selectedJobId,
  onSelectJob,
  onOpenIntake,
  onSeedJobs,
  isLoading,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [stateFilter, setStateFilter] = useState<string>('all');

  const filteredJobs = jobs.filter((j) => {
    const matchesSearch =
      j.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      j.job_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      j.device_kind.toLowerCase().includes(searchTerm.toLowerCase()) ||
      j.brand_model.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesFilter = stateFilter === 'all' || j.current_state === stateFilter;
    return matchesSearch && matchesFilter;
  });

  const getStateBadgeClass = (state: JobState) => `badge badge-${state}`;

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div>
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Repair Bench</h2>
          <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>
            {jobs.length} total active jobs
          </span>
        </div>
        <button type="button" onClick={onOpenIntake} className="btn btn-primary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>
          + New Intake
        </button>
      </div>

      {/* Filter and Search */}
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--slate-200)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <input
          type="text"
          className="form-input"
          placeholder="Search customer, job #, model..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
        />
        <select
          className="form-select"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          style={{ fontSize: '0.8rem', padding: '0.35rem 0.6rem' }}
        >
          <option value="all">All States ({jobs.length})</option>
          <option value="intake">State: Intake</option>
          <option value="diagnosis">State: Diagnosis</option>
          <option value="parts_lookup">State: Parts Lookup</option>
          <option value="estimate_pending">State: Estimate Pending</option>
          <option value="customer_approved">State: Customer Approved</option>
          <option value="parts_ready">State: Parts Ready</option>
          <option value="repair_queue">State: Repair Queue</option>
          <option value="repair_in_progress">State: In Progress</option>
          <option value="repair_completed">State: Repair Completed</option>
          <option value="ready_for_pickup">State: Ready for Pickup</option>
          <option value="follow_up">State: Follow-up</option>
          <option value="closed">State: Closed</option>
        </select>
      </div>

      {/* List */}
      <div className="job-list">
        {isLoading && jobs.length === 0 ? (
          <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--slate-400)', fontSize: '0.85rem' }}>
            Loading repair bench...
          </div>
        ) : filteredJobs.length === 0 ? (
          <div style={{ padding: '2rem 1rem', textAlign: 'center' }}>
            <p style={{ color: 'var(--slate-500)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              No repair jobs found.
            </p>
            <button
              type="button"
              onClick={onSeedJobs}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', width: '100%' }}
            >
              Seed 4 Tamil Nadu Preset Jobs
            </button>
          </div>
        ) : (
          filteredJobs.map((j) => {
            const isSelected = j.job_id === selectedJobId;
            return (
              <div
                key={j.job_id}
                className={`job-item ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectJob(j.job_id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--slate-900)' }}>
                    {j.job_number}
                  </span>
                  <span className={getStateBadgeClass(j.current_state)}>
                    {j.current_state.replace('_', ' ')}
                  </span>
                </div>

                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--slate-800)', marginBottom: '0.15rem' }}>
                  {j.customer_name}
                </div>

                <div style={{ fontSize: '0.775rem', color: 'var(--slate-600)', marginBottom: '0.25rem' }}>
                  {j.brand_model} • <span style={{ color: 'var(--slate-500)' }}>{j.device_kind}</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--slate-400)' }}>
                  <span>Promised: {j.promised_date || 'Standard'}</span>
                  <span>v{j.version}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
