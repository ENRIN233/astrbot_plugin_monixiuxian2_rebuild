import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

interface ProgressBarProps {
  value: number;
  max: number;
  label?: string;
  color?: string;
}

export function ProgressBar({ value, max, label, color }: Omit<ProgressBarProps, 'color'> & { color?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-20px' });
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;

  return (
    <div ref={ref} className="min-w-[80px]">
      {label && (
        <div className="flex justify-between text-xs mb-1" style={{ color: 'rgba(200,208,224,0.4)' }}>
          <span>{label}</span>
          <span className="font-mono" style={{ color: 'rgba(0,240,255,0.7)' }}>{value.toLocaleString()}</span>
        </div>
      )}
      <div className="progress-mini">
        <motion.div
          className="progress-mini-fill"
          initial={{ width: 0 }}
          animate={isInView ? { width: `${pct}%` } : { width: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          style={color ? { background: `linear-gradient(90deg, ${color}33, ${color})` } : undefined}
        />
      </div>
      {!label && (
        <span className="font-mono text-xs mt-1 block" style={{ color: 'rgba(0,240,255,0.5)' }}>
          {value.toLocaleString()}
        </span>
      )}
    </div>
  );
}
