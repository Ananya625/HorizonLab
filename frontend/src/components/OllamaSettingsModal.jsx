import React, { useState } from 'react';
import { X, RefreshCw, CheckCircle2, AlertTriangle, Server, Cpu, Sliders } from 'lucide-react';
import { configureOllama, fetchOllamaStatus } from '../services/api';

export default function OllamaSettingsModal({ isOpen, onClose, currentStatus, onStatusUpdated, temperature, setTemperature }) {
  const [host, setHost] = useState(currentStatus?.host || 'http://127.0.0.1:11434');
  const [selectedModel, setSelectedModel] = useState(currentStatus?.current_model || 'qwen2.5-coder:7b');
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  if (!isOpen) return null;

  const handleTestAndSave = async () => {
    setTesting(true);
    setFeedback(null);
    try {
      const res = await configureOllama(host, selectedModel);
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
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div className="card-panel" style={{
        width: '520px',
        maxWidth: '92vw',
        padding: '24px',
        backgroundColor: '#111827',
        border: '1px solid #1f293d',
        boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
        position: 'relative'
      }}>
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="btn btn-ghost btn-sm"
          style={{ position: 'absolute', top: '16px', right: '16px', padding: '4px' }}
        >
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Server size={18} color="#38bdf8" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>Ollama LLM Engine Settings</h3>
            <p style={{ fontSize: '0.775rem', color: '#94a3b8' }}>Configure local inference endpoint and parameters for requirement extraction</p>
          </div>
        </div>

        {/* Host URL input */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#cbd5e1', marginBottom: '6px' }}>
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
              backgroundColor: '#0c121d',
              border: '1px solid #24344d',
              borderRadius: '6px',
              color: '#f8fafc',
              fontSize: '0.85rem',
              outline: 'none'
            }}
          />
        </div>

        {/* Model Selection */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#cbd5e1', marginBottom: '6px' }}>
            Active Extraction Model
          </label>
          <select 
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#0c121d',
              border: '1px solid #24344d',
              borderRadius: '6px',
              color: '#f8fafc',
              fontSize: '0.85rem',
              outline: 'none'
            }}
          >
            {currentStatus?.models && currentStatus.models.length > 0 ? (
              currentStatus.models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))
            ) : (
              <option value="qwen2.5-coder:7b">qwen2.5-coder:7b (Default)</option>
            )}
          </select>
        </div>

        {/* Temperature Slider */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 500, color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sliders size={14} color="#94a3b8" /> Inference Temperature
            </label>
            <span className="font-mono" style={{ fontSize: '0.8rem', color: '#38bdf8' }}>{temperature}</span>
          </div>
          <input 
            type="range" 
            min="0.0" 
            max="1.0" 
            step="0.05"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#0284c7' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>
            <span>0.0 (Deterministic / Strict)</span>
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
            backgroundColor: feedback.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
            border: `1px solid ${feedback.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            color: feedback.type === 'success' ? '#34d399' : '#fb7185'
          }}>
            {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button onClick={onClose} className="btn btn-secondary">
            Cancel
          </button>
          <button 
            onClick={handleTestAndSave} 
            disabled={testing}
            className="btn btn-primary"
          >
            {testing ? <RefreshCw size={14} className="live-pulse" /> : <CheckCircle2 size={14} />}
            <span>{testing ? 'Testing Connection...' : 'Save & Test Connection'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
