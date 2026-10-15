import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { rolldown } from 'rolldown';
import { createRequire } from 'node:module';

let cachedComponent = null;

async function getWorkflowView() {
  if (cachedComponent) return cachedComponent;
  const bundle = await rolldown({
    input: './src/components/WorkflowAnalysis.jsx',
    external: ['react', 'react/jsx-runtime']
  });
  const { output } = await bundle.generate({ format: 'cjs', exports: 'named' });
  const module = { exports: {} };
  new Function('require', 'module', 'exports', output[0].code)(createRequire(import.meta.url), module, module.exports);
  cachedComponent = module.exports.WorkflowView;
  return cachedComponent;
}

test('frontend correctly distinguishes task verification from evidence completeness', async () => {
  const WorkflowView = await getWorkflowView();
  const report = {
    version: 'workflow-v1',
    execution_mode: 'mixed_demo',
    evidence_status: 'partial',
    task_verification_status: 'verified_passed',
    workflow_evidence_completeness: 'partial',
    snapshot_sequence: 1,
    summary: {
      action_attempts: 10,
      verified_sub_goals: 3,
      required_sub_goals: 3,
      progress_rate: 1.0,
      verified_outcome: true,
      resources: { tool_calls: 10, model_calls: 0 }
    },
    coverage: {
      paired_outcomes: 1.0,
      state_references: 1.0,
      sub_goal_mapping: 0.632
    },
    sub_goal_mapping_coverage: {
      mapped_percentage: 63.2,
      unmapped_percentage: 36.8,
      mapped_actions: 12,
      unmapped_actions: 7
    },
    sub_goals: [
      { id: 's1', title: 'Goal 1', status: 'verified', attempts: 1, resources: {} },
      { id: 's2', title: 'Goal 2', status: 'verified', attempts: 1, resources: {} },
      { id: 's3', title: 'Goal 3', status: 'verified', attempts: 1, resources: {} }
    ],
    findings: [],
    overhead: { recovery: {}, rework: {}, union: {} },
    limitations: []
  };

  const html = renderToStaticMarkup(React.createElement(WorkflowView, {
    state: { runId: 'run-1', report, history: [0], evidence: [] }
  }));

  // Must clearly show Task: Verified Passed
  assert.match(html, /Task:\s*Verified Passed/);
  // Must show Evidence: Partial Evidence separately
  assert.match(html, /Evidence:\s*Partial Evidence/);
  // Must show mapping coverage separately without conflating
  assert.match(html, /63\.2% mapped/);
  assert.match(html, /36\.8% unmapped/);
});

test('frontend renders clear explanation box for partial-evidence status', async () => {
  const WorkflowView = await getWorkflowView();
  const report = {
    version: 'workflow-v1',
    evidence_status: 'partial',
    task_verification_status: 'verified_passed',
    workflow_evidence_completeness: 'partial',
    partial_evidence_reasons: [
      '7 of 19 action(s) (36.8%) were executed outside sub-goal scopes (e.g., initial system inspection, planning, or independent verification).'
    ],
    sub_goal_mapping_coverage: {
      mapped_percentage: 63.2,
      unmapped_percentage: 36.8,
      mapped_actions: 12,
      unmapped_actions: 7
    },
    summary: { action_attempts: 19, verified_sub_goals: 3, required_sub_goals: 3 },
    coverage: { sub_goal_mapping: 0.632 },
    sub_goals: [],
    findings: [],
    overhead: { recovery: {}, rework: {}, union: {} }
  };

  const html = renderToStaticMarkup(React.createElement(WorkflowView, {
    state: { runId: 'run-1', report, history: [0], evidence: [] }
  }));

  // Explanation box exists with role and aria-label
  assert.match(html, /Why is workflow evidence partial\?/);
  assert.match(html, /7 of 19 action\(s\) \(36\.8%\) were executed outside sub-goal scopes/);
  assert.match(html, /aria-label="Partial evidence explanation"/);
});

