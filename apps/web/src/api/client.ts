import type {
  AssistantDraftMessageResponse,
  AssistantPartsSuggestionResponse,
  AuditEvent,
  Job,
  JobDetails,
} from '../types/benchbook';

const API_BASE = '/api';

export class ApiError extends Error {
  constructor(
    public status: number,
    public error: string,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errJson: { error?: string; message?: string; details?: Record<string, unknown> } = {};
    try {
      errJson = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(
      res.status,
      errJson.error || 'UNKNOWN_ERROR',
      errJson.message || `Request failed with status ${res.status}`,
      errJson.details
    );
  }
  return res.json();
}

export const api = {
  async getHealth(): Promise<{ status: string; app: string; milestone: string; shop: { name: string } }> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse(res);
  },

  async getJobs(state?: string): Promise<{ jobs: Job[]; count: number }> {
    const url = state ? `${API_BASE}/jobs?state=${encodeURIComponent(state)}` : `${API_BASE}/jobs`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getJobDetails(jobId: string): Promise<JobDetails> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`);
    return handleResponse(res);
  },

  async getAuditTrail(jobId: string): Promise<{ job_id: string; audit_events: AuditEvent[] }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/audit`);
    return handleResponse(res);
  },

  async createJob(payload: {
    customer_name: string;
    customer_phone: string;
    customer_address?: string | null;
    device_kind: string;
    brand_model: string;
    serial_number?: string | null;
    intake_symptoms: string;
    physical_condition?: string | null;
    accessories_received?: string[];
    promised_date?: string | null;
    assigned_technician?: string | null;
    idempotency_key?: string | null;
  }): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async seedSampleJobs(): Promise<{ message: string; jobs: Job[] }> {
    const res = await fetch(`${API_BASE}/jobs/seed`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async addTechnicianNote(
    jobId: string,
    payload: {
      expected_version: number;
      technician_name: string;
      diagnosis_findings: string;
      root_cause: string;
      recommended_action: string;
      test_measurements?: Record<string, unknown>;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/technician-note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async addPartsLookup(
    jobId: string,
    payload: {
      expected_version: number;
      parts: Array<{
        part_name: string;
        part_number?: string | null;
        supplier_name?: string | null;
        unit_cost_inr: number;
        quantity: number;
        availability_status: string;
        suggested_by: string;
      }>;
      actor_name: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/parts-lookup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async createEstimate(
    jobId: string,
    payload: {
      expected_version: number;
      labor_charge_inr: number;
      parts_total_inr: number;
      tax_inr: number;
      total_amount_inr: number;
      promised_delivery_date?: string | null;
      notes?: string | null;
      created_by: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/estimate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async recordCustomerApproval(
    jobId: string,
    payload: {
      expected_version: number;
      approved: boolean;
      approved_by: string;
      recorded_by_technician: string;
      channel: string;
      approval_notes?: string | null;
      agreed_amount_inr: number;
      actor_type?: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/customer-approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async updateSupplierStatus(
    jobId: string,
    payload: {
      expected_version: number;
      supplier_name: string;
      order_reference?: string | null;
      parts_status: string;
      expected_arrival_date?: string | null;
      tracking_notes?: string | null;
      actor_name: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/supplier-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async transitionRepairQueue(
    jobId: string,
    payload: {
      expected_version: number;
      target_state: string;
      actor_name: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/repair-queue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async recordRepairCompletion(
    jobId: string,
    payload: {
      expected_version: number;
      technician_name: string;
      actions_taken: string;
      parts_replaced: string[];
      qc_tests_passed: string[];
      burn_in_duration_minutes: number;
      technician_signature_confirmed: boolean;
      actor_type?: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/repair-completion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async recordPickupNotification(
    jobId: string,
    payload: {
      expected_version: number;
      channel: string;
      recipient_phone: string;
      message_text: string;
      sent_by_technician: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/pickup-notification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async recordFollowUp(
    jobId: string,
    payload: {
      expected_version: number;
      amount_paid_inr: number;
      payment_method: string;
      payment_reference?: string | null;
      warranty_days: number;
      customer_feedback?: string | null;
      feedback_rating?: number | null;
      recorded_by: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/follow-up`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async recordJobClose(
    jobId: string,
    payload: {
      expected_version: number;
      closed_by: string;
      resolution_summary: string;
      actor_type?: string;
      idempotency_key?: string | null;
    }
  ): Promise<{ job: Job }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async assistantSuggestParts(payload: {
    device_kind: string;
    symptoms: string;
    findings?: string | null;
  }): Promise<AssistantPartsSuggestionResponse> {
    const res = await fetch(`${API_BASE}/assistant/suggest-parts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async assistantDraftEstimateMessage(payload: {
    customer_name: string;
    device_kind: string;
    brand_model: string;
    labor_charge_inr: number;
    parts_total_inr: number;
    tax_inr: number;
    total_amount_inr: number;
    promised_date?: string | null;
  }): Promise<AssistantDraftMessageResponse> {
    const res = await fetch(`${API_BASE}/assistant/draft-estimate-message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async assistantDraftPickupNotification(payload: {
    customer_name: string;
    device_kind: string;
    brand_model: string;
    total_amount_inr: number;
    warranty_days?: number;
  }): Promise<AssistantDraftMessageResponse> {
    const res = await fetch(`${API_BASE}/assistant/draft-pickup-notification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },
};
