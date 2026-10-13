import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

export default function ParsingProgress({ modelName, requirements = true }) {
  const [elapsedSec, setElapsedSec] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setElapsedSec(value => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return <section className="card-panel" style={{ padding: 32, textAlign: 'center' }} role="status" aria-live="polite">
    <Loader2 size={26} aria-hidden="true" />
    <h3>{requirements ? 'Preparing requirements for your review' : 'Running the requested workflow stages'}</h3>
    <p>{requirements ? 'Checking the request and preparing a proposed goal. Code runs only after you confirm it.' : 'Your requirements are confirmed. Follow the execution log below for progress.'}</p>
    <p>Elapsed: {elapsedSec}s{modelName ? ` · Selected model: ${modelName}` : ''}</p>
    {requirements && elapsedSec >= 10 && <p>Still waiting for requirement analysis. If the model does not respond, a draft will be offered for review.</p>}
  </section>;
}