test('frontend renders readable finding titles without hover', async () => {
  const WorkflowView = await getWorkflowView();
  const report = {
    version: 'workflow-v1',
    evidence_status: 'observed',
    task_verification_status: 'unverified',
    workflow_evidence_completeness: 'complete',
    summary: {},
    coverage: {},
    sub_goals: [],
    overhead: { recovery: {}, rework: {}, union: {} },
    findings: [
      {
        id: 'f1',
        kind: 'plan_dependency_unverified',
        title: 'Plan Step 2 started before Step 1 was verified',
        status: 'unverified',
        confidence: 'observed',
        message: 'Plan step 2 prerequisites were not verified.',
        reason: 'Prerequisite Step 1 lacks conclusive passing verification evidence.',
        recommended_action: 'Execute and pass verification checks for Step 1 before executing Step 2.',
        occurrence_count: 1
      }
    ]
  };

  const html = renderToStaticMarkup(React.createElement(WorkflowView, {
    state: { runId: 'run-1', report, history: [0], evidence: [] }
  }));

  // Finding title is rendered directly in markup without hovering
  assert.match(html, /Plan Step 2 started before Step 1 was verified/);
  // Reason and action are also rendered
  assert.match(html, /Prerequisite Step 1 lacks conclusive passing verification evidence/);
  assert.match(html, /Execute and pass verification checks for Step 1 before executing Step 2/);
  // Status chip is rendered
  assert.match(html, /wf-finding-chip is-unverified/);
});

test('frontend provides accessible expandable rows with keyboard support and chevron', async () => {
  const WorkflowView = await getWorkflowView();
  const report = {
    version: 'workflow-v1',
    evidence_status: 'observed',
    summary: {},
    coverage: {},
    sub_goals: [],
    overhead: { recovery: {}, rework: {}, union: {} },
    findings: [
      {
        id: 'f1',
        kind: 'plan_dependency_unverified',
        title: 'Plan Step 2 started before Step 1 was verified',
        status: 'unverified',
        prerequisite_step: 1,
        dependent_step: 2,
        occurrence_count: 3
      }
    ]
  };

  const html = renderToStaticMarkup(React.createElement(WorkflowView, {
    state: { runId: 'run-1', report, history: [0], evidence: [] }
  }));

  // Native details tag for semantic, fully accessible keyboard expand/collapse
  assert.match(html, /<details[^>]*class="wf-finding-card"/);
  assert.match(html, /<summary[^>]*role="button"/);
  assert.match(html, /tabindex="0"/i);
  assert.match(html, /wf-chevron/);
  assert.match(html, /aria-label="Finding: Plan Step 2 started before Step 1 was verified, Status: unverified"/);
});

test('frontend contains no blank controls or unlabelled buttons in finding rows', async () => {
  const WorkflowView = await getWorkflowView();
  const report = {
    version: 'workflow-v1',
    evidence_status: 'observed',
    summary: {},
    coverage: {},
    sub_goals: [],
    overhead: { recovery: {}, rework: {}, union: {} },
    findings: [
      {
        id: 'f1',
        kind: 'plan_dependency_unverified',
        title: 'Plan Step 2 started before Step 1 was verified',
        status: 'unverified'
      }
    ]
  };

  const html = renderToStaticMarkup(React.createElement(WorkflowView, {
    state: { runId: 'run-1', report, history: [0], evidence: [] }
  }));

  // There should be NO empty button tags like <button ...></button>
  assert.doesNotMatch(html, /<button[^>]*>\s*<\/button>/);
  // Any button inside finding card has text like "Inspect Event Evidence"
  assert.match(html, /Inspect Event Evidence/);
});

test('frontend displays correct finding grouping, step pills, and occurrence counts', async () => {
  const WorkflowView = await getWorkflowView();
  const report = {
    version: 'workflow-v1',
    evidence_status: 'observed',
    summary: {},
    coverage: {},
    sub_goals: [],
    overhead: { recovery: {}, rework: {}, union: {} },
    findings: [
      {
        id: 'f1',
        kind: 'plan_dependency_unverified',
        title: 'Plan Step 2 started before Step 1 was verified',
        status: 'unverified',
        prerequisite_step: 1,
        dependent_step: 2,
        occurrence_count: 5
      },
      {
        id: 'f2',
        kind: 'single_occurrence_finding',
        title: 'Isolated issue',
        status: 'failed',
        occurrence_count: 1
      }
    ]
  };

  const html = renderToStaticMarkup(React.createElement(WorkflowView, {
    state: { runId: 'run-1', report, history: [0], evidence: [] }
  }));

  // Step dependency pill
  assert.match(html, /Step 1 → Step 2/);
  // Occurrence count badge shown when > 1
  assert.match(html, /5× occurrences/);
  // Occurrence badge NOT shown for single occurrence
  assert.doesNotMatch(html, /1× occurrences/);
  // Total recorded occurrences in header
  assert.match(html, /6 total recorded occurrence\(s\)/);
});
