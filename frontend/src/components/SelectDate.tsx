import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { SelectDateProps } from '../types/components';

// --- Local-time-safe date helpers -------------------------------------------

// Format a Date as 'YYYY-MM-DD' using its LOCAL parts (avoids the UTC shift you
// get from Date.prototype.toISOString()).
export function toISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// Parse 'YYYY-MM-DD' into a local Date at midnight, or null if malformed.
export function parseISODate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

const triggerFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

const MONTHS = Array.from({ length: 12 }, (_, month) =>
  new Intl.DateTimeFormat(undefined, { month: 'long' }).format(new Date(2000, month, 1)),
);

const panelStyle: React.CSSProperties = {
  border: '1px solid rgba(148, 163, 184, 0.45)',
  backgroundColor: 'rgba(2, 8, 23, 0.88)',
  borderRadius: 10,
  padding: '10px 12px',
  boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
};

const selectStyle: React.CSSProperties = {
  width: '100%',
  minWidth: 0,
  height: 34,
  borderRadius: 6,
  border: '1px solid rgba(148, 163, 184, 0.45)',
  backgroundColor: 'rgba(15, 23, 42, 0.9)',
  color: '#e2e8f0',
  fontSize: 13,
  padding: '0 8px',
};

const SelectDate: React.FC<SelectDateProps> = ({
  value,
  onChange,
  label = 'Date',
  minDate,
  maxDate,
  availableDates,
  disabled = false,
  variant = 'panel',
  className,
  style,
}) => {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  const selectedDate = useMemo(() => (value ? parseISODate(value) : null), [value]);
  const initialDate = selectedDate ?? new Date();
  const [draftYear, setDraftYear] = useState(initialDate.getFullYear());
  const [draftMonth, setDraftMonth] = useState(initialDate.getMonth());
  const [draftDay, setDraftDay] = useState(initialDate.getDate());

  const availableSet = useMemo(
    () => (availableDates ? new Set(availableDates) : null),
    [availableDates],
  );

  // Reset the selectors when opening to the selected date (or today).
  useEffect(() => {
    if (!open) return;
    const date = selectedDate ?? new Date();
    setDraftYear(date.getFullYear());
    setDraftMonth(date.getMonth());
    setDraftDay(date.getDate());
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on outside click / Escape while open.
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const isDisabledDate = (iso: string): boolean => {
    if (minDate && iso < minDate) return true;
    if (maxDate && iso > maxDate) return true;
    if (availableSet && !availableSet.has(iso)) return true;
    return false;
  };

  const years = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const minYear = minDate ? parseISODate(minDate)?.getFullYear() : currentYear - 100;
    const maxYear = maxDate ? parseISODate(maxDate)?.getFullYear() : currentYear + 100;
    const start = Math.min(minYear ?? currentYear - 100, draftYear);
    const end = Math.max(maxYear ?? currentYear + 100, draftYear);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }, [draftYear, maxDate, minDate]);

  const daysInMonth = new Date(draftYear, draftMonth + 1, 0).getDate();
  const days = Array.from({ length: daysInMonth }, (_, index) => index + 1);

  const applyDate = () => {
    const iso = toISODate(new Date(draftYear, draftMonth, Math.min(draftDay, daysInMonth)));
    if (isDisabledDate(iso)) return;
    onChange(iso);
    setOpen(false);
  };

  const containerStyle: React.CSSProperties = {
    position: 'relative',
    width: 240,
    color: '#f1f5f9',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    opacity: disabled ? 0.6 : 1,
    ...(variant === 'panel' ? panelStyle : null),
    ...style,
  };

  return (
    <div ref={rootRef} className={className} style={containerStyle}>

      {/* Trigger */}
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          width: '100%',
          padding: '8px 10px',
          borderRadius: 8,
          border: '1px solid rgba(148, 163, 184, 0.45)',
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          color: selectedDate ? '#f1f5f9' : '#94a3b8',
          fontSize: 13,
          fontWeight: 600,
          cursor: disabled ? 'not-allowed' : 'pointer',
          textAlign: 'left',
        }}
      >
        <span
          style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {selectedDate ? triggerFmt.format(selectedDate) : 'Select a date'}
        </span>
      </button>

      {/* Popover selectors */}
      {open && (
        <div
          role="dialog"
          aria-label={label}
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 60,
            width: 260,
            padding: 12,
            borderRadius: 10,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            backgroundColor: 'rgba(2, 8, 23, 0.97)',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
          }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 76px 92px', gap: 6 }}>
            <select
              aria-label="Month"
              value={draftMonth}
              onChange={(event) => setDraftMonth(Number(event.target.value))}
              style={selectStyle}
            >
              {MONTHS.map((month, index) => <option key={month} value={index}>{month}</option>)}
            </select>
            <select
              aria-label="Day"
              value={Math.min(draftDay, daysInMonth)}
              onChange={(event) => setDraftDay(Number(event.target.value))}
              style={selectStyle}
            >
              {days.map((day) => <option key={day} value={day}>{day}</option>)}
            </select>
            <select
              aria-label="Year"
              value={draftYear}
              onChange={(event) => setDraftYear(Number(event.target.value))}
              style={selectStyle}
            >
              {years.map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
          </div>
          <button
            type="button"
            onClick={applyDate}
            disabled={isDisabledDate(toISODate(new Date(draftYear, draftMonth, Math.min(draftDay, daysInMonth))))}
            style={{
              width: '100%',
              height: 34,
              marginTop: 10,
              borderRadius: 6,
              border: 0,
              backgroundColor: '#38bdf8',
              color: '#02121f',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            Apply date
          </button>
        </div>
      )}
    </div>
  );
};

export default SelectDate;