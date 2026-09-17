import React from 'react';
import { formatMetricName } from '../services/map';
import type { HeatRiskScaleProps } from '../types/components';
import { getScaleLabels } from '../services/colors';

const HeatRiskScale: React.FC<HeatRiskScaleProps> = ({ metricKey, gradient }) => {
  const label = formatMetricName(metricKey);
  const { tickLabels, lowLabel, highLabel } = getScaleLabels(metricKey);

  return (
    <div
      style={{
        position: 'absolute',
        right: 20,
        bottom: 20,
        zIndex: 25,
        width: 240,
        border: '1px solid var(--border-strong)',
        backgroundColor: 'var(--surface-panel)',
        borderRadius: 10,
        padding: '10px 12px',
        color: 'var(--text-primary)',
        boxShadow: 'var(--shadow-panel)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>{label} Scale</div>
      <div
        style={{
          height: 12,
          width: '100%',
          borderRadius: 999,
          background: gradient,
          border: '1px solid var(--border-subtle)',
        }}
      />
      <div
        style={{
          marginTop: 6,
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          color: 'var(--text-secondary)',
        }}
      >
        {tickLabels.map((tick) => (
          <span key={tick}>{tick}</span>
        ))}
      </div>
      <div
        style={{
          marginTop: 6,
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          color: 'var(--text-muted)',
        }}
      >
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
};

export default HeatRiskScale;