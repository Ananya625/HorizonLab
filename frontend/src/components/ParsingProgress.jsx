import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

export default function ParsingProgress({ modelName, requirements = true }) {
  const [elapsedSec, setElapsedSec] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setElapsedSec(value => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <section 
      className="card-panel" 
      style={{ 
        padding: '36px 24px', 
        textAlign: 'center', 
        backgroundColor: '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px'
      }} 
      role="status" 
      aria-live="polite"
    >
      <Loader2 size={30} aria-hidden="true" className="animate-spin" color="var(--accent-primary, #6257D9)" />
      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary, #172033)', margin: 0 }}>
        {requirements ? 'Preparing requirements for your review' : 'Running the requested workflow stages'}
      </h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', maxWidth: '520px', margin: 0 }}>
        {requirements ? 'Checking the request and preparing a proposed goal. Code runs only after you confirm it.' : 'Your requirements are confirmed. Follow the execution log below for progress.'}
      </p>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #667085)', margin: 0, fontFamily: 'var(--font-mono)' }}>
        Elapsed: {elapsedSec}s{modelName ? ` · Selected model: ${modelName}` : ''}
      </p>
      {requirements && elapsedSec >= 10 && (
        <p style={{ fontSize: '0.75rem', color: 'var(--warning-color, #B7791F)', margin: 0 }}>
          Still waiting for requirement analysis. If the model does not respond, a draft will be offered for review.
        </p>
      )}
    </section>
  );
}
