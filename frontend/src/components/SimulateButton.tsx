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
        border: '1px solid rgba(56, 189, 248, 0.45)',
        backgroundColor: 'rgba(8, 47, 73, 0.95)',
        color: '#e0f2fe',
        fontSize: 13,
        fontWeight: 700,
        letterSpacing: '0.01em',
        cursor: disabled ? 'not-allowed' : 'pointer',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.25)',
        transition: 'transform 120ms ease, background-color 120ms ease, border-color 120ms ease',
        opacity: disabled ? 0.65 : 1,
        ...style,
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
      }}
    >
      {label}
    </button>
  );
};

export default SimulateButton;