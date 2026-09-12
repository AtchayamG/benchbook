import React, { useState } from 'react';
import { api } from '../api/client';
import type { Job } from '../types/benchbook';

interface JobIntakeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onJobCreated: (job: Job) => void;
}

const PRESETS = [
  {
    label: '⚡ Atomberg BLDC Fan',
    data: {
      customer_name: 'Senthil Nathan',
      customer_phone: '+91 98401 23456',
      customer_address: 'Gandhipuram, Coimbatore',
      device_kind: 'BLDC Ceiling Fan',
      brand_model: 'Atomberg Renesa 1200mm Smart',
      serial_number: 'ATMB-2024-88419',
      intake_symptoms: 'Motor humming loudly at speed 2, erratic speed transitions, LED blinks 3 times.',
      physical_condition: 'Blade bracket intact, canopy dust, remote included.',
      accessories_received: ['Remote Control', 'Shackle Kit'],
      promised_date: '2026-09-15',
      assigned_technician: 'Murugan R.',
    },
  },
  {
    label: '❄️ Voltas Inverter AC Board',
    data: {
      customer_name: 'Meenakshi Sundaram',
      customer_phone: '+91 94432 34567',
      customer_address: 'RS Puram, Coimbatore',
      device_kind: 'Split AC Inverter PCB',
      brand_model: 'Voltas 185V Vectra 1.5 Ton Inverter',
      serial_number: 'VLT-PCB-99210',
      intake_symptoms: 'Outdoor unit fan runs for 20 seconds, compressor does not start, display shows E6 error code.',
      physical_condition: 'PCB board removed by customer AC mechanic; heatsink paste dried.',
      accessories_received: ['Outdoor Main PCB', 'Temp Sensor Probe'],
      promised_date: '2026-09-14',
      assigned_technician: 'Palanisamy K.',
    },
  },
  {
    label: '🌀 Preethi Mixer Grinder',
    data: {
      customer_name: 'Anitha Selvaraj',
      customer_phone: '+91 97890 45678',
      customer_address: 'Peelamedu, Coimbatore',
      device_kind: 'Mixer Grinder',
      brand_model: 'Preethi Zodiac 750W',
      serial_number: 'PZ-750-44912',
      intake_symptoms: 'Strong burning smell from base, high sparking seen through bottom vents, overload reset popped.',
      physical_condition: 'Couplers normal, light stains on base body.',
      accessories_received: ['1.5L Master Chef Jar', 'Power Cord Base'],
      promised_date: '2026-09-13',
      assigned_technician: 'Murugan R.',
    },
  },
  {
    label: '💻 ThinkPad Laptop',
    data: {
      customer_name: 'Dr. R. Balaji',
      customer_phone: '+91 94860 67890',
      customer_address: 'Ramnagar, Coimbatore',
      device_kind: 'Laptop',
      brand_model: 'Lenovo ThinkPad E14 Gen 4 AMD',
      serial_number: 'PF-3X992A',
      intake_symptoms: 'USB-C charging port loose, battery not charging, right display hinge stiff and cracking palmrest.',
      physical_condition: 'Top cover minor scuffs, right corner bezel separated, charger adapter included.',
      accessories_received: ['65W USB-C Adapter', 'Laptop Sleeve'],
      promised_date: '2026-09-16',
      assigned_technician: 'Karthik Rajan',
    },
  },
];

export const JobIntakeModal: React.FC<JobIntakeModalProps> = ({ isOpen, onClose, onJobCreated }) => {
  const [formData, setFormData] = useState({
    customer_name: '',
    customer_phone: '',
    customer_address: '',
    device_kind: '',
    brand_model: '',
    serial_number: '',
    intake_symptoms: '',
    physical_condition: '',
    accessories_received: '',
    promised_date: '',
    assigned_technician: 'Murugan R.',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleApplyPreset = (presetData: typeof PRESETS[0]['data']) => {
    setFormData({
      ...presetData,
      accessories_received: presetData.accessories_received.join(', '),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const accessories = formData.accessories_received
        ? formData.accessories_received.split(',').map((s) => s.trim()).filter(Boolean)
        : [];

      const res = await api.createJob({
        ...formData,
        accessories_received: accessories,
      });
      onJobCreated(res.job);
      onClose();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to register job');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="card-header">
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600 }}>New Repair Job Intake</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--slate-500)' }}>
              Register incoming customer device at Kovai Tech Bench
            </p>
          </div>
          <button type="button" onClick={onClose} className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem' }}>
            ✕
          </button>
        </div>

        <div className="card-body">
          {/* Preset Buttons */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label className="form-label" style={{ marginBottom: '0.5rem' }}>
              Quick Fill Tamil Nadu Shop Presets:
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleApplyPreset(p.data)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.775rem', padding: '0.35rem 0.65rem' }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {errorMsg && (
            <div style={{ backgroundColor: '#ffe4e6', color: '#be123c', padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem', fontSize: '0.85rem' }}>
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Customer Full Name *</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={formData.customer_name}
                  onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                  placeholder="e.g. Senthil Nathan"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Phone Number *</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={formData.customer_phone}
                  onChange={(e) => setFormData({ ...formData, customer_phone: e.target.value })}
                  placeholder="e.g. +91 98401 23456"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Customer Address / Locality</label>
              <input
                type="text"
                className="form-input"
                value={formData.customer_address}
                onChange={(e) => setFormData({ ...formData, customer_address: e.target.value })}
                placeholder="e.g. Gandhipuram, Coimbatore"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Device Kind *</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={formData.device_kind}
                  onChange={(e) => setFormData({ ...formData, device_kind: e.target.value })}
                  placeholder="e.g. BLDC Ceiling Fan, Split AC PCB"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Brand & Model *</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={formData.brand_model}
                  onChange={(e) => setFormData({ ...formData, brand_model: e.target.value })}
                  placeholder="e.g. Atomberg Renesa 1200mm"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Intake Symptoms / Reported Fault *</label>
              <textarea
                required
                rows={2}
                className="form-textarea"
                value={formData.intake_symptoms}
                onChange={(e) => setFormData({ ...formData, intake_symptoms: e.target.value })}
                placeholder="Describe what customer noticed..."
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Promised Completion Date</label>
                <input
                  type="date"
                  className="form-input"
                  value={formData.promised_date}
                  onChange={(e) => setFormData({ ...formData, promised_date: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Assigned Bench Technician</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.assigned_technician}
                  onChange={(e) => setFormData({ ...formData, assigned_technician: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Accessories Received (comma separated)</label>
              <input
                type="text"
                className="form-input"
                value={formData.accessories_received}
                onChange={(e) => setFormData({ ...formData, accessories_received: e.target.value })}
                placeholder="e.g. Remote, Shackle Kit, Power Cord"
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                {isSubmitting ? 'Registering...' : 'Register Repair Job'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
