export function startLogPolling({runId, active, fetchLogs, onLogs, schedule = setTimeout, cancel = clearTimeout}) {
  let disposed = false;
  let timer;
  async function refresh() {
    try {
      const data = await fetchLogs(runId);
      if (!disposed) onLogs(data.logs || []);
    } catch {
      // A transient log failure must not terminate an active workflow.
    } finally {
      if (!disposed && active) timer = schedule(refresh, 3000);
    }
  }
  if (runId) refresh();
  return () => { disposed = true; cancel(timer); };
}
