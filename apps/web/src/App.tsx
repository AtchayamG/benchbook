import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api/client';
import { JobDetailPanel } from './components/JobDetailPanel';
import { JobIntakeModal } from './components/JobIntakeModal';
import { JobListView } from './components/JobListView';
import type { Job, JobDetails, SessionResponse } from './types/benchbook';

export const App: React.FC = () => {
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const selectedIdRef = useRef<string | null>(null);
  const detailRequest = useRef(0);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetails, setJobDetails] = useState<JobDetails | null>(null);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [isIntakeOpen, setIsIntakeOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(true);
  const [healthInfo, setHealthInfo] = useState<{
    app: string;
    milestone: string;
    shop: { name: string };
    database?: { engine: string; status: string };
    assistant?: { mode: string };
  } | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await api.getJobs();
      setJobs(res.jobs);
      setSelectedJobId((previous) => previous || res.jobs[0]?.job_id || null);
      setConnectionError(null);
    } catch (err) {
      setConnectionError(err instanceof Error ? err.message : 'Workbench connection unavailable.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchSelectedJob = async (jobId: string) => {
    const requestId = ++detailRequest.current;
    try {
      const details = await api.getJobDetails(jobId);
      if (requestId === detailRequest.current && selectedIdRef.current === jobId) setJobDetails(details);
    } catch (err) {
      console.error('Failed to fetch job details', err);
    }
  };

  useEffect(() => {
    let stopped = false;
    api.initSession().then(async (current) => {
      if (stopped) return;
      setSession(current);
      await fetchJobs();
    }).catch((error: unknown) => {
      if (!stopped) {
        setConnectionError(error instanceof Error ? error.message : 'Could not start workbench.');
        setIsLoading(false);
      }
    });
    api.getHealth().then(setHealthInfo).catch(() => undefined);
    return () => { stopped = true; };
  }, [fetchJobs]);

  useEffect(() => {
    selectedIdRef.current = selectedJobId;
    setJobDetails(null);
    if (selectedJobId) {
      fetchSelectedJob(selectedJobId);
    } else {
      setJobDetails(null);
    }
  }, [selectedJobId]);

  const handleSeedJobs = async () => {
    try {
      await api.seedSampleJobs();
      await fetchJobs();
    } catch (err) {
      setConnectionError(err instanceof Error ? err.message : 'Could not load sample jobs.');
    }
  };

  const handleJobCreated = (newJob: Job) => {
    setJobs((prev) => [newJob, ...prev]);
    setSelectedJobId(newJob.job_id);
  };

  const handleRefresh = () => {
    if (selectedJobId) {
      fetchSelectedJob(selectedJobId);
    }
    api.getSession().then(setSession).catch(console.error);
    fetchJobs();
  };

  return (
    <div>
      {/* Top Header */}
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.4rem' }}>🛠️</span>
            <div>
              <h1 style={{ fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                Benchbook
              </h1>
              <span style={{ fontSize: '0.725rem', color: 'var(--slate-500)' }}>
                Professional Repair Shop Workflow
              </span>
            </div>
          </div>
          <span className="brand-badge">
            {healthInfo?.shop?.name || 'Kovai Tech Bench'} • Coimbatore, TN
          </span>
          <span style={{ fontSize: '0.75rem', backgroundColor: '#e2e8f0', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
            Milestone {healthInfo?.milestone || 'M1'}
          </span>
          <span style={{ fontSize: '0.75rem', backgroundColor: '#e0e7ff', color: '#3730a3', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
            DB: {healthInfo?.database?.engine === 'postgres' ? 'PostgreSQL' : 'SQLite'}
          </span>
          {session && (
            <span
              style={{
                fontSize: '0.75rem',
                backgroundColor: '#f1f5f9',
                color: '#334155',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                fontWeight: 600,
                border: '1px solid #cbd5e1',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
              }}
              title={`Workbench Workspace ID: ${session.workspace_id}\nExpires: ${session.expires_at}`}
            >
              🔒 <span>Workbench: <code style={{ fontSize: '0.7rem' }}>{session.workspace_id.substring(0, 8)}...</code></span>
              <span style={{ color: jobs.length >= 50 ? '#dc2626' : '#0284c7' }}>
                ({jobs.length}/50 jobs)
              </span>
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }}></span>
            Assistant: {healthInfo?.assistant?.mode === 'live' ? 'Strands / Groq' : healthInfo?.assistant?.mode === 'deterministic' ? 'Offline catalogue' : healthInfo?.assistant?.mode === 'offline_transport_test' ? 'Offline transport test' : 'Checking availability'} (Advisory Only)
          </span>
          <button
            type="button"
            onClick={handleRefresh}
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
          >
            ↻ Refresh
          </button>
        </div>
      </header>

      {connectionError && <div role="alert" style={{ padding: '1rem', color: '#991b1b' }}>
        {connectionError} Free hosting may need a moment to wake up.
        <button type="button" className="btn btn-secondary" onClick={() => window.location.reload()}>Reconnect workbench</button>
      </div>}
      <p style={{ padding: '0.5rem 1rem', fontSize: '0.8rem' }}>Public demo: use synthetic customer details only. Messages stay as drafts; no messages are sent.</p>
      {/* Capacity Warning Banner */}
      {jobs.length >= 50 && (
        <div style={{ backgroundColor: '#fef2f2', color: '#991b1b', padding: '0.5rem 1rem', fontSize: '0.8rem', borderBottom: '1px solid #fecaca', fontWeight: 600 }}>
          ⚠️ Workspace Capacity Reached: 50 / 50 active jobs limit in this isolated workbench. This workbench has reached its storage limit.
        </div>
      )}

      {/* Evaluator & Judge Walkthrough Guide */}
      {showGuide && (
        <div className="evaluator-guide-banner">
          <div className="evaluator-guide-content">
            <div className="evaluator-guide-title">
              <span>💡</span>
              <strong>Evaluator Guide (60-Second Walkthrough):</strong>
            </div>
            <p className="evaluator-guide-text">
              <strong>Benchbook keeps a repair shop moving from intake to pickup without making the technician become a full-time coordinator.</strong>{' '}
              The technician owns diagnostic and repair authority across 11 persisted stages. The Assistant suggests parts &amp; drafts messages with explicit provenance, but
              <strong> CANNOT</strong> approve estimates, sign off QC completion, or close jobs (indicated by 🔒 locks on the timeline).
              Click <em>&ldquo;Seed Sample Jobs&rdquo;</em> on the left bench to load contact-safe Tamil Nadu repair presets (Atomberg Fan, Voltas AC PCB, Preethi Mixer, ThinkPad Laptop).
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowGuide(false)}
            className="evaluator-guide-close"
            aria-label="Dismiss Evaluator Guide"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Container */}
      <div className="app-container">
        <JobListView
          jobs={jobs}
          selectedJobId={selectedJobId}
          onSelectJob={setSelectedJobId}
          onOpenIntake={() => setIsIntakeOpen(true)}
          onSeedJobs={handleSeedJobs}
          isLoading={isLoading}
        />

        {jobDetails ? (
          <JobDetailPanel key={`${jobDetails.job.job_id}:${jobDetails.job.version}`} details={jobDetails} onRefresh={handleRefresh} />
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--slate-400)' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📋</div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--slate-700)' }}>
              No Repair Job Selected
            </h3>
            <p style={{ fontSize: '0.875rem', maxWidth: '400px', textAlign: 'center', marginBottom: '1.25rem' }}>
              Select an existing repair ticket from the left bench or create a new customer intake.
            </p>
            <button
              type="button"
              onClick={() => setIsIntakeOpen(true)}
              className="btn btn-primary"
            >
              + Create New Intake
            </button>
          </div>
        )}
      </div>

      <JobIntakeModal
        isOpen={isIntakeOpen}
        onClose={() => setIsIntakeOpen(false)}
        onJobCreated={handleJobCreated}
      />
    </div>
  );
};

export default App;
