import React, { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, CircleHelp, X } from 'lucide-react';

const TOUR_STEPS = [
  {
    stage: 'input',
    eyebrow: '01 / Start with a task',
    title: 'A clear brief is the start of a traceable run.',
    description: 'Enter the coding request, choose a workspace, and review the model connection before asking HorizonLab to analyze it.'
  },
  {
    stage: 'goal_model',
    eyebrow: '02 / Make the goal explicit',
    title: 'Turn intent into requirements you can inspect.',
    description: 'Review the parsed goal, constraints, acceptance criteria, and any questions that need your confirmation before execution.'
  },
  {
    stage: 'planner',
    eyebrow: '03 / Inspect the plan',
    title: 'See the proposed work before code is changed.',
    description: 'The planner view shows the repository analysis and implementation steps returned for this run. No plan is shown when one has not been generated.'
  },
  {
    stage: 'coder',
    eyebrow: '04 / Follow implementation',
    title: 'Review the files the coding stage changed.',
    description: 'Open the coding view to inspect the recorded changes and continue to testing. An empty view means there are no recorded code changes for the selected run.'
  },
  {
    stage: 'testing',
    eyebrow: '05 / Check regression evidence',
    title: 'Test results and recovery are separate from task success.',
    description: 'Inspect recorded test runs and recovery attempts. Passing tests alone do not imply that the independent verifier approved the task.'
  },
  {
    stage: 'verifier',
    eyebrow: '06 / Verify independently',
    title: 'Reported completion is not the same as verified completion.',
    description: 'The verifier reports only the checks and evidence the backend supports. Missing evidence and failed checks remain visible rather than being treated as success.'
  },
  {
    stage: 'evaluations',
    eyebrow: '07 / Audit the outcome',
    title: 'Trace the result back to the run evidence.',
    description: 'Explore the saved evaluation, workflow events, sub-goal evidence, and resource measurements for the selected run. Unavailable measurements remain explicitly unavailable.'
  }
];

export default function GuidedTour({
  onClose,
  onNavigate,
  runId,
  goalModel,
  codeChanges = [],
  testResults = [],
  verification
}) {
  const [stepIndex, setStepIndex] = useState(0);
  const step = TOUR_STEPS[stepIndex];
  const isSummary = stepIndex === TOUR_STEPS.length - 1;
  const passedTests = testResults.filter((result) => result.status === 'PASSED').length;
  const failedTests = testResults.filter((result) => result.status === 'FAILED').length;

  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  const goToStep = (nextIndex) => {
    const boundedIndex = Math.max(0, Math.min(TOUR_STEPS.length - 1, nextIndex));
    setStepIndex(boundedIndex);
    onNavigate(TOUR_STEPS[boundedIndex].stage);
  };

  return (
    <div className="tour-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="tour-dialog" role="dialog" aria-modal="true" aria-labelledby="tour-title">
        <header className="tour-dialog-header">
          <div className="tour-dialog-brand">
            <span className="tour-icon"><CircleHelp size={17} /></span>
            <div>
              <p>HorizonLab walkthrough</p>
              <span>{runId ? `Using run ${runId}` : 'No run selected'}</span>
            </div>
          </div>
          <button type="button" className="tour-close" onClick={onClose} aria-label="Close guided tour">
            <X size={18} />
          </button>
        </header>

        <div className="tour-progress" aria-label={`Step ${stepIndex + 1} of ${TOUR_STEPS.length}`}>
          {TOUR_STEPS.map((tourStep, index) => (
            <span
              key={tourStep.stage}
              className={index <= stepIndex ? 'is-complete' : ''}
              aria-hidden="true"
            />
          ))}
        </div>

        <div className="tour-dialog-content">
          <p className="tour-eyebrow">{step.eyebrow}</p>
          <h2 id="tour-title">{step.title}</h2>
          <p className="tour-description">{step.description}</p>

          {isSummary ? (
            <div className="tour-summary" aria-label="Current run summary">
              <div className="tour-summary-item">
                <span>Original goal</span>
                <strong>{goalModel?.main_goal || 'Requirements have not been parsed'}</strong>
              </div>
              <div className="tour-summary-grid">
                <div className="tour-summary-item">
                  <span>Independent verification</span>
                  <strong>{verification?.overall_verdict || 'Not run'}</strong>
                </div>
                <div className="tour-summary-item">
                  <span>Recorded code changes</span>
                  <strong>{runId ? codeChanges.length : 'Unavailable'}</strong>
                </div>
                <div className="tour-summary-item">
                  <span>Test runs · passed / failed</span>
                  <strong>{testResults.length ? `${testResults.length} · ${passedTests} / ${failedTests}` : 'No test runs recorded'}</strong>
                </div>
              </div>
              <p className="tour-honesty-note">
                This walkthrough reads the selected run only. It does not start agents or add sample results.
              </p>
            </div>
          ) : (
            <div className="tour-data-note">
              {runId
                ? <><CheckCircle2 size={15} /> Explore this stage using the selected run’s saved data.</>
                : <><CircleHelp size={15} /> No run is selected yet. You can explore the task composer now.</>}
            </div>
          )}
        </div>

        <footer className="tour-dialog-footer">
          <span>{stepIndex + 1} of {TOUR_STEPS.length}</span>
          <div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => goToStep(stepIndex - 1)}
              disabled={stepIndex === 0}
            >
              <ArrowLeft size={15} /> Back
            </button>
            {isSummary ? (
              <button type="button" className="btn btn-primary" onClick={onClose}>
                Finish <CheckCircle2 size={15} />
              </button>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => goToStep(stepIndex + 1)}>
                Next <ArrowRight size={15} />
              </button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}
