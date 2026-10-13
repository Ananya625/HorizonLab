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
  Eye, 
  HelpCircle,
  Clock,
  Sparkles,
  ChevronRight,
  Shield,
  Zap,
  Info
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
    // Also remove orphaned criteria
    setCriteria(criteria.filter((c) => c.sub_goal_id !== id));
  };

  const handleMoveSubGoal = (idx, direction) => {
    if ((direction === -1 && idx === 0) || (direction === 1 && idx === subGoals.length - 1)) return;
    const newIdx = idx + direction;
    const updated = [...subGoals];
    const temp = updated[idx];
    updated[idx] = updated[newIdx];
    updated[newIdx] = temp;
    // Reassign order
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

  // Save patch to backend
  const handleTriggerSavePatch = () => {
    onSavePatch({
      run_id: goalModel.run_id,
      main_goal: mainGoal,
      summary: summary,
      sub_goals: subGoals,
      success_criteria: criteria,
      hard_constraints: hardConstraints,
      soft_constraints: softConstraints,
      expected_output: expectedOutput,
      change_summary: changeNote.trim() || `User updated Goal Model elements`
    });
    setChangeNote('');
  };

  const unresolvedBlockingCount = (goalModel?.ambiguities || []).filter(a => a.severity === 'blocking' && !a.resolved).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Telemetry & Main Goal Card */}
      <div className="card-panel" style={{ padding: '24px', position: 'relative' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Target size={20} color="#38bdf8" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-cyan">State 2: Goal Model</span>
                <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{goalModel?.task_id}</span>
                <span className="badge badge-purple">Version {goalModel?.goal_model_version}</span>
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
                Governed Goal Specification
              </h2>
            </div>
          </div>

          {onProceedToConfirmation && (
            <button className="btn btn-primary" disabled={isSaving}
              onClick={unresolvedBlockingCount > 0 ? onNavigateToClarifications : onProceedToConfirmation}>
              {unresolvedBlockingCount > 0 ? 'Resolve questions to continue' : 'Review and confirm requirements'}
              <ChevronRight size={14} />
            </button>
          )}
          {/* Ambiguity Alert button */}
          {goalModel?.ambiguities && goalModel.ambiguities.length > 0 && (
            <button 
              onClick={onNavigateToClarifications}
              className={`btn btn-sm ${unresolvedBlockingCount > 0 ? 'btn-danger' : 'btn-secondary'}`}
              style={{ padding: '6px 12px' }}
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

        {/* Main Goal editable row */}
        <div style={{
          backgroundColor: '#0c121d',
          border: '1px solid #1f2a3e',
          borderRadius: '8px',
          padding: '16px',
          marginBottom: '14px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.725rem', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Main Objective (Goal Model Root)
            </span>
            <button 
              onClick={() => setIsEditingMainGoal(!isEditingMainGoal)}
              className="btn btn-ghost btn-sm"
              style={{ fontSize: '0.725rem', padding: '2px 6px', color: '#94a3b8' }}
            >
              <Edit3 size={12} />
              <span>{isEditingMainGoal ? 'Collapse' : 'Edit Objective'}</span>
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
                  backgroundColor: '#070b12',
                  border: '1px solid #38bdf8',
                  borderRadius: '6px',
                  color: '#f8fafc',
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
                  backgroundColor: '#070b12',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#cbd5e1',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              />
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '4px' }}>
                {mainGoal}
              </div>
              <div style={{ fontSize: '0.825rem', color: '#94a3b8', lineHeight: '1.4' }}>
                {summary}
              </div>
            </div>
          )}
        </div>

        {/* Quick metrics row */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
            <Layers size={14} color="#38bdf8" />
            <span style={{ color: '#64748b' }}>Sub-Goals:</span>
            <span className="font-mono" style={{ fontWeight: 600, color: '#38bdf8' }}>{subGoals.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
            <CheckCircle2 size={14} color="#10b981" />
            <span style={{ color: '#64748b' }}>Success Criteria:</span>
            <span className="font-mono" style={{ fontWeight: 600, color: '#10b981' }}>{criteria.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
            <ShieldAlert size={14} color="#f43f5e" />
            <span style={{ color: '#64748b' }}>Hard Constraints:</span>
            <span className="font-mono" style={{ fontWeight: 600, color: '#fb7185' }}>{hardConstraints.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
            <Shield size={14} color="#f59e0b" />
            <span style={{ color: '#64748b' }}>Soft Constraints:</span>
            <span className="font-mono" style={{ fontWeight: 600, color: '#fbbf24' }}>{softConstraints.length}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
            <FileCheck size={14} color="#8b5cf6" />
            <span style={{ color: '#64748b' }}>Output Format:</span>
            <span className="font-mono" style={{ fontWeight: 600, color: '#c084fc' }}>{expectedOutput.format}</span>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1e293b', paddingBottom: '2px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={() => setActiveSubTab('sub_goals')}
            className={`btn btn-sm ${activeSubTab === 'sub_goals' ? 'btn-secondary' : 'btn-ghost'}`}
            style={{ borderBottom: activeSubTab === 'sub_goals' ? '2px solid #38bdf8' : 'none', borderRadius: '4px 4px 0 0' }}
          >
            <Layers size={14} />
            <span>1. Sub-Goals Hierarchy ({subGoals.length})</span>
          </button>
          <button 
            onClick={() => setActiveSubTab('criteria')}
            className={`btn btn-sm ${activeSubTab === 'criteria' ? 'btn-secondary' : 'btn-ghost'}`}
            style={{ borderBottom: activeSubTab === 'criteria' ? '2px solid #10b981' : 'none', borderRadius: '4px 4px 0 0' }}
          >
            <CheckCircle2 size={14} />
            <span>2. Success Criteria Matrix ({criteria.length})</span>
          </button>
          <button 
            onClick={() => setActiveSubTab('constraints')}
            className={`btn btn-sm ${activeSubTab === 'constraints' ? 'btn-secondary' : 'btn-ghost'}`}
            style={{ borderBottom: activeSubTab === 'constraints' ? '2px solid #f43f5e' : 'none', borderRadius: '4px 4px 0 0' }}
          >
            <ShieldAlert size={14} />
            <span>3. Constraints Guardrails ({hardConstraints.length + softConstraints.length})</span>
          </button>
          <button 
            onClick={() => setActiveSubTab('output')}
            className={`btn btn-sm ${activeSubTab === 'output' ? 'btn-secondary' : 'btn-ghost'}`}
            style={{ borderBottom: activeSubTab === 'output' ? '2px solid #8b5cf6' : 'none', borderRadius: '4px 4px 0 0' }}
          >
            <FileCheck size={14} />
            <span>4. Expected Output</span>
          </button>
          <button 
            onClick={() => setActiveSubTab('raw_json')}
            className={`btn btn-sm ${activeSubTab === 'raw_json' ? 'btn-secondary' : 'btn-ghost'}`}
            style={{ borderBottom: activeSubTab === 'raw_json' ? '2px solid #06b6d4' : 'none', borderRadius: '4px 4px 0 0' }}
          >
            <Code size={14} />
            <span>5. Raw JSON Spec</span>
          </button>
        </div>
      </div>

      {/* Tab 1: Sub-Goals Hierarchy */}
      {activeSubTab === 'sub_goals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
              Ordered hierarchical decomposition of required operational stages and assigned agent roles:
            </p>
            <button 
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
                backgroundColor: '#0e1522',
                border: '1px solid #1e2a3c',
                display: 'flex',
                gap: '16px',
                alignItems: 'flex-start'
              }}
            >
              {/* Order & Reorder Controls */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', minWidth: '32px' }}>
                <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: 700, color: '#38bdf8' }}>
                  #{idx + 1}
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <button 
                    onClick={() => handleMoveSubGoal(idx, -1)} 
                    disabled={idx === 0}
                    className="btn btn-ghost btn-sm" 
                    style={{ padding: '2px', opacity: idx === 0 ? 0.2 : 1 }}
                  >
                    <ArrowUp size={12} />
                  </button>
                  <button 
                    onClick={() => handleMoveSubGoal(idx, 1)} 
                    disabled={idx === subGoals.length - 1}
                    className="btn btn-ghost btn-sm" 
                    style={{ padding: '2px', opacity: idx === subGoals.length - 1 ? 0.2 : 1 }}
                  >
                    <ArrowDown size={12} />
                  </button>
                </div>
              </div>

              {/* Body */}
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8', backgroundColor: '#131e30', padding: '2px 6px', borderRadius: '4px' }}>
                    {sg.id}
                  </span>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
                    {sg.title}
                  </h4>
                  <span className={`badge ${sg.priority === 'high' ? 'badge-rose' : (sg.priority === 'medium' ? 'badge-amber' : 'badge-slate')}`}>
                    {sg.priority}
                  </span>
                  <span className="badge badge-cyan" style={{ textTransform: 'none' }}>
                    Role: {sg.assigned_agent_role}
                  </span>
                </div>
                <p style={{ fontSize: '0.825rem', color: '#94a3b8', lineHeight: '1.4', marginBottom: '8px' }}>
                  {sg.description}
                </p>

                {/* Dependencies pills */}
                {sg.dependencies && sg.dependencies.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Depends on:</span>
                    {sg.dependencies.map((dep) => (
                      <span key={dep} className="font-mono" style={{ fontSize: '0.675rem', backgroundColor: '#1a2538', color: '#38bdf8', padding: '1px 6px', borderRadius: '3px' }}>
                        {dep}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '6px' }}>
                <button 
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
                  onClick={() => handleDeleteSubGoal(sg.id)}
                  className="btn btn-ghost btn-sm"
                  style={{ color: '#fb7185' }}
                  title="Delete Sub-Goal"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 2: Success Criteria Matrix */}
      {activeSubTab === 'criteria' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
              Objective verification criteria evaluated independently at completion:
            </p>
            <button 
              onClick={() => {
                setEditingCriterion(null);
                setIsCriterionModalOpen(true);
              }}
              className="btn btn-sm btn-emerald"
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
                  backgroundColor: '#0e1522',
                  border: '1px solid #1e2a3c',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between'
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="font-mono" style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600 }}>{sc.id}</span>
                      {sc.sub_goal_id && (
                        <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>Mapped: {sc.sub_goal_id}</span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button 
                        onClick={() => {
                          setEditingCriterion(sc);
                          setIsCriterionModalOpen(true);
                        }}
                        className="btn btn-ghost btn-sm" 
                        style={{ padding: '2px 4px' }}
                      >
                        <Edit3 size={13} />
                      </button>
                      <button 
                        onClick={() => handleDeleteCriterion(sc.id)}
                        className="btn btn-ghost btn-sm" 
                        style={{ padding: '2px 4px', color: '#fb7185' }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  <p style={{ fontSize: '0.85rem', color: '#f8fafc', fontWeight: 500, marginBottom: '10px' }}>
                    {sc.description}
                  </p>

                  <div style={{
                    backgroundColor: '#080d15',
                    border: '1px solid #1a2538',
                    borderRadius: '6px',
                    padding: '8px 10px',
                    marginBottom: '8px'
                  }}>
                    <div style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '2px' }}>
                      Verification Metric
                    </div>
                    <div className="font-mono" style={{ fontSize: '0.775rem', color: '#38bdf8' }}>
                      {sc.metric}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: '#64748b', borderTop: '1px solid #1a2538', paddingTop: '8px', marginTop: '6px' }}>
                  <span className="badge badge-emerald" style={{ fontSize: '0.625rem' }}>
                    {sc.verification_method}
                  </span>
                  {sc.expected_output && (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={sc.expected_output}>
                      Target: {sc.expected_output}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Constraints Guardrails */}
      {activeSubTab === 'constraints' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Hard Constraints Column */}
          <div className="card-panel" style={{ padding: '18px', backgroundColor: '#0e1522', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldAlert size={18} color="#f43f5e" />
                <div>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fb7185' }}>
                    Hard Constraints ({hardConstraints.length})
                  </h4>
                  <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Strict invariant walls — Never violated</span>
                </div>
              </div>
              <button 
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
                    backgroundColor: '#120f18',
                    border: '1px solid rgba(244, 63, 94, 0.25)',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <span className="font-mono" style={{ fontSize: '0.7rem', color: '#fb7185', fontWeight: 600 }}>{hc.id}</span>
                      <span className="badge badge-rose" style={{ fontSize: '0.6rem' }}>{hc.category}</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: '#f1f5f9', lineHeight: '1.4' }}>
                      {hc.text}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '2px', marginLeft: '8px' }}>
                    <button 
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
                      onClick={() => handleDeleteConstraint(hc.id, true)}
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '2px', color: '#fb7185' }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Soft Constraints Column */}
          <div className="card-panel" style={{ padding: '18px', backgroundColor: '#0e1522', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield size={18} color="#f59e0b" />
                <div>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fbbf24' }}>
                    Soft Constraints ({softConstraints.length})
                  </h4>
                  <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Operational preferences & guidelines</span>
                </div>
              </div>
              <button 
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
                    backgroundColor: '#141410',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <span className="font-mono" style={{ fontSize: '0.7rem', color: '#fbbf24', fontWeight: 600 }}>{sc.id}</span>
                      <span className="badge badge-amber" style={{ fontSize: '0.6rem' }}>{sc.category}</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: '#f1f5f9', lineHeight: '1.4' }}>
                      {sc.text}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '2px', marginLeft: '8px' }}>
                    <button 
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
                      onClick={() => handleDeleteConstraint(sc.id, false)}
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '2px', color: '#fb7185' }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Expected Output */}
      {activeSubTab === 'output' && (
        <div className="card-panel" style={{ padding: '24px', backgroundColor: '#0e1522', maxWidth: '640px' }}>
          <h4 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileCheck size={18} color="#8b5cf6" /> Expected Output Artifact Specifications
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Target Output Format</label>
              <input 
                type="text" 
                value={expectedOutput.format} 
                onChange={(e) => setExpectedOutput({ ...expectedOutput, format: e.target.value })}
                placeholder="e.g. JSON Summary & Audit Ledger"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#070b12',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Schema & Artifact Structure</label>
              <textarea 
                value={expectedOutput.schema_summary} 
                onChange={(e) => setExpectedOutput({ ...expectedOutput, schema_summary: e.target.value })}
                rows={3}
                placeholder="Description of required fields, arrays, checksums, or report sections..."
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#070b12',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.85rem',
                  outline: 'none',
                  resize: 'vertical'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Delivery Target / Destination</label>
              <input 
                type="text" 
                value={expectedOutput.delivery_target} 
                onChange={(e) => setExpectedOutput({ ...expectedOutput, delivery_target: e.target.value })}
                placeholder="e.g. Support Dashboard and Event Ledger"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#070b12',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: Raw JSON Spec */}
      {activeSubTab === 'raw_json' && (
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#090d14' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span className="font-mono" style={{ fontSize: '0.75rem', color: '#64748b' }}>
              Canonical JSON Manifest (Task ID: {goalModel?.task_id})
            </span>
            <button 
              onClick={() => navigator.clipboard.writeText(JSON.stringify(goalModel, null, 2))}
              className="btn btn-secondary btn-sm"
            >
              Copy JSON
            </button>
          </div>
          <pre className="font-mono" style={{
            fontSize: '0.775rem',
            color: '#38bdf8',
            backgroundColor: '#05070c',
            padding: '16px',
            borderRadius: '6px',
            overflowX: 'auto',
            maxHeight: '420px'
          }}>
            {JSON.stringify(goalModel, null, 2)}
          </pre>
        </div>
      )}

      {/* Persistent Save Patch Bar */}
      <div style={{
        position: 'sticky',
        bottom: '16px',
        backgroundColor: '#111827',
        border: '1px solid #24344d',
        borderRadius: '10px',
        padding: '12px 20px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 50
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, marginRight: '16px' }}>
          <span style={{ fontSize: '0.775rem', fontWeight: 600, color: '#94a3b8', whiteSpace: 'nowrap' }}>
            Change Summary Log:
          </span>
          <input 
            type="text"
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            placeholder="e.g. Added constraint for manager approval threshold (optional note)"
            style={{
              flex: 1,
              padding: '6px 10px',
              backgroundColor: '#070b12',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              color: '#f8fafc',
              fontSize: '0.8rem',
              outline: 'none'
            }}
          />
        </div>

        <button 
          onClick={handleTriggerSavePatch}
          disabled={isSaving}
          className="btn btn-primary"
          style={{ padding: '8px 18px' }}
        >
          <Save size={14} />
          <span>{isSaving ? 'Patching Goal Model...' : 'Save & Bump Version'}</span>
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
