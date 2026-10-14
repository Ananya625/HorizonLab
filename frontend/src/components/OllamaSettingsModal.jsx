import React, { useState } from 'react';
import { X, RefreshCw, CheckCircle2, AlertTriangle, Server, Sliders } from 'lucide-react';
import { configureOllama } from '../services/api';

export default function OllamaSettingsModal({ isOpen, onClose, currentStatus, onStatusUpdated, temperature, setTemperature }) {
  const [host, setHost] = useState(currentStatus?.host || 'http://127.0.0.1:11434');
  // Status arrives after mount; use its selection until the user edits this form.
  const [modelOverride, setSelectedModel] = useState(null);
  const selectedModel = modelOverride || currentStatus?.current_model || 'qwen3:1.7b';
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  if (!isOpen) return null;

  const handleTestAndSave = async () => {
    setTesting(true);
    setFeedback(null);
    try {
      const res = await configureOllama({ host, default_model: selectedModel });
      onStatusUpdated(res.status);
      setFeedback({
        type: res.status.connected ? 'success' : 'warning',
        message: res.status.connected 
          ? `Successfully connected! Latency: ${res.status.latency_ms}ms (${res.status.models.length} models detected)`
          : `Failed to connect: ${res.status.message}`
      });
    } catch (err) {
      setFeedback({
        type: 'error',
        message: `Connection error: ${err.message}`
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(16, 24, 40, 0.45)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div className="card-panel" style={{
        width: '520px',
        maxWidth: '92vw',
        padding: '24px',
        backgroundColor: '#FFFFFF',
        border: '1px solid var(--border-subtle, #E5E7EF)',
        boxShadow: '0 20px 48px rgba(16, 24, 40, 0.16)',
        position: 'relative'
      }}>
        {/* Close Button */}
        <button 
          type="button"
          onClick={onClose}
          className="btn btn-ghost btn-sm"
          style={{ position: 'absolute', top: '16px', right: '16px', padding: '4px' }}
          title="Close settings"
        >
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '18px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'var(--accent-primary-subtle, #F0EEFF)',
            border: '1px solid var(--accent-primary-border, #D8D2FB)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Server size={18} color="var(--accent-primary, #6257D9)" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary, #172033)', margin: 0 }}>
              Ollama LLM Engine Settings
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
              Configure local inference endpoint and parameters
            </p>
          </div>
        </div>

        {/* Host URL input */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #172033)', marginBottom: '6px' }}>
            Ollama Host Endpoint
          </label>
          <input 
            type="text" 
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="http://127.0.0.1:11434"
            className="font-mono"
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#FFFFFF',
              border: '1px solid var(--border-subtle, #E5E7EF)',
              borderRadius: '6px',
              color: 'var(--text-primary, #172033)',
              fontSize: '0.85rem',
              outline: 'none'
            }}
          />
        </div>

        {/* Model Selection */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #172033)', marginBottom: '6px' }}>
            Active Extraction Model
          </label>
          <select 
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#FFFFFF',
              border: '1px solid var(--border-subtle, #E5E7EF)',
              borderRadius: '6px',
              color: 'var(--text-primary, #172033)',
              fontSize: '0.85rem',
              outline: 'none'
            }}
          >
            {currentStatus?.models && currentStatus.models.length > 0 ? (
              currentStatus.models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))
            ) : (
              <option value={selectedModel}>{selectedModel} (installation not confirmed)</option>
            )}
          </select>
        </div>

        {/* Temperature Slider */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sliders size={14} color="var(--text-secondary, #667085)" /> Inference Temperature
            </label>
            <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--accent-primary, #6257D9)', fontWeight: 700 }}>
              {temperature}
            </span>
          </div>
          <input 
            type="range" 
            min="0.0" 
            max="1.0" 
            step="0.05"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent-primary, #6257D9)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-secondary, #667085)', marginTop: '2px' }}>
            <span>0.0 (Deterministic)</span>
            <span>0.2 (Recommended)</span>
            <span>1.0 (Creative)</span>
          </div>
        </div>

        {/* Feedback message */}
        {feedback && (
          <div style={{
            padding: '10px 14px',
            borderRadius: '6px',
            marginBottom: '18px',
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: feedback.type === 'success' ? 'var(--success-subtle, #ECFDF5)' : 'var(--danger-subtle, #FEF2F2)',
            border: `1px solid ${feedback.type === 'success' ? 'var(--success-border, #A7F3D0)' : 'var(--danger-border, #FECACA)'}`,
            color: feedback.type === 'success' ? 'var(--success-color, #16845B)' : 'var(--danger-color, #D14343)'
          }}>
            {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" onClick={onClose} className="btn btn-secondary">
            Cancel
          </button>
          <button 
            type="button"
            onClick={handleTestAndSave} 
            disabled={testing}
            className="btn btn-primary"
          >
            {testing ? <RefreshCw size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
            <span>{testing ? 'Testing Connection...' : 'Save & Test Connection'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
