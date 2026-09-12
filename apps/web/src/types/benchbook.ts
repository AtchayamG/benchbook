export type JobState =
  | 'intake'
  | 'diagnosis'
  | 'parts_lookup'
  | 'estimate_pending'
  | 'customer_approved'
  | 'estimate_rejected'
  | 'supplier_ordered'
  | 'parts_ready'
  | 'repair_queue'
  | 'repair_in_progress'
  | 'repair_completed'
  | 'ready_for_pickup'
  | 'follow_up'
  | 'closed';

export interface Job {
  job_id: string;
  job_number: string;
  customer_name: string;
  customer_phone: string;
  customer_address?: string | null;
  device_kind: string;
  brand_model: string;
  serial_number?: string | null;
  intake_symptoms: string;
  physical_condition?: string | null;
  accessories_received: string[];
  promised_date?: string | null;
  assigned_technician?: string | null;
  current_state: JobState;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TechnicianNote {
  note_id: string;
  job_id: string;
  technician_name: string;
  diagnosis_findings: string;
  root_cause: string;
  recommended_action: string;
  test_measurements: Record<string, unknown>;
  created_at: string;
}

export interface PartItem {
  part_id: string;
  job_id: string;
  part_name: string;
  part_number?: string | null;
  supplier_name?: string | null;
  unit_cost_inr: number;
  quantity: number;
  availability_status: string;
  suggested_by: string;
  created_at: string;
}

export interface Estimate {
  estimate_id: string;
  job_id: string;
  labor_charge_inr: number;
  parts_total_inr: number;
  tax_inr: number;
  total_amount_inr: number;
  promised_delivery_date?: string | null;
  notes?: string | null;
  created_by: string;
  created_at: string;
}

export interface CustomerApproval {
  approval_id: string;
  job_id: string;
  approved: boolean;
  approved_by: string;
  recorded_by_technician: string;
  channel: string;
  approval_notes?: string | null;
  agreed_amount_inr: number;
  approved_at: string;
}

export interface SupplierStatus {
  status_id: string;
  job_id: string;
  supplier_name: string;
  order_reference?: string | null;
  parts_status: string;
  expected_arrival_date?: string | null;
  tracking_notes?: string | null;
  updated_at: string;
}

export interface RepairCompletion {
  completion_id: string;
  job_id: string;
  technician_name: string;
  actions_taken: string;
  parts_replaced: string[];
  qc_tests_passed: string[];
  burn_in_duration_minutes: number;
  technician_signature_confirmed: boolean;
  completed_at: string;
}

export interface PickupNotification {
  notification_id: string;
  job_id: string;
  channel: string;
  recipient_phone: string;
  message_text: string;
  sent_by_technician: string;
  sent_at: string;
}

export interface FollowUpRecord {
  followup_id: string;
  job_id: string;
  picked_up_at: string;
  amount_paid_inr: number;
  payment_method: string;
  payment_reference?: string | null;
  warranty_days: number;
  customer_feedback?: string | null;
  feedback_rating?: number | null;
  recorded_by: string;
  recorded_at: string;
}

export interface JobClose {
  close_id: string;
  job_id: string;
  closed_by: string;
  resolution_summary: string;
  closed_at: string;
}

export interface AuditEvent {
  event_id: string;
  job_id: string;
  from_state: string;
  to_state: string;
  action: string;
  actor_type: 'technician' | 'customer' | 'system' | 'assistant';
  actor_name: string;
  idempotency_key?: string | null;
  version_before: number;
  version_after: number;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface JobDetails {
  job: Job;
  technician_notes: TechnicianNote[];
  parts: PartItem[];
  estimate: Estimate | null;
  customer_approval: CustomerApproval | null;
  supplier_statuses: SupplierStatus[];
  repair_completion: RepairCompletion | null;
  pickup_notifications: PickupNotification[];
  follow_up: FollowUpRecord | null;
  job_close: JobClose | null;
  audit_events: AuditEvent[];
}

export interface AssistantProvenance {
  engine: string;
  model: string;
  generated_at: string;
  advisory_only: boolean;
  requires_human_verification: boolean;
}

export interface PartSuggestionItem {
  part_name: string;
  part_number?: string;
  supplier_name?: string;
  unit_cost_inr: number;
  availability_status: string;
  relevance_reason?: string;
}

export interface AssistantPartsSuggestionResponse {
  device_kind: string;
  symptoms_analyzed: string;
  suggestions: PartSuggestionItem[];
  confidence_score: number;
  provenance: AssistantProvenance;
}

export interface AssistantDraftMessageResponse {
  channel: string;
  message_text: string;
  character_count: number;
  provenance: AssistantProvenance;
}

export interface HealthResponse {
  status: string;
  app: string;
  milestone: string;
  shop: { name: string; location?: string; phone?: string };
  database?: {
    engine: string;
    status: string;
    connected?: boolean;
  };
  assistant?: {
    mode: string;
    human_approval_required: boolean;
  };
}
