import React, { useState } from 'react';
import { 
  Target, 
  Layers, 
  CheckCircle2, 
  ShieldAlert, 
  FileCheck, 
  Edit3, 
  Plus, 
  Trash2, 
  ArrowUp, 
  ArrowDown, 
  Save, 
  Code, 
  HelpCircle,
  Sparkles,
  ChevronRight,
  Shield,
  FileCode,
  AlertTriangle
} from 'lucide-react';
import EditSubGoalModal from './EditSubGoalModal';
import { EditCriterionModal, EditConstraintModal } from './EditConstraintModal';

export default function GoalModelView({ 
  goalModel, 
  onSavePatch, 
  onNavigateToClarifications,
  onProceedToConfirmation,
  isSaving
}) {
  const [activeSubTab, setActiveSubTab] = useState('sub_goals'); // 'sub_goals' | 'criteria' | 'constraints' | 'output' | 'raw_json'
  
  // Local editable draft state
  const [mainGoal, setMainGoal] = useState(goalModel?.main_goal || '');
  const [summary, setSummary] = useState(goalModel?.summary || '');
  const [subGoals, setSubGoals] = useState(goalModel?.sub_goals || []);
  const [criteria, setCriteria] = useState(goalModel?.success_criteria || []);
  const [hardConstraints, setHardConstraints] = useState(goalModel?.hard_constraints || []);
  const [softConstraints, setSoftConstraints] = useState(goalModel?.soft_constraints || []);
  const [expectedOutput, setExpectedOutput] = useState(goalModel?.expected_output || { format: 'JSON', schema_summary: '', delivery_target: '' });
  
  const [changeNote, setChangeNote] = useState('');
  const [isEditingMainGoal, setIsEditingMainGoal] = useState(false);

  // Modals state
  const [editingSubGoal, setEditingSubGoal] = useState(null);
  const [isSubGoalModalOpen, setIsSubGoalModalOpen] = useState(false);

  const [editingCriterion, setEditingCriterion] = useState(null);
  const [isCriterionModalOpen, setIsCriterionModalOpen] = useState(false);

  const [editingConstraint, setEditingConstraint] = useState(null);
  const [isConstraintModalOpen, setIsConstraintModalOpen] = useState(false);
  const [defaultHardModal, setDefaultHardModal] = useState(true);

  // Sync state if incoming goalModel changes from outside
  React.useEffect(() => {
    if (goalModel) {
      setMainGoal(goalModel.main_goal || '');
      setSummary(goalModel.summary || '');
      setSubGoals(goalModel.sub_goals || []);
      setCriteria(goalModel.success_criteria || []);
      setHardConstraints(goalModel.hard_constraints || []);
      setSoftConstraints(goalModel.soft_constraints || []);
      setExpectedOutput(goalModel.expected_output || { format: 'JSON', schema_summary: '', delivery_target: '' });
    }
  }, [goalModel]);

  // Sub-goal handlers
  const handleSaveSubGoal = (sgData) => {
    const existingIdx = subGoals.findIndex((s) => s.id === sgData.id);
    if (existingIdx >= 0) {
      const updated = [...subGoals];
      updated[existingIdx] = sgData;
      setSubGoals(updated);
    } else {
      setSubGoals([...subGoals, sgData]);
    }
  };

  const handleDeleteSubGoal = (id) => {
    setSubGoals(subGoals.filter((s) => s.id !== id));
    setCriteria(criteria.filter((c) => c.sub_goal_id !== id));
  };

  const handleMoveSubGoal = (idx, direction) => {
    if ((direction === -1 && idx === 0) || (direction === 1 && idx === subGoals.length - 1)) return;
    const newIdx = idx + direction;
    const updated = [...subGoals];
    const temp = updated[idx];
    updated[idx] = updated[newIdx];
    updated[newIdx] = temp;
    updated.forEach((sg, i) => { sg.order = i + 1; });
    setSubGoals(updated);
  };

  // Criteria handlers
  const handleSaveCriterion = (critData) => {
    const existingIdx = criteria.findIndex((c) => c.id === critData.id);
    if (existingIdx >= 0) {
      const updated = [...criteria];
      updated[existingIdx] = critData;
      setCriteria(updated);
    } else {
      setCriteria([...criteria, critData]);
    }
  };

  const handleDeleteCriterion = (id) => {
    setCriteria(criteria.filter((c) => c.id !== id));
  };

  // Constraints handlers
  const handleSaveConstraint = (conData) => {
    if (conData.is_hard) {
      const existingIdx = hardConstraints.findIndex((c) => c.id === conData.id);
      if (existingIdx >= 0) {
        const updated = [...hardConstraints];
        updated[existingIdx] = conData;
        setHardConstraints(updated);
      } else {
        setHardConstraints([...hardConstraints, conData]);
      }
    } else {
      const existingIdx = softConstraints.findIndex((c) => c.id === conData.id);
      if (existingIdx >= 0) {
        const updated = [...softConstraints];
        updated[existingIdx] = conData;
        setSoftConstraints(updated);
      } else {
        setSoftConstraints([...softConstraints, conData]);
      }
    }
  };

  const handleDeleteConstraint = (id, isHard) => {
    if (isHard) {
      setHardConstraints(hardConstraints.filter((c) => c.id !== id));
    } else {
      setSoftConstraints(softConstraints.filter((c) => c.id !== id));
    }
  };

  // Trigger Save Patch to backend
  const handleTriggerSavePatch = () => {
    const payload = {
      run_id: goalModel.run_id,
      main_goal: mainGoal,
      summary: summary,
      sub_goals: subGoals,
      success_criteria: criteria,
      hard_constraints: hardConstraints,
      soft_constraints: softConstraints,
      expected_output: expectedOutput,
      change_summary: changeNote.trim() || 'Manual revision of goal model'
    };
    onSavePatch(payload);
    setChangeNote('');
  };

  const unresolvedBlockingCount = (goalModel?.ambiguities || []).filter(
    (a) => a.severity === 'blocking' && !a.resolved
  ).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner & Primary Navigation */}
      <section className="card-panel" style={{ padding: '20px 24px', backgroundColor: '#FFFFFF' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '16px'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="badge badge-purple">Stage 2: Requirements Analysis</span>
              <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
                v{goalModel?.version || '1.0'}
              </span>
              <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)' }}>
                {goalModel?.is_confirmed ? '✓ Confirmed by Engineer' : 'Pending Formal Confirmation'}
              </span>
            </div>
            <h2 style={{ 
              fontSize: '1.35rem', 
              fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
              fontWeight: 700, 
              color: 'var(--text-primary, #172033)' 
            }}>
              Interpreted Requirements & Goal Model
            </h2>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            {onProceedToConfirmation && (
              <button 
                type="button"
                className="btn btn-primary" 
                disabled={isSaving}
                onClick={unresolvedBlockingCount > 0 ? onNavigateToClarifications : onProceedToConfirmation}
                style={{ fontWeight: 600 }}
              >
                <span>{unresolvedBlockingCount > 0 ? 'Resolve questions to continue' : 'Review and confirm requirements'}</span>
                <ChevronRight size={14} />
              </button>
            )}

            {goalModel?.ambiguities && goalModel.ambiguities.length > 0 && (
              <button 
                type="button"
                onClick={onNavigateToClarifications}
                className={`btn btn-sm ${unresolvedBlockingCount > 0 ? 'btn-danger' : 'btn-secondary'}`}
              >
                <HelpCircle size={14} />
                <span>
                  {unresolvedBlockingCount > 0 
                    ? `${unresolvedBlockingCount} Blocking Clarifications Required` 
                    : `${goalModel.ambiguities.length} Clarifications Answered`}
                </span>
                <ChevronRight size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Section A: Task Understanding (Main Objective) */}
        <div style={{
          backgroundColor: 'var(--bg-page, #F6F7FB)',
          border: '1px solid var(--border-subtle, #E5E7EF)',
          borderRadius: '8px',
          padding: '16px',
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.725rem', fontWeight: 700, color: 'var(--accent-primary, #6257D9)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Task Understanding & Executive Summary
            </span>
            <button 
              type="button"
              onClick={() => setIsEditingMainGoal(!isEditingMainGoal)}
              className="btn btn-ghost btn-sm"
              style={{ fontSize: '0.725rem', padding: '2px 6px' }}
            >
              <Edit3 size={12} />
              <span>{isEditingMainGoal ? 'Close Edit' : 'Edit Objective'}</span>
            </button>
          </div>

          {isEditingMainGoal ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
              <input 
                type="text"
                value={mainGoal}
                onChange={(e) => setMainGoal(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--accent-primary, #6257D9)',
                  borderRadius: '6px',
                  color: 'var(--text-primary, #172033)',
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  outline: 'none'
                }}
              />
              <textarea 
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={2}
                placeholder="Executive summary..."
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--border-subtle, #E5E7EF)',
                  borderRadius: '6px',
                  color: 'var(--text-primary, #172033)',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              />
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #172033)', marginBottom: '4px' }}>
                {mainGoal}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5' }}>
                {summary}
              </div>
            </div>
          )}
        </div>

        {/* Quick Metrics Count Bar */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
            <Layers size={14} color="var(--accent-primary, #6257D9)" />
            <span style={{ color: 'var(--text-secondary, #667085)' }}>Sub-Goals:</span>
            <span style={{ fontWeight: 700, color: 'var(--text-primary, #172033)' }}>{subGoals.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
            <CheckCircle2 size={14} color="var(--success-color, #16845B)" />
            <span style={{ color: 'var(--text-secondary, #667085)' }}>Acceptance Criteria:</span>
            <span style={{ fontWeight: 700, color: 'var(--success-color, #16845B)' }}>{criteria.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
            <ShieldAlert size={14} color="var(--danger-color, #D14343)" />
            <span style={{ color: 'var(--text-secondary, #667085)' }}>Hard Constraints:</span>
            <span style={{ fontWeight: 700, color: 'var(--danger-color, #D14343)' }}>{hardConstraints.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
            <Shield size={14} color="var(--warning-color, #B7791F)" />
            <span style={{ color: 'var(--text-secondary, #667085)' }}>Soft Constraints:</span>
            <span style={{ fontWeight: 700, color: 'var(--warning-color, #B7791F)' }}>{softConstraints.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
            <FileCheck size={14} color="var(--accent-primary, #6257D9)" />
            <span style={{ color: 'var(--text-secondary, #667085)' }}>Output Format:</span>
            <span style={{ fontWeight: 600, color: 'var(--accent-primary, #6257D9)' }}>{expectedOutput.format}</span>
          </div>
        </div>
      </section>

      {/* Navigation Sub-Tabs */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        borderBottom: '1px solid var(--border-subtle, #E5E7EF)', 
        paddingBottom: '2px',
        overflowX: 'auto'
      }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button 
            type="button"
            onClick={() => setActiveSubTab('sub_goals')}
            className={`btn btn-sm ${activeSubTab === 'sub_goals' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: '6px 6px 0 0' }}
          >
            <Layers size={13} />
            <span>1. Functional Requirements ({subGoals.length})</span>
          </button>
          <button 
            type="button"
            onClick={() => setActiveSubTab('criteria')}
            className={`btn btn-sm ${activeSubTab === 'criteria' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: '6px 6px 0 0' }}
          >
            <CheckCircle2 size={13} />
            <span>2. Acceptance Criteria ({criteria.length})</span>
          </button>
          <button 
            type="button"
            onClick={() => setActiveSubTab('constraints')}
            className={`btn btn-sm ${activeSubTab === 'constraints' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: '6px 6px 0 0' }}
          >
            <ShieldAlert size={13} />
            <span>3. Constraints & Guardrails ({hardConstraints.length + softConstraints.length})</span>
          </button>
          <button 
            type="button"
            onClick={() => setActiveSubTab('output')}
            className={`btn btn-sm ${activeSubTab === 'output' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: '6px 6px 0 0' }}
          >
            <FileCheck size={13} />
            <span>4. Expected Output</span>
          </button>
          <button 
            type="button"
            onClick={() => setActiveSubTab('raw_json')}
            className={`btn btn-sm ${activeSubTab === 'raw_json' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: '6px 6px 0 0' }}
          >
            <Code size={13} />
            <span>5. Technical Specification</span>
          </button>
        </div>
      </div>

      {/* Tab 1: Functional Requirements (Sub-Goals) */}
      {activeSubTab === 'sub_goals' && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
              Hierarchical operational decomposition and assigned agent capabilities:
            </p>
            <button 
              type="button"
              onClick={() => {
                setEditingSubGoal(null);
                setIsSubGoalModalOpen(true);
              }}
              className="btn btn-sm btn-primary"
            >
              <Plus size={14} /> Add Sub-Goal
            </button>
          </div>

          {subGoals.map((sg, idx) => (
            <div 
              key={sg.id}
              className="card-panel"
              style={{
                padding: '16px',
                backgroundColor: '#FFFFFF',
                display: 'flex',
                gap: '16px',
                alignItems: 'flex-start'
              }}
            >
              {/* Order & Reorder Controls */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', minWidth: '32px' }}>
                <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-primary, #6257D9)' }}>
                  #{idx + 1}
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <button 
                    type="button"
                    onClick={() => handleMoveSubGoal(idx, -1)} 
                    disabled={idx === 0}
                    className="btn btn-ghost btn-sm" 
                    style={{ padding: '2px', opacity: idx === 0 ? 0.2 : 1 }}
                    title="Move up"
                  >
                    <ArrowUp size={12} />
                  </button>
                  <button 
                    type="button"
                    onClick={() => handleMoveSubGoal(idx, 1)} 
                    disabled={idx === subGoals.length - 1}
                    className="btn btn-ghost btn-sm" 
                    style={{ padding: '2px', opacity: idx === subGoals.length - 1 ? 0.2 : 1 }}
                    title="Move down"
                  >
                    <ArrowDown size={12} />
                  </button>
                </div>
              </div>

              {/* Sub-Goal Body */}
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                  <span className="font-mono" style={{ fontSize: '0.725rem', color: '#172033', backgroundColor: '#F1F4F9', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                    {sg.id}
                  </span>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary, #172033)', margin: 0 }}>
                    {sg.title}
                  </h4>
                  <span className={`badge ${sg.priority === 'high' ? 'badge-rose' : (sg.priority === 'medium' ? 'badge-amber' : 'badge-slate')}`}>
                    {sg.priority}
                  </span>
                  <span className="badge badge-purple" style={{ textTransform: 'none' }}>
                    Role: {sg.assigned_agent_role}
                  </span>
                </div>
                <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5', marginBottom: '8px' }}>
                  {sg.description}
                </p>

                {sg.dependencies && sg.dependencies.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #667085)' }}>Depends on:</span>
                    {sg.dependencies.map((dep) => (
                      <span key={dep} className="font-mono" style={{ fontSize: '0.675rem', backgroundColor: '#F1F4F9', color: 'var(--accent-primary, #6257D9)', padding: '1px 6px', borderRadius: '3px' }}>
                        {dep}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '4px' }}>
                <button 
                  type="button"
                  onClick={() => {
                    setEditingSubGoal(sg);
                    setIsSubGoalModalOpen(true);
                  }}
                  className="btn btn-ghost btn-sm"
                  title="Edit Sub-Goal"
                >
                  <Edit3 size={14} />
                </button>
                <button 
                  type="button"
                  onClick={() => handleDeleteSubGoal(sg.id)}
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'var(--danger-color, #D14343)' }}
                  title="Delete Sub-Goal"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Tab 2: Acceptance Criteria Matrix */}
      {activeSubTab === 'criteria' && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
              Objective verification criteria evaluated independently at completion:
            </p>
            <button 
              type="button"
              onClick={() => {
                setEditingCriterion(null);
                setIsCriterionModalOpen(true);
              }}
              className="btn btn-sm btn-primary"
            >
              <Plus size={14} /> Add Criterion
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px' }}>
            {criteria.map((sc) => (
              <div 
                key={sc.id}
                className="card-panel"
                style={{
                  padding: '16px',
                  backgroundColor: '#FFFFFF',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '10px'
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-primary, #6257D9)', fontWeight: 700 }}>
                        {sc.id}
                      </span>
                      {sc.sub_goal_id && (
                        <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
                          Sub-Goal: {sc.sub_goal_id}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button 
                        type="button"
                        onClick={() => {
                          setEditingCriterion(sc);
                          setIsCriterionModalOpen(true);
                        }}
                        className="btn btn-ghost btn-sm" 
                        style={{ padding: '2px 4px' }}
                        title="Edit Criterion"
                      >
                        <Edit3 size={13} />
                      </button>
                      <button 
                        type="button"
                        onClick={() => handleDeleteCriterion(sc.id)}
                        className="btn btn-ghost btn-sm" 
                        style={{ padding: '2px 4px', color: 'var(--danger-color, #D14343)' }}
                        title="Delete Criterion"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  <p style={{ fontSize: '0.85rem', color: 'var(--text-primary, #172033)', fontWeight: 500, marginBottom: '8px' }}>
                    {sc.description}
                  </p>

                  <div style={{
                    backgroundColor: 'var(--bg-page, #F6F7FB)',
                    border: '1px solid var(--border-subtle, #E5E7EF)',
                    borderRadius: '6px',
                    padding: '8px 10px',
                    marginBottom: '8px'
                  }}>
                    <div style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', marginBottom: '2px' }}>
                      Verification Metric
                    </div>
                    <div className="font-mono" style={{ fontSize: '0.775rem', color: 'var(--text-primary, #172033)' }}>
                      {sc.metric}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.725rem', borderTop: '1px solid var(--border-subtle, #E5E7EF)', paddingTop: '8px' }}>
                  <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>
                    {sc.verification_method}
                  </span>
                  <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
                    Status: {goalModel?.is_confirmed ? 'Confirmed' : 'Pending'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Tab 3: Constraints Guardrails */}
      {activeSubTab === 'constraints' && (
        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Hard Constraints Column */}
          <div className="card-panel" style={{ padding: '18px', backgroundColor: '#FFFFFF', border: '1px solid #FECACA' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldAlert size={18} color="var(--danger-color, #D14343)" />
                <div>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--danger-color, #D14343)', margin: 0 }}>
                    Hard Constraints ({hardConstraints.length})
                  </h4>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #667085)' }}>Strict invariant guardrails — Non-negotiable</span>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => {
                  setEditingConstraint(null);
                  setDefaultHardModal(true);
                  setIsConstraintModalOpen(true);
                }}
                className="btn btn-sm btn-danger"
              >
                <Plus size={13} /> Add Hard
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {hardConstraints.map((hc) => (
                <div 
                  key={hc.id}
                  style={{
                    backgroundColor: '#FEF2F2',
                    border: '1px solid #FECACA',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <span className="font-mono" style={{ fontSize: '0.7rem', color: '#D14343', fontWeight: 700 }}>{hc.id}</span>
                      <span className="badge badge-rose" style={{ fontSize: '0.6rem' }}>{hc.category}</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: '#172033', lineHeight: '1.4', margin: 0 }}>
                      {hc.text}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '2px', marginLeft: '8px' }}>
                    <button 
                      type="button"
                      onClick={() => {
                        setEditingConstraint(hc);
                        setDefaultHardModal(true);
                        setIsConstraintModalOpen(true);
                      }}
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '2px' }}
                    >
                      <Edit3 size={12} />
                    </button>
                    <button 
                      type="button"
                      onClick={() => handleDeleteConstraint(hc.id, true)}
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '2px', color: '#D14343' }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Soft Constraints Column */}
          <div className="card-panel" style={{ padding: '18px', backgroundColor: '#FFFFFF', border: '1px solid #FDE68A' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield size={18} color="var(--warning-color, #B7791F)" />
                <div>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--warning-color, #B7791F)', margin: 0 }}>
                    Soft Constraints ({softConstraints.length})
                  </h4>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #667085)' }}>Operational preferences & architectural guidelines</span>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => {
                  setEditingConstraint(null);
                  setDefaultHardModal(false);
                  setIsConstraintModalOpen(true);
                }}
                className="btn btn-sm btn-secondary"
              >
                <Plus size={13} /> Add Soft
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {softConstraints.map((sc) => (
                <div 
                  key={sc.id}
                  style={{
                    backgroundColor: '#FFFBEB',
                    border: '1px solid #FDE68A',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <span className="font-mono" style={{ fontSize: '0.7rem', color: '#B7791F', fontWeight: 700 }}>{sc.id}</span>
                      <span className="badge badge-amber" style={{ fontSize: '0.6rem' }}>{sc.category}</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: '#172033', lineHeight: '1.4', margin: 0 }}>
                      {sc.text}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '2px', marginLeft: '8px' }}>
                    <button 
                      type="button"
                      onClick={() => {
                        setEditingConstraint(sc);
                        setDefaultHardModal(false);
                        setIsConstraintModalOpen(true);
                      }}
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '2px' }}
                    >
                      <Edit3 size={12} />
                    </button>
                    <button 
                      type="button"
                      onClick={() => handleDeleteConstraint(sc.id, false)}
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '2px', color: '#D14343' }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Tab 4: Expected Output */}
      {activeSubTab === 'output' && (
        <section className="card-panel expected-output-panel">
          <div className="expected-output-header">
            <div className="expected-output-heading">
              <span className="expected-output-heading-icon"><FileCheck size={16} /></span>
              <div>
                <h3>Expected Delivery Format &amp; Target</h3>
                <p>What HorizonLab will produce and where it will be delivered.</p>
              </div>
            </div>
            <span className="expected-output-badge">DELIVERY CONTRACT</span>
          </div>
          <div className="expected-output-flow">
            <article className="expected-output-card expected-output-format">
              <span className="expected-output-card-icon"><FileCode size={18} /></span>
              <div className="expected-output-card-content">
                <span className="expected-output-label">Output format</span>
                <strong>{expectedOutput.format || 'Application Files'}</strong>
                <span className="expected-output-hint">The deliverable structure</span>
              </div>
            </article>
            <div className="expected-output-connector" aria-hidden="true">
              <span />
              <ChevronRight size={16} />
              <span />
            </div>
            <article className="expected-output-card expected-output-target">
              <span className="expected-output-card-icon"><Target size={18} /></span>
              <div className="expected-output-card-content">
                <span className="expected-output-label">Delivery target</span>
                <strong>{expectedOutput.delivery_target || 'Workspace Filesystem'}</strong>
                <span className="expected-output-hint">Where the result will land</span>
              </div>
            </article>
          </div>
        </section>
      )}

      {/* Tab 5: Technical Details (Raw JSON) */}
      {activeSubTab === 'raw_json' && (
        <section className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)' }}>
              Canonical JSON Manifest (Task ID: {goalModel?.task_id})
            </span>
            <button 
              type="button"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(goalModel, null, 2))}
              className="btn btn-secondary btn-sm"
            >
              Copy JSON
            </button>
          </div>
          <pre style={{
            fontSize: '0.775rem',
            color: '#172033',
            backgroundColor: 'var(--bg-page, #F6F7FB)',
            padding: '16px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle, #E5E7EF)',
            overflowX: 'auto',
            maxHeight: '420px'
          }}>
            {JSON.stringify(goalModel, null, 2)}
          </pre>
        </section>
      )}

      {/* Persistent Save Patch Bar */}
      <div style={{
        position: 'sticky',
        bottom: '44px',
        backgroundColor: '#FFFFFF',
        border: '1px solid var(--border-subtle, #E5E7EF)',
        borderRadius: '10px',
        padding: '12px 20px',
        boxShadow: 'var(--shadow-md)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 35
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, marginRight: '16px' }}>
          <span style={{ fontSize: '0.775rem', fontWeight: 600, color: 'var(--text-secondary, #667085)', whiteSpace: 'nowrap' }}>
            Revision Note:
          </span>
          <input 
            type="text"
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            placeholder="e.g. Added constraint for password hashing salt rounds (optional)"
            style={{
              flex: 1,
              padding: '6px 12px',
              backgroundColor: 'var(--bg-page, #F6F7FB)',
              border: '1px solid var(--border-subtle, #E5E7EF)',
              borderRadius: '6px',
              color: 'var(--text-primary, #172033)',
              fontSize: '0.8rem',
              outline: 'none'
            }}
          />
        </div>

        <button 
          type="button"
          onClick={handleTriggerSavePatch}
          disabled={isSaving}
          className="btn btn-primary btn-sm"
          style={{ padding: '8px 16px', fontWeight: 600 }}
        >
          <Save size={14} />
          <span>{isSaving ? 'Saving Changes...' : 'Save & Bump Version'}</span>
        </button>
      </div>

      {/* Modals */}
      <EditSubGoalModal 
        isOpen={isSubGoalModalOpen}
        onClose={() => setIsSubGoalModalOpen(false)}
        subGoal={editingSubGoal}
        onSave={handleSaveSubGoal}
        existingIds={subGoals.map((s) => s.id)}
      />

      <EditCriterionModal 
        isOpen={isCriterionModalOpen}
        onClose={() => setIsCriterionModalOpen(false)}
        criterion={editingCriterion}
        subGoals={subGoals}
        onSave={handleSaveCriterion}
        existingIds={criteria.map((c) => c.id)}
      />

      <EditConstraintModal 
        isOpen={isConstraintModalOpen}
        onClose={() => setIsConstraintModalOpen(false)}
        constraint={editingConstraint}
        isHardDefault={defaultHardModal}
        onSave={handleSaveConstraint}
        existingIds={[...hardConstraints, ...softConstraints].map((c) => c.id)}
      />
    </div>
  );
}
