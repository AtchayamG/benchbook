import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { api } from '../api/client';
import type { Job, JobDetails } from '../types/benchbook';

const mockJob: Job = {
  job_id: 'test-uuid-101',
  job_number: 'BB-2026-101',
  customer_name: 'Senthil Nathan',
  customer_phone: '+91 98401 23456',
  customer_address: 'Gandhipuram, Coimbatore',
  device_kind: 'BLDC Ceiling Fan',
  brand_model: 'Atomberg Renesa 1200mm',
  serial_number: 'ATMB-2024-88419',
  intake_symptoms: 'Motor humming loudly at speed 2',
  physical_condition: 'Good',
  accessories_received: ['Remote'],
  promised_date: '2026-09-15',
  assigned_technician: 'Murugan R.',
  current_state: 'intake',
  version: 1,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockDetails: JobDetails = {
  job: mockJob,
  technician_notes: [],
  parts: [],
  estimate: null,
  customer_approval: null,
  supplier_statuses: [],
  repair_completion: null,
  pickup_notifications: [],
  follow_up: null,
  job_close: null,
  audit_events: [
    {
      event_id: 'evt-1',
      job_id: 'test-uuid-101',
      from_state: 'none',
      to_state: 'intake',
      action: 'create_job',
      actor_type: 'technician',
      actor_name: 'Murugan R.',
      version_before: 0,
      version_after: 1,
      payload: { job_number: 'BB-2026-101' },
      created_at: new Date().toISOString(),
    },
  ],
};

describe('Benchbook Frontend Workflow Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    vi.spyOn(api, 'getHealth').mockResolvedValue({
      status: 'ok',
      app: 'Benchbook',
      milestone: 'M1',
      shop: { name: 'Kovai Tech Bench' },
    });

    vi.spyOn(api, 'getJobs').mockResolvedValue({
      jobs: [mockJob],
      count: 1,
    });

    vi.spyOn(api, 'getJobDetails').mockResolvedValue(mockDetails);
  });

  it('renders application header with shop identity and M1 milestone', async () => {
    render(<App />);

    expect(screen.getByText('Benchbook')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Kovai Tech Bench/)).toBeInTheDocument();
      expect(screen.getByText('Milestone M1')).toBeInTheDocument();
    });
  });

  it('renders active repair jobs and displays details on selection', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText('BB-2026-101').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Senthil Nathan').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Atomberg Renesa 1200mm/).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows visual timeline with current state active', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('1. Intake')).toBeInTheDocument();
      expect(screen.getByText('2. Diagnosis')).toBeInTheDocument();
      expect(screen.getByText('4. Estimate')).toBeInTheDocument();
    });
  });

  it('renders diagnosis action form when job is at intake stage', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Current Stage Action: INTAKE/)).toBeInTheDocument();
      expect(screen.getByText('Save Diagnosis & Proceed to Parts')).toBeInTheDocument();
    });
  });

  it('shows human gate alert when job is at estimate_pending state', async () => {
    const pendingJob: Job = { ...mockJob, current_state: 'estimate_pending', version: 4 };
    const pendingDetails: JobDetails = { ...mockDetails, job: pendingJob };

    vi.spyOn(api, 'getJobs').mockResolvedValue({ jobs: [pendingJob], count: 1 });
    vi.spyOn(api, 'getJobDetails').mockResolvedValue(pendingDetails);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Human Approval Gate:/)).toBeInTheDocument();
      expect(screen.getByText('Record Customer Authorization')).toBeInTheDocument();
    });
  });

  it('shows human gate alert when job is at repair_in_progress state', async () => {
    const progressJob: Job = { ...mockJob, current_state: 'repair_in_progress', version: 8 };
    const progressDetails: JobDetails = { ...mockDetails, job: progressJob };

    vi.spyOn(api, 'getJobs').mockResolvedValue({ jobs: [progressJob], count: 1 });
    vi.spyOn(api, 'getJobDetails').mockResolvedValue(progressDetails);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Human Technician Sign-Off Gate:/)).toBeInTheDocument();
      expect(screen.getByText(/Sign-off QC & Mark Repair Completed/)).toBeInTheDocument();
    });
  });

  it('displays audit events with monotonic version transitions', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText('BB-2026-101').length).toBeGreaterThanOrEqual(1);
    });

    const auditTabBtn = screen.getByText(/Audit Stream/);
    fireEvent.click(auditTabBtn);

    await waitFor(() => {
      expect(screen.getByText('create_job')).toBeInTheDocument();
      expect(screen.getByText('v0 → v1')).toBeInTheDocument();
    });
  });
});
