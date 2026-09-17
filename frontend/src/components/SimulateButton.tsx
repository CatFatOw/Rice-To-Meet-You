import React from 'react';
import type { SimulateButtonProps } from '../types/components';

const SimulateButton: React.FC<SimulateButtonProps> = ({
  onClick,
  disabled = false,
  label = 'Simulate',
  className,
  style,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 110,
        height: 52,
        padding: '0 16px',
        borderRadius: 8,
        border: '1px solid var(--accent)',
        backgroundColor: 'var(--accent-strong)',
        color: '#f0f9ff',
        fontSize: 13,
        fontWeight: 700,
        letterSpacing: '0.01em',
        cursor: disabled ? 'not-allowed' : 'pointer',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.25)',
        transition: 'transform 120ms ease, background-color 120ms ease, border-color 120ms ease, box-shadow 120ms ease',
        opacity: disabled ? 0.65 : 1,
        ...style,
      }}
      onMouseEnter={(event) => {
        if (disabled) return;
        event.currentTarget.style.boxShadow = '0 6px 18px rgba(0, 0, 0, 0.32)';
        event.currentTarget.style.borderColor = 'var(--focus-ring)';
      }}
      onMouseDown={(event) => {
        if (disabled) return;
        event.currentTarget.style.transform = 'translateY(1px)';
      }}
      onMouseUp={(event) => {
        event.currentTarget.style.transform = 'translateY(0)';
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.transform = 'translateY(0)';
        event.currentTarget.style.boxShadow = '0 4px 14px rgba(0, 0, 0, 0.25)';
        event.currentTarget.style.borderColor = 'var(--accent)';
      }}
    >
      {label}
    </button>
  );
};

export default SimulateButton;