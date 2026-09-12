import React, { useState } from 'react';
import { api, ApiError } from '../api/client';
import type {
  AssistantDraftMessageResponse,
  AssistantPartsSuggestionResponse,
  JobDetails,
} from '../types/benchbook';
import { AssistantAdvisoryCard } from './AssistantAdvisoryCard';
import { AuditEventStream } from './AuditEventStream';
import { WorkflowTimeline } from './WorkflowTimeline';

interface JobDetailPanelProps {
  details: JobDetails;
  onRefresh: () => void;
}

export const JobDetailPanel: React.FC<JobDetailPanelProps> = ({ details, onRefresh }) => {
  const { job } = details;
  const [activeTab, setActiveTab] = useState<'action' | 'records' | 'audit'>('action');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Assistant states
  const [partsSuggestion, setPartsSuggestion] = useState<AssistantPartsSuggestionResponse | null>(null);
  const [estimateDraft, setEstimateDraft] = useState<AssistantDraftMessageResponse | null>(null);
  const [pickupDraft, setPickupDraft] = useState<AssistantDraftMessageResponse | null>(null);

  // Form states for transitions
  const [noteForm, setNoteForm] = useState({
    technician_name: job.assigned_technician || 'Murugan R.',
    diagnosis_findings: '',
    root_cause: '',
    recommended_action: '',
    test_measurements: '{"dc_volts": 230, "coil_resistance_ohms": 12.4}',
  });

  const [partsForm, setPartsForm] = useState({
    part_name: '',
    part_number: '',
    supplier_name: 'Supreme Electronics Spares, Cross Cut Road, Coimbatore',
    unit_cost_inr: 0,
    quantity: 1,
    availability_status: 'in_stock',
  });

  const [estimateForm, setEstimateForm] = useState({
    labor_charge_inr: 450,
    parts_total_inr: details.parts.reduce((acc, p) => acc + p.unit_cost_inr * p.quantity, 0) || 350,
    tax_inr: 144,
    notes: 'Standard bench labor, ultrasonic flux cleaning, 2-hour burn-in.',
    promised_delivery_date: job.promised_date || '2026-09-16',
    created_by: job.assigned_technician || 'Murugan R.',
  });

  const [approvalForm, setApprovalForm] = useState({
    approved: true,
    approved_by: job.customer_name,
    recorded_by_technician: job.assigned_technician || 'Murugan R.',
    channel: 'phone',
    approval_notes: 'Customer confirmed estimate over phone.',
    agreed_amount_inr: details.estimate?.total_amount_inr || 944,
  });

  const [supplierForm, setSupplierForm] = useState({
    supplier_name: 'Supreme Electronics Spares, Cross Cut Road',
    order_reference: 'SES-CBE-2026-042',
    parts_status: 'in_stock',
    expected_arrival_date: '2026-09-14',
    tracking_notes: 'Collected over counter',
    actor_name: job.assigned_technician || 'Murugan R.',
  });

  const [completionForm, setCompletionForm] = useState({
    technician_name: job.assigned_technician || 'Murugan R.',
    actions_taken: 'Replaced defective components, cleaned PCB, checked solder joints.',
    parts_replaced: details.parts.map((p) => p.part_name).join(', ') || 'Driver IC, Capacitor',
    qc_tests_passed: 'Phase voltage balance verified, full load test passed, thermal stable',
    burn_in_duration_minutes: 120,
    technician_signature_confirmed: true,
  });

  const [notificationForm, setNotificationForm] = useState({
    channel: 'whatsapp',
    recipient_phone: job.customer_phone,
    message_text: `Vanakkam ${job.customer_name}, your ${job.brand_model} (${job.device_kind}) is repaired and ready for pickup at Kovai Tech Bench!`,
    sent_by_technician: job.assigned_technician || 'Murugan R.',
  });

  const [followupForm, setFollowupForm] = useState({
    amount_paid_inr: details.estimate?.total_amount_inr || 944,
    payment_method: 'upi',
    payment_reference: 'UPI/20260915/998124',
    warranty_days: 30,
    customer_feedback: 'Device tested on pickup bench, customer fully satisfied.',
    feedback_rating: 5,
    recorded_by: job.assigned_technician || 'Murugan R.',
  });

  const [closeForm, setCloseForm] = useState({
    closed_by: job.assigned_technician || 'Murugan R.',
    resolution_summary: 'Repair verified, device handed over to customer, payment settled, 30-day warranty active.',
  });

  // Action Handlers
  const handleActionError = (err: unknown) => {
    if (err instanceof ApiError) {
      if (err.status === 409) {
        setErrorMsg(`[State Conflict 409] Job was modified elsewhere (expected v${job.version}). Refreshing latest state...`);
        onRefresh();
        return;
      }
      if (err.status === 403) {
        setErrorMsg(`[Human Approval Required 403] ${err.message}`);
        return;
      }
      setErrorMsg(`[${err.error} ${err.status}] ${err.message}`);
    } else {
      setErrorMsg(err instanceof Error ? err.message : 'Unknown error occurred');
    }
  };

  // 1. Submit Note
  const submitTechnicianNote = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      let measurements: Record<string, unknown> = {};
      try {
        measurements = JSON.parse(noteForm.test_measurements);
      } catch {
        // keep empty
      }
      await api.addTechnicianNote(job.job_id, {
        expected_version: job.version,
        technician_name: noteForm.technician_name,
        diagnosis_findings: noteForm.diagnosis_findings,
        root_cause: noteForm.root_cause,
        recommended_action: noteForm.recommended_action,
        test_measurements: measurements,
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 2. Submit Parts
  const submitPartsLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.addPartsLookup(job.job_id, {
        expected_version: job.version,
        parts: [
          {
            part_name: partsForm.part_name,
            part_number: partsForm.part_number || null,
            supplier_name: partsForm.supplier_name,
            unit_cost_inr: Number(partsForm.unit_cost_inr),
            quantity: Number(partsForm.quantity),
            availability_status: partsForm.availability_status,
            suggested_by: 'technician',
          },
        ],
        actor_name: job.assigned_technician || 'Murugan R.',
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 3. Submit Estimate
  const submitEstimate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const labor = Number(estimateForm.labor_charge_inr);
      const parts = Number(estimateForm.parts_total_inr);
      const tax = Number(estimateForm.tax_inr);
      const total = labor + parts + tax;

      await api.createEstimate(job.job_id, {
        expected_version: job.version,
        labor_charge_inr: labor,
        parts_total_inr: parts,
        tax_inr: tax,
        total_amount_inr: total,
        promised_delivery_date: estimateForm.promised_delivery_date,
        notes: estimateForm.notes,
        created_by: estimateForm.created_by,
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 4. Submit Customer Approval (Human Gate)
  const submitCustomerApproval = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.recordCustomerApproval(job.job_id, {
        expected_version: job.version,
        approved: approvalForm.approved,
        approved_by: approvalForm.approved_by,
        recorded_by_technician: approvalForm.recorded_by_technician,
        channel: approvalForm.channel,
        approval_notes: approvalForm.approval_notes,
        agreed_amount_inr: Number(approvalForm.agreed_amount_inr),
        actor_type: 'technician', // HUMAN GATE
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 5. Submit Supplier Status
  const submitSupplierStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.updateSupplierStatus(job.job_id, {
        expected_version: job.version,
        supplier_name: supplierForm.supplier_name,
        order_reference: supplierForm.order_reference,
        parts_status: supplierForm.parts_status,
        expected_arrival_date: supplierForm.expected_arrival_date,
        tracking_notes: supplierForm.tracking_notes,
        actor_name: supplierForm.actor_name,
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 6. Move Queue / Bench
  const handleTransitionQueue = async (targetState: 'repair_queue' | 'repair_in_progress') => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.transitionRepairQueue(job.job_id, {
        expected_version: job.version,
        target_state: targetState,
        actor_name: job.assigned_technician || 'Murugan R.',
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 7. Submit Repair Completion (Human Gate)
  const submitRepairCompletion = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const parts = completionForm.parts_replaced
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const qcTests = completionForm.qc_tests_passed
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      await api.recordRepairCompletion(job.job_id, {
        expected_version: job.version,
        technician_name: completionForm.technician_name,
        actions_taken: completionForm.actions_taken,
        parts_replaced: parts,
        qc_tests_passed: qcTests,
        burn_in_duration_minutes: Number(completionForm.burn_in_duration_minutes),
        technician_signature_confirmed: completionForm.technician_signature_confirmed,
        actor_type: 'technician', // HUMAN GATE
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 8. Submit Pickup Notification
  const submitPickupNotification = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.recordPickupNotification(job.job_id, {
        expected_version: job.version,
        channel: notificationForm.channel,
        recipient_phone: notificationForm.recipient_phone,
        message_text: notificationForm.message_text,
        sent_by_technician: notificationForm.sent_by_technician,
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 9. Submit Follow-up / Settlement
  const submitFollowup = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.recordFollowUp(job.job_id, {
        expected_version: job.version,
        amount_paid_inr: Number(followupForm.amount_paid_inr),
        payment_method: followupForm.payment_method,
        payment_reference: followupForm.payment_reference,
        warranty_days: Number(followupForm.warranty_days),
        customer_feedback: followupForm.customer_feedback,
        feedback_rating: Number(followupForm.feedback_rating),
        recorded_by: followupForm.recorded_by,
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 10. Submit Close Job (Human Gate)
  const submitCloseJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await api.recordJobClose(job.job_id, {
        expected_version: job.version,
        closed_by: closeForm.closed_by,
        resolution_summary: closeForm.resolution_summary,
        actor_type: 'technician', // HUMAN GATE
      });
      onRefresh();
    } catch (err) {
      handleActionError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Assistant triggers
  const triggerPartsSuggestion = async () => {
    try {
      const res = await api.assistantSuggestParts({
        device_kind: job.device_kind,
        symptoms: job.intake_symptoms,
      });
      setPartsSuggestion(res);
      if (res.suggestions.length > 0) {
        const top = res.suggestions[0];
        setPartsForm((prev) => ({
          ...prev,
          part_name: top.part_name,
          part_number: top.part_number || '',
          supplier_name: top.supplier_name || prev.supplier_name,
          unit_cost_inr: top.unit_cost_inr,
        }));
      }
    } catch (err) {
      handleActionError(err);
    }
  };

  const triggerEstimateDraft = async () => {
    try {
      const labor = Number(estimateForm.labor_charge_inr);
      const parts = Number(estimateForm.parts_total_inr);
      const tax = Number(estimateForm.tax_inr);
      const total = labor + parts + tax;

      const res = await api.assistantDraftEstimateMessage({
        customer_name: job.customer_name,
        device_kind: job.device_kind,
        brand_model: job.brand_model,
        labor_charge_inr: labor,
        parts_total_inr: parts,
        tax_inr: tax,
        total_amount_inr: total,
        promised_date: estimateForm.promised_delivery_date,
      });
      setEstimateDraft(res);
    } catch (err) {
      handleActionError(err);
    }
  };

  const triggerPickupDraft = async () => {
    try {
      const res = await api.assistantDraftPickupNotification({
        customer_name: job.customer_name,
        device_kind: job.device_kind,
        brand_model: job.brand_model,
        total_amount_inr: details.estimate?.total_amount_inr || 944,
        warranty_days: 30,
      });
      setPickupDraft(res);
      setNotificationForm((prev) => ({
        ...prev,
        message_text: res.message_text,
      }));
    } catch (err) {
      handleActionError(err);
    }
  };

  return (
    <div className="main-content">
      {/* Job Banner */}
      <div className="card">
        <div className="card-body" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
              <h1 style={{ fontSize: '1.4rem', fontWeight: 800 }}>{job.job_number}</h1>
              <span className={`badge badge-${job.current_state}`}>{job.current_state.replace('_', ' ')}</span>
              <span style={{ fontSize: '0.8rem', backgroundColor: 'var(--slate-100)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: 'var(--slate-600)' }}>
                Lock Version: v{job.version}
              </span>
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--slate-600)' }}>
              <strong>{job.customer_name}</strong> ({job.customer_phone}) • {job.brand_model} ({job.device_kind})
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--slate-500)' }}>Assigned: {job.assigned_technician || 'Bench Pool'}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--slate-500)' }}>Promised: {job.promised_date || 'Standard'}</div>
          </div>
        </div>
      </div>

      {/* Visual Timeline */}
      <WorkflowTimeline currentState={job.current_state} />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--slate-200)', paddingBottom: '0.5rem' }}>
        <button
          type="button"
          onClick={() => setActiveTab('action')}
          className={`btn ${activeTab === 'action' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.4rem 0.85rem' }}
        >
          Active Step Action
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('records')}
          className={`btn ${activeTab === 'records' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.4rem 0.85rem' }}
        >
          Job Records ({details.technician_notes.length + details.parts.length + (details.estimate ? 1 : 0) + (details.customer_approval ? 1 : 0) + (details.repair_completion ? 1 : 0)})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('audit')}
          className={`btn ${activeTab === 'audit' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.4rem 0.85rem' }}
        >
          Audit Stream ({details.audit_events.length})
        </button>
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div style={{ backgroundColor: '#ffe4e6', color: '#be123c', padding: '0.85rem', borderRadius: '6px', marginBottom: '1.25rem', fontSize: '0.875rem' }}>
          {errorMsg}
        </div>
      )}

      {/* TAB 1: ACTIVE STEP ACTION */}
      {activeTab === 'action' && (
        <div className="card">
          <div className="card-header">
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>
              Current Stage Action: {job.current_state.replace('_', ' ').toUpperCase()}
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>
              Idempotent & Version Guarded (Expected v{job.version})
            </span>
          </div>
          <div className="card-body">
            {/* 1. INTAKE -> DIAGNOSIS */}
            {job.current_state === 'intake' && (
              <form onSubmit={submitTechnicianNote}>
                <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)', marginBottom: '1rem' }}>
                  Technician receives device on bench. Inspect circuits, record test measurements, and identify root cause.
                </p>
                <div className="form-group">
                  <label className="form-label">Diagnosis Findings *</label>
                  <textarea
                    required
                    rows={2}
                    className="form-textarea"
                    value={noteForm.diagnosis_findings}
                    onChange={(e) => setNoteForm({ ...noteForm, diagnosis_findings: e.target.value })}
                    placeholder="e.g. Inspect motor driver PCB. Phase B gate driver FET shorted."
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group">
                    <label className="form-label">Root Cause *</label>
                    <input
                      type="text"
                      required
                      className="form-input"
                      value={noteForm.root_cause}
                      onChange={(e) => setNoteForm({ ...noteForm, root_cause: e.target.value })}
                      placeholder="e.g. Failed FD6288Q gate driver IC and dried capacitor"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Recommended Repair Action *</label>
                    <input
                      type="text"
                      required
                      className="form-input"
                      value={noteForm.recommended_action}
                      onChange={(e) => setNoteForm({ ...noteForm, recommended_action: e.target.value })}
                      placeholder="e.g. Replace gate driver IC and 450V capacitor"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Test Measurements (JSON)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={noteForm.test_measurements}
                    onChange={(e) => setNoteForm({ ...noteForm, test_measurements: e.target.value })}
                  />
                </div>
                <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                  {isSubmitting ? 'Saving Diagnosis...' : 'Save Diagnosis & Proceed to Parts'}
                </button>
              </form>
            )}

            {/* 2. DIAGNOSIS -> PARTS LOOKUP */}
            {job.current_state === 'diagnosis' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)' }}>
                    Record parts needed. You can ask the advisory assistant for local Tamil Nadu parts suggestions.
                  </p>
                  <button type="button" onClick={triggerPartsSuggestion} className="btn btn-secondary">
                    🤖 Ask Assistant for Parts Suggestions
                  </button>
                </div>

                {partsSuggestion && (
                  <AssistantAdvisoryCard title="Spare Parts Suggestions" provenance={partsSuggestion.provenance}>
                    <p style={{ marginBottom: '0.5rem' }}>
                      Based on symptoms <em>"{partsSuggestion.symptoms_analyzed}"</em>, the following parts are commonly required:
                    </p>
                    <ul style={{ paddingLeft: '1.25rem', marginBottom: '0.5rem' }}>
                      {partsSuggestion.suggestions.map((p, idx) => (
                        <li key={idx} style={{ marginBottom: '0.35rem' }}>
                          <strong>{p.part_name}</strong> ({p.part_number}) — Est. ₹{p.unit_cost_inr} ({p.supplier_name})
                          <div style={{ fontSize: '0.75rem', color: 'var(--slate-600)' }}>{p.relevance_reason}</div>
                        </li>
                      ))}
                    </ul>
                  </AssistantAdvisoryCard>
                )}

                <form onSubmit={submitPartsLookup}>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Part Name *</label>
                      <input
                        type="text"
                        required
                        className="form-input"
                        value={partsForm.part_name}
                        onChange={(e) => setPartsForm({ ...partsForm, part_name: e.target.value })}
                        placeholder="e.g. BLDC Driver Controller IC (FD6288Q)"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Part Number</label>
                      <input
                        type="text"
                        className="form-input"
                        value={partsForm.part_number}
                        onChange={(e) => setPartsForm({ ...partsForm, part_number: e.target.value })}
                        placeholder="e.g. FD6288Q"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Est. Unit Cost (₹) *</label>
                      <input
                        type="number"
                        required
                        className="form-input"
                        value={partsForm.unit_cost_inr}
                        onChange={(e) => setPartsForm({ ...partsForm, unit_cost_inr: Number(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Supplier / Local Market Source *</label>
                    <input
                      type="text"
                      required
                      className="form-input"
                      value={partsForm.supplier_name}
                      onChange={(e) => setPartsForm({ ...partsForm, supplier_name: e.target.value })}
                    />
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                    {isSubmitting ? 'Saving Parts...' : 'Record Part & Advance to Estimate'}
                  </button>
                </form>
              </div>
            )}

            {/* 3. PARTS LOOKUP -> ESTIMATE PENDING */}
            {job.current_state === 'parts_lookup' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)' }}>
                    Calculate labor, parts total, and tax to prepare customer estimate.
                  </p>
                  <button type="button" onClick={triggerEstimateDraft} className="btn btn-secondary">
                    🤖 Draft WhatsApp Estimate Message
                  </button>
                </div>

                {estimateDraft && (
                  <AssistantAdvisoryCard title="Customer WhatsApp Estimate Draft" provenance={estimateDraft.provenance}>
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.825rem' }}>
                      {estimateDraft.message_text}
                    </pre>
                  </AssistantAdvisoryCard>
                )}

                <form onSubmit={submitEstimate}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Labor Charge (₹) *</label>
                      <input
                        type="number"
                        required
                        className="form-input"
                        value={estimateForm.labor_charge_inr}
                        onChange={(e) => setEstimateForm({ ...estimateForm, labor_charge_inr: Number(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Parts Total (₹) *</label>
                      <input
                        type="number"
                        required
                        className="form-input"
                        value={estimateForm.parts_total_inr}
                        onChange={(e) => setEstimateForm({ ...estimateForm, parts_total_inr: Number(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">GST Tax (18% ₹)</label>
                      <input
                        type="number"
                        className="form-input"
                        value={estimateForm.tax_inr}
                        onChange={(e) => setEstimateForm({ ...estimateForm, tax_inr: Number(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div style={{ padding: '0.75rem', backgroundColor: 'var(--slate-50)', borderRadius: '6px', marginBottom: '1rem', fontWeight: 600 }}>
                    Total Estimated Amount: ₹{(Number(estimateForm.labor_charge_inr) + Number(estimateForm.parts_total_inr) + Number(estimateForm.tax_inr)).toFixed(2)}
                  </div>

                  <div className="form-group">
                    <label className="form-label">Notes for Customer</label>
                    <input
                      type="text"
                      className="form-input"
                      value={estimateForm.notes}
                      onChange={(e) => setEstimateForm({ ...estimateForm, notes: e.target.value })}
                    />
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                    {isSubmitting ? 'Creating Estimate...' : 'Submit Estimate for Customer Approval'}
                  </button>
                </form>
              </div>
            )}

            {/* 4. ESTIMATE PENDING -> CUSTOMER APPROVAL (HUMAN GATE) */}
            {job.current_state === 'estimate_pending' && (
              <div>
                <div className="human-gate-banner">
                  <span>🔒</span>
                  <span>
                    <strong>Human Approval Gate:</strong> The assistant is strictly advisory and CANNOT authorize
                    repairs or spend money. An explicit customer confirmation must be recorded.
                  </span>
                </div>

                <form onSubmit={submitCustomerApproval}>
                  <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        checked={approvalForm.approved}
                        onChange={() => setApprovalForm({ ...approvalForm, approved: true })}
                      />
                      <span style={{ fontWeight: 600, color: 'var(--emerald-600)' }}>Customer Approved</span>
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        checked={!approvalForm.approved}
                        onChange={() => setApprovalForm({ ...approvalForm, approved: false })}
                      />
                      <span style={{ fontWeight: 600, color: 'var(--rose-600)' }}>Customer Declined (Reject)</span>
                    </label>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Approved By (Customer Name) *</label>
                      <input
                        type="text"
                        required
                        className="form-input"
                        value={approvalForm.approved_by}
                        onChange={(e) => setApprovalForm({ ...approvalForm, approved_by: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Approval Channel *</label>
                      <select
                        className="form-select"
                        value={approvalForm.channel}
                        onChange={(e) => setApprovalForm({ ...approvalForm, channel: e.target.value })}
                      >
                        <option value="phone">Phone Call</option>
                        <option value="whatsapp">WhatsApp Message</option>
                        <option value="in_person">In-Person at Counter</option>
                        <option value="sms">SMS</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Approval Notes / Verification</label>
                    <input
                      type="text"
                      className="form-input"
                      value={approvalForm.approval_notes}
                      onChange={(e) => setApprovalForm({ ...approvalForm, approval_notes: e.target.value })}
                      placeholder="e.g. Customer approved ₹914.50 over phone call at 11:30 AM"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className={`btn ${approvalForm.approved ? 'btn-success' : 'btn-danger'}`}
                  >
                    {isSubmitting
                      ? 'Recording...'
                      : approvalForm.approved
                      ? 'Record Customer Authorization'
                      : 'Record Customer Rejection'}
                  </button>
                </form>
              </div>
            )}

            {/* 5. CUSTOMER APPROVED -> SUPPLIER STATUS / QUEUE */}
            {job.current_state === 'customer_approved' && (
              <div>
                <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)', marginBottom: '1rem' }}>
                  Customer has approved the repair. Update supplier order status or proceed directly to repair queue if parts are in stock.
                </p>

                <form onSubmit={submitSupplierStatus} style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Option A: Update Supplier Parts Order</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Supplier Name *</label>
                      <input
                        type="text"
                        required
                        className="form-input"
                        value={supplierForm.supplier_name}
                        onChange={(e) => setSupplierForm({ ...supplierForm, supplier_name: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Parts Status *</label>
                      <select
                        className="form-select"
                        value={supplierForm.parts_status}
                        onChange={(e) => setSupplierForm({ ...supplierForm, parts_status: e.target.value })}
                      >
                        <option value="in_stock">In Stock / Sourced</option>
                        <option value="ordered">Ordered from Supplier</option>
                        <option value="in_transit">In Transit / Dispatched</option>
                        <option value="delivered">Delivered to Counter</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Expected Arrival Date</label>
                      <input
                        type="date"
                        className="form-input"
                        value={supplierForm.expected_arrival_date}
                        onChange={(e) => setSupplierForm({ ...supplierForm, expected_arrival_date: e.target.value })}
                      />
                    </div>
                  </div>
                  <button type="submit" disabled={isSubmitting} className="btn btn-secondary">
                    {isSubmitting ? 'Updating...' : 'Update Supplier Status'}
                  </button>
                </form>

                <div style={{ borderTop: '1px solid var(--slate-200)', paddingTop: '1rem' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Option B: Parts Already in Stock</h4>
                  <button
                    type="button"
                    onClick={() => handleTransitionQueue('repair_queue')}
                    disabled={isSubmitting}
                    className="btn btn-primary"
                  >
                    Move Straight to Repair Queue
                  </button>
                </div>
              </div>
            )}

            {/* 6. PARTS READY / SUPPLIER ORDERED -> QUEUE */}
            {(job.current_state === 'parts_ready' || job.current_state === 'supplier_ordered') && (
              <div>
                <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)', marginBottom: '1rem' }}>
                  Parts procurement tracked. Ready to place device into active repair queue.
                </p>
                <button
                  type="button"
                  onClick={() => handleTransitionQueue('repair_queue')}
                  disabled={isSubmitting}
                  className="btn btn-primary"
                >
                  Move to Repair Queue
                </button>
              </div>
            )}

            {/* 7. REPAIR QUEUE -> IN PROGRESS */}
            {job.current_state === 'repair_queue' && (
              <div>
                <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)', marginBottom: '1rem' }}>
                  Job is waiting in queue. Technician can pull device to active soldering / rework bench.
                </p>
                <button
                  type="button"
                  onClick={() => handleTransitionQueue('repair_in_progress')}
                  disabled={isSubmitting}
                  className="btn btn-primary"
                >
                  Start Bench Repair (In Progress)
                </button>
              </div>
            )}

            {/* 8. REPAIR IN PROGRESS -> COMPLETION (HUMAN GATE) */}
            {job.current_state === 'repair_in_progress' && (
              <div>
                <div className="human-gate-banner">
                  <span>🔒</span>
                  <span>
                    <strong>Human Technician Sign-Off Gate:</strong> The assistant CANNOT certify repairs or
                    quality tests. A human technician must pass quality control and sign off.
                  </span>
                </div>

                <form onSubmit={submitRepairCompletion}>
                  <div className="form-group">
                    <label className="form-label">Actions Taken by Technician *</label>
                    <textarea
                      required
                      rows={2}
                      className="form-textarea"
                      value={completionForm.actions_taken}
                      onChange={(e) => setCompletionForm({ ...completionForm, actions_taken: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Quality Control Tests Passed (comma separated) *</label>
                    <input
                      type="text"
                      required
                      className="form-input"
                      value={completionForm.qc_tests_passed}
                      onChange={(e) => setCompletionForm({ ...completionForm, qc_tests_passed: e.target.value })}
                      placeholder="e.g. 3-phase back-EMF balance, 2-hour thermal scan, speed test"
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Burn-in Duration (Minutes)</label>
                      <input
                        type="number"
                        className="form-input"
                        value={completionForm.burn_in_duration_minutes}
                        onChange={(e) => setCompletionForm({ ...completionForm, burn_in_duration_minutes: Number(e.target.value) })}
                      />
                    </div>
                    <div className="form-group" style={{ display: 'flex', alignItems: 'center', marginTop: '1.5rem' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={completionForm.technician_signature_confirmed}
                          onChange={(e) => setCompletionForm({ ...completionForm, technician_signature_confirmed: e.target.checked })}
                        />
                        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                          Technician Signature: I certify QC passed
                        </span>
                      </label>
                    </div>
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn btn-success">
                    {isSubmitting ? 'Recording Sign-off...' : 'Sign-off QC & Mark Repair Completed'}
                  </button>
                </form>
              </div>
            )}

            {/* 9. REPAIR COMPLETED -> PICKUP NOTIFICATION */}
            {job.current_state === 'repair_completed' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)' }}>
                    Repair complete! Notify customer via WhatsApp or SMS that device is ready for pickup.
                  </p>
                  <button type="button" onClick={triggerPickupDraft} className="btn btn-secondary">
                    🤖 Draft WhatsApp Pickup Notification
                  </button>
                </div>

                {pickupDraft && (
                  <AssistantAdvisoryCard title="Customer WhatsApp Pickup Draft" provenance={pickupDraft.provenance}>
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.825rem' }}>
                      {pickupDraft.message_text}
                    </pre>
                  </AssistantAdvisoryCard>
                )}

                <form onSubmit={submitPickupNotification}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Channel</label>
                      <select
                        className="form-select"
                        value={notificationForm.channel}
                        onChange={(e) => setNotificationForm({ ...notificationForm, channel: e.target.value })}
                      >
                        <option value="whatsapp">WhatsApp</option>
                        <option value="sms">SMS</option>
                        <option value="phone">Phone Call</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Recipient Phone</label>
                      <input
                        type="text"
                        className="form-input"
                        value={notificationForm.recipient_phone}
                        onChange={(e) => setNotificationForm({ ...notificationForm, recipient_phone: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Message Text</label>
                    <textarea
                      rows={3}
                      className="form-textarea"
                      value={notificationForm.message_text}
                      onChange={(e) => setNotificationForm({ ...notificationForm, message_text: e.target.value })}
                    />
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                    {isSubmitting ? 'Logging Notification...' : 'Send / Log Notification to Customer'}
                  </button>
                </form>
              </div>
            )}

            {/* 10. READY FOR PICKUP -> FOLLOW-UP / SETTLEMENT */}
            {job.current_state === 'ready_for_pickup' && (
              <div>
                <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)', marginBottom: '1rem' }}>
                  Customer has arrived at counter to collect device. Record payment settlement and activate warranty.
                </p>

                <form onSubmit={submitFollowup}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Amount Paid (₹) *</label>
                      <input
                        type="number"
                        required
                        className="form-input"
                        value={followupForm.amount_paid_inr}
                        onChange={(e) => setFollowupForm({ ...followupForm, amount_paid_inr: Number(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Payment Mode *</label>
                      <select
                        className="form-select"
                        value={followupForm.payment_method}
                        onChange={(e) => setFollowupForm({ ...followupForm, payment_method: e.target.value })}
                      >
                        <option value="upi">UPI (GPay / PhonePe / Paytm)</option>
                        <option value="cash">Cash Counter</option>
                        <option value="card">Credit / Debit Card</option>
                        <option value="neft">NEFT / NetBanking</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Warranty Days Included</label>
                      <input
                        type="number"
                        className="form-input"
                        value={followupForm.warranty_days}
                        onChange={(e) => setFollowupForm({ ...followupForm, warranty_days: Number(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Customer Feedback & Rating (1-5)</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <input
                        type="text"
                        className="form-input"
                        value={followupForm.customer_feedback}
                        onChange={(e) => setFollowupForm({ ...followupForm, customer_feedback: e.target.value })}
                        placeholder="Customer comment on collection..."
                      />
                      <select
                        className="form-select"
                        style={{ width: '120px' }}
                        value={followupForm.feedback_rating}
                        onChange={(e) => setFollowupForm({ ...followupForm, feedback_rating: Number(e.target.value) })}
                      >
                        <option value={5}>⭐⭐⭐⭐⭐ (5)</option>
                        <option value={4}>⭐⭐⭐⭐ (4)</option>
                        <option value={3}>⭐⭐⭐ (3)</option>
                        <option value={2}>⭐⭐ (2)</option>
                        <option value={1}>⭐ (1)</option>
                      </select>
                    </div>
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                    {isSubmitting ? 'Settling...' : 'Record Payment & Handover Device'}
                  </button>
                </form>
              </div>
            )}

            {/* 11. FOLLOW-UP -> CLOSED (HUMAN GATE) */}
            {job.current_state === 'follow_up' && (
              <div>
                <div className="human-gate-banner">
                  <span>🔒</span>
                  <span>
                    <strong>Human Close Gate:</strong> Final verification that device is collected, customer is satisfied,
                    and payment is cleared. Assistant cannot perform job closure.
                  </span>
                </div>

                <form onSubmit={submitCloseJob}>
                  <div className="form-group">
                    <label className="form-label">Resolution Summary *</label>
                    <textarea
                      required
                      rows={2}
                      className="form-textarea"
                      value={closeForm.resolution_summary}
                      onChange={(e) => setCloseForm({ ...closeForm, resolution_summary: e.target.value })}
                    />
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn btn-success">
                    {isSubmitting ? 'Closing Job...' : 'Confirm Job Closure'}
                  </button>
                </form>
              </div>
            )}

            {/* 12. CLOSED */}
            {job.current_state === 'closed' && (
              <div style={{ textAlign: 'center', padding: '1.5rem' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🎉</div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--emerald-600)', marginBottom: '0.5rem' }}>
                  Job Successfully Completed & Closed
                </h3>
                <p style={{ fontSize: '0.875rem', color: 'var(--slate-600)', maxWidth: '500px', margin: '0 auto' }}>
                  {details.job_close?.resolution_summary || 'Device repaired, tested, paid, and collected.'}
                </p>
                {details.follow_up && (
                  <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: 'var(--slate-500)' }}>
                    Warranty valid for {details.follow_up.warranty_days} days. Amount Paid: ₹{details.follow_up.amount_paid_inr} via {details.follow_up.payment_method.toUpperCase()}.
                  </div>
                )}
              </div>
            )}

            {/* ESTIMATE REJECTED */}
            {job.current_state === 'estimate_rejected' && (
              <div>
                <p style={{ fontSize: '0.875rem', color: 'var(--rose-600)', marginBottom: '1rem' }}>
                  Customer declined the estimate. Hand over device without repair and close job.
                </p>
                <button
                  type="button"
                  onClick={submitCloseJob}
                  disabled={isSubmitting}
                  className="btn btn-secondary"
                >
                  Close Un-repaired Job
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: ALL HISTORICAL RECORDS */}
      {activeTab === 'records' && (
        <div>
          {/* Notes */}
          <div className="card">
            <div className="card-header">
              <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Technician Diagnostic Notes</h4>
            </div>
            <div className="card-body">
              {details.technician_notes.length === 0 ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--slate-400)' }}>No diagnostic notes recorded yet.</p>
              ) : (
                details.technician_notes.map((n) => (
                  <div key={n.note_id} style={{ marginBottom: '0.75rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--slate-100)' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                      {n.technician_name} • <span style={{ color: 'var(--slate-500)', fontSize: '0.75rem' }}>{new Date(n.created_at).toLocaleString()}</span>
                    </div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--slate-700)', marginTop: '0.25rem' }}>
                      <strong>Findings:</strong> {n.diagnosis_findings}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--slate-700)' }}>
                      <strong>Root Cause:</strong> {n.root_cause}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Parts */}
          <div className="card">
            <div className="card-header">
              <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Required Spare Parts</h4>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              {details.parts.length === 0 ? (
                <p style={{ padding: '1rem', fontSize: '0.85rem', color: 'var(--slate-400)' }}>No parts listed.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Part Name</th>
                      <th>Part #</th>
                      <th>Supplier Source</th>
                      <th>Unit (₹)</th>
                      <th>Qty</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {details.parts.map((p) => (
                      <tr key={p.part_id}>
                        <td>{p.part_name}</td>
                        <td>{p.part_number || '-'}</td>
                        <td>{p.supplier_name || 'Local Market'}</td>
                        <td>₹{p.unit_cost_inr.toFixed(2)}</td>
                        <td>{p.quantity}</td>
                        <td><span className="badge badge-parts_ready">{p.availability_status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Estimate & Approval */}
          {details.estimate && (
            <div className="card">
              <div className="card-header">
                <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Cost Estimate & Approval</h4>
              </div>
              <div className="card-body">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>Labor Charge</span>
                    <div style={{ fontWeight: 700 }}>₹{details.estimate.labor_charge_inr.toFixed(2)}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>Parts Total</span>
                    <div style={{ fontWeight: 700 }}>₹{details.estimate.parts_total_inr.toFixed(2)}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>GST (18%)</span>
                    <div style={{ fontWeight: 700 }}>₹{details.estimate.tax_inr.toFixed(2)}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>Total Payable</span>
                    <div style={{ fontWeight: 800, color: 'var(--primary)', fontSize: '1.1rem' }}>
                      ₹{details.estimate.total_amount_inr.toFixed(2)}
                    </div>
                  </div>
                </div>

                {details.customer_approval && (
                  <div style={{ padding: '0.75rem', backgroundColor: '#f0fdf4', borderRadius: '6px', border: '1px solid #bbf7d0', fontSize: '0.85rem' }}>
                    <strong>Customer Approval:</strong> {details.customer_approval.approved ? 'APPROVED' : 'DECLINED'} by{' '}
                    <strong>{details.customer_approval.approved_by}</strong> via {details.customer_approval.channel.toUpperCase()} at{' '}
                    {new Date(details.customer_approval.approved_at).toLocaleString()}.
                    {details.customer_approval.approval_notes && <div><em>"{details.customer_approval.approval_notes}"</em></div>}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* QC Sign-off */}
          {details.repair_completion && (
            <div className="card">
              <div className="card-header">
                <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Quality Control & Bench Sign-off</h4>
              </div>
              <div className="card-body">
                <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                  <strong>Technician:</strong> {details.repair_completion.technician_name} (Signed off {new Date(details.repair_completion.completed_at).toLocaleString()})
                </div>
                <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                  <strong>Actions:</strong> {details.repair_completion.actions_taken}
                </div>
                <div style={{ fontSize: '0.85rem' }}>
                  <strong>QC Tests Passed:</strong>
                  <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                    {details.repair_completion.qc_tests_passed.map((test, idx) => (
                      <li key={idx}>{test}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: AUDIT STREAM */}
      {activeTab === 'audit' && (
        <div className="card">
          <div className="card-header">
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Immutable Audit Event Stream</h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--slate-500)' }}>
              Verified lifecycle events with monotonic version transitions
            </span>
          </div>
          <div className="card-body">
            <AuditEventStream events={details.audit_events} />
          </div>
        </div>
      )}
    </div>
  );
};
