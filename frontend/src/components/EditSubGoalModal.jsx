import React, { useState } from 'react';
import { X, CheckCircle2, Layers } from 'lucide-react';

export default function EditSubGoalModal({ isOpen, onClose, subGoal, onSave, existingIds = [] }) {
  if (!isOpen) return null;

  const isNew = !subGoal?.id;
  const [id, setId] = useState(subGoal?.id || `SG-${existingIds.length + 1}`);
  const [title, setTitle] = useState(subGoal?.title || '');
  const [description, setDescription] = useState(subGoal?.description || '');
  const [priority, setPriority] = useState(subGoal?.priority || 'high');
  const [assignedRole, setAssignedRole] = useState(subGoal?.assigned_agent_role || 'Execution Agent');
  const [dependenciesStr, setDependenciesStr] = useState((subGoal?.dependencies || []).join(', '));

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    const dependencies = dependenciesStr
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);

    onSave({
      id: id.trim() || `SG-${Date.now()}`,
      title: title.trim(),
      description: description.trim(),
      order: subGoal?.order || existingIds.length + 1,
      priority,
      assigned_agent_role: assignedRole.trim() || 'General Agent',
      dependencies,
      status: subGoal?.status || 'pending'
    });
    onClose();
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
      zIndex: 1100
    }}>
      <div className="card-panel" style={{
        width: '560px',
        maxWidth: '92vw',
        padding: '24px',
        backgroundColor: '#0D1526',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
        position: 'relative'
      }}>
        <button onClick={onClose} className="btn btn-ghost btn-sm" style={{ position: 'absolute', top: '16px', right: '16px', padding: '4px' }}>
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            background: 'rgba(99, 102, 241, 0.15)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Layers size={18} color="#818CF8" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#F1F5F9' }}>
              {isNew ? 'Add Hierarchical Sub-Goal' : `Edit Sub-Goal (${id})`}
            </h3>
            <p style={{ fontSize: '0.775rem', color: '#94A3B8' }}>
              Define explicit, verifiable sub-goal parameters and agent role allocation
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#94A3B8', fontWeight: 500, marginBottom: '4px' }}>Sub-Goal ID</label>
              <input 
                type="text" 
                value={id} 
                onChange={(e) => setId(e.target.value)}
                disabled={!isNew}
                className="font-mono"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: isNew ? '#070B16' : '#0A1020',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '6px',
                  color: '#F1F5F9',
                  fontSize: '0.825rem',
                  outline: 'none',
                  opacity: isNew ? 1 : 0.7
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#94A3B8', fontWeight: 500, marginBottom: '4px' }}>Priority Level</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#070B16',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '6px',
                  color: '#F1F5F9',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              >
                <option value="high">HIGH — Critical Path</option>
                <option value="medium">MEDIUM — Normal Priority</option>
                <option value="low">LOW — Non-blocking / Auxiliary</option>
              </select>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', color: '#94A3B8', fontWeight: 500, marginBottom: '4px' }}>Title</label>
            <input 
              type="text" 
              value={title} 
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Ingest and Classify Support Tickets"
              required
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#070B16',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '6px',
                color: '#F1F5F9',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', color: '#94A3B8', fontWeight: 500, marginBottom: '4px' }}>Description & Scope</label>
            <textarea 
              value={description} 
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Detailed description of what must be achieved in this sub-goal..."
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#070B16',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '6px',
                color: '#F1F5F9',
                fontSize: '0.85rem',
                outline: 'none',
                resize: 'vertical'
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#94A3B8', fontWeight: 500, marginBottom: '4px' }}>Target Agent Role</label>
              <input 
                type="text" 
                value={assignedRole} 
                onChange={(e) => setAssignedRole(e.target.value)}
                placeholder="e.g. Verification Agent"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#070B16',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '6px',
                  color: '#F1F5F9',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#94A3B8', fontWeight: 500, marginBottom: '4px' }}>Dependencies (comma separated IDs)</label>
              <input 
                type="text" 
                value={dependenciesStr} 
                onChange={(e) => setDependenciesStr(e.target.value)}
                placeholder="e.g. SG-1, SG-2"
                className="font-mono"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#070B16',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '6px',
                  color: '#F1F5F9',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              <CheckCircle2 size={14} />
              <span>{isNew ? 'Add Sub-Goal' : 'Save Changes'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
