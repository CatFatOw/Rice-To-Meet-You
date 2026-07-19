import React from 'react';
import type { HeatRiskScaleProps } from '../types/components';

const HeatRiskScale: React.FC<HeatRiskScaleProps> = ({ label, gradient }) => {
  const isTemperature = label.trim().toLowerCase() === 'temperature';
  const tickLabels = isTemperature ? ['10', '20', '30', '40', '50'] : ['0', '25', '50', '75', '100'];

  return (
    <div
      style={{
        position: 'absolute',
        right: 20,
        bottom: 20,
        zIndex: 25,
        width: 240,
        border: '1px solid rgba(148, 163, 184, 0.45)',
        backgroundColor: 'rgba(2, 8, 23, 0.88)',
        borderRadius: 10,
        padding: '10px 12px',
        color: '#f1f5f9',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>{label} Scale</div>
      <div
        style={{
          height: 12,
          width: '100%',
          borderRadius: 999,
          background: gradient,
          border: '1px solid rgba(148, 163, 184, 0.35)',
        }}
      />
      <div
        style={{
          marginTop: 6,
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          color: '#cbd5e1',
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
          color: '#94a3b8',
        }}
      >
        <span>Low</span>
        <span>High</span>
      </div>
    </div>
  );
};

export default HeatRiskScale;