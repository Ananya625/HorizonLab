// Request ownership is centralized so a slow previous run never replaces current data.
export function createWorkflowController(api, publish) {
  let generation = 0;
  const requestNumbers = { view: 0, evidence: 0 };
  let abort;
  let state = { runId: null, loading: false, report: null, page: null, evidence: [], finding: null, error: null, history: [0] };
  const update = patch => { state = { ...state, ...patch }; publish(state); };
  async function guarded(operation, channel = 'view') {
    const owner = generation;
    const request = ++requestNumbers[channel];
    try { await operation(() => owner === generation && request === requestNumbers[channel], abort?.signal); }
    catch (err) { if (owner === generation && request === requestNumbers[channel] && err.name !== 'AbortError') update({ error: err.message, ...(channel === 'view' ? { loading: false } : {}) }); }
  }
  return {
    async select(runId) {
      generation += 1; abort?.abort(); abort = new AbortController();
      update({ runId, loading: !!runId, report: null, page: null, evidence: [], finding: null, error: null, history: [0] });
      if (!runId) return;
      await guarded(async (current, signal) => {
        const report = await api.report(runId, signal);
        if (!current()) return;
        const page = await api.events(runId, 0, report.snapshot_sequence, signal);
        if (current()) update({ report, page, loading: false });
      });
    },
    async page(direction) {
      if (!state.report || state.loading) return;
      const history = [...state.history];
      if (direction === 'next' && state.page?.next_after != null) history.push(state.page.next_after);
      else if (direction === 'previous' && history.length > 1) history.pop();
      else return;
      update({ loading: true, error: null });
      await guarded(async (current, signal) => {
        const page = await api.events(state.runId, history.at(-1), state.report.snapshot_sequence, signal);
        if (current()) update({ page, history, loading: false });
      });
    },
    async inspect(finding) {
      const runId = state.runId;
      update({ finding, evidence: [], error: null });
      await guarded(async (current, signal) => {
        const evidence = await Promise.all(finding.event_ids.map(id => api.event(runId, id, signal)));
        if (current()) update({ evidence });
      }, 'evidence');
    },
    dispose() { generation += 1; abort?.abort(); },
  };
}
