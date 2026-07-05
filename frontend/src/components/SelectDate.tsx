import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';

interface SelectDateProps {
  // Selected date as 'YYYY-MM-DD', or null when nothing is chosen yet.
  value: string | null;
  onChange: (isoDate: string) => void;
  // Heading shown above the trigger. Defaults to "Date".
  label?: string;
  // Optional bounds (inclusive), as 'YYYY-MM-DD'. Days outside are disabled.
  minDate?: string;
  maxDate?: string;
  // If provided, ONLY these dates ('YYYY-MM-DD') are selectable — handy for a
  // heatmap where only some days have data.
  availableDates?: string[];
  disabled?: boolean;
  // 0 = weeks start on Sunday (default), 1 = Monday.
  weekStartsOn?: 0 | 1;
  /**
   * 'panel' (default) renders self-contained chrome (border + translucent
   * background). 'bare' drops it for embedding in an existing panel/toolbar.
   */
  variant?: 'panel' | 'bare';
  className?: string;
  // Escape hatch for positioning (e.g. absolute placement over the map).
  style?: React.CSSProperties;
}

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

const addDays = (date: Date, n: number): Date =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate() + n);

const addMonths = (date: Date, n: number): Date =>
  new Date(date.getFullYear(), date.getMonth() + n, 1);

const startOfMonth = (date: Date): Date =>
  new Date(date.getFullYear(), date.getMonth(), 1);

const triggerFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

const monthTitleFmt = new Intl.DateTimeFormat(undefined, {
  month: 'long',
  year: 'numeric',
});

const WEEKDAY_LABELS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

const panelStyle: React.CSSProperties = {
  border: '1px solid rgba(148, 163, 184, 0.45)',
  backgroundColor: 'rgba(2, 8, 23, 0.88)',
  borderRadius: 10,
  padding: '10px 12px',
  boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
};

const navButtonStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 28,
  height: 28,
  flexShrink: 0,
  borderRadius: 8,
  border: '1px solid rgba(148, 163, 184, 0.45)',
  backgroundColor: 'rgba(15, 23, 42, 0.9)',
  color: '#e2e8f0',
  cursor: 'pointer',
};

const SelectDate: React.FC<SelectDateProps> = ({
  value,
  onChange,
  label = 'Date',
  minDate,
  maxDate,
  availableDates,
  disabled = false,
  weekStartsOn = 0,
  variant = 'panel',
  className,
  style,
}) => {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  const selectedDate = useMemo(() => (value ? parseISODate(value) : null), [value]);

  // The month currently shown in the grid.
  const [viewDate, setViewDate] = useState<Date>(() =>
    startOfMonth(selectedDate ?? new Date()),
  );

  const availableSet = useMemo(
    () => (availableDates ? new Set(availableDates) : null),
    [availableDates],
  );

  const todayIso = useMemo(() => toISODate(new Date()), []);

  // When opening, jump the grid to the selected month (or today).
  useEffect(() => {
    if (open) setViewDate(startOfMonth(selectedDate ?? new Date()));
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

  // 42 cells (6 weeks) starting on the configured weekday, including trailing
  // days from adjacent months so the grid height stays stable.
  const cells = useMemo(() => {
    const first = startOfMonth(viewDate);
    const offset = (first.getDay() - weekStartsOn + 7) % 7;
    const gridStart = addDays(first, -offset);
    return Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  }, [viewDate, weekStartsOn]);

  const weekdays = useMemo(
    () => WEEKDAY_LABELS.map((_, i) => WEEKDAY_LABELS[(i + weekStartsOn) % 7]),
    [weekStartsOn],
  );

  const selectDay = (date: Date) => {
    const iso = toISODate(date);
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

  const viewMonth = viewDate.getMonth();

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
        <Calendar size={15} color="#94a3b8" style={{ flexShrink: 0 }} />
      </button>

      {/* Popover calendar */}
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
          {/* Month navigation */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 10,
            }}
          >
            <button
              type="button"
              onClick={() => setViewDate((d) => addMonths(d, -1))}
              aria-label="Previous month"
              style={navButtonStyle}
            >
              <ChevronLeft size={16} />
            </button>
            <div style={{ fontSize: 13, fontWeight: 700 }}>
              {monthTitleFmt.format(viewDate)}
            </div>
            <button
              type="button"
              onClick={() => setViewDate((d) => addMonths(d, 1))}
              aria-label="Next month"
              style={navButtonStyle}
            >
              <ChevronRight size={16} />
            </button>
          </div>

          {/* Weekday header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gap: 2,
              marginBottom: 4,
            }}
          >
            {weekdays.map((wd, i) => (
              <div
                key={`wd-${i}`}
                style={{
                  textAlign: 'center',
                  fontSize: 11,
                  fontWeight: 600,
                  color: '#64748b',
                  padding: '2px 0',
                }}
              >
                {wd}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div
            style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}
          >
            {cells.map((date) => {
              const iso = toISODate(date);
              const inMonth = date.getMonth() === viewMonth;
              const isSelected = value === iso;
              const isToday = iso === todayIso;
              const dayDisabled = isDisabledDate(iso);

              let color = inMonth ? '#e2e8f0' : '#475569';
              if (dayDisabled) color = '#334155';
              if (isSelected) color = '#02121f';

              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => selectDay(date)}
                  disabled={dayDisabled}
                  aria-label={triggerFmt.format(date)}
                  aria-pressed={isSelected}
                  style={{
                    height: 30,
                    borderRadius: 6,
                    border:
                      isToday && !isSelected
                        ? '1px solid rgba(56, 189, 248, 0.6)'
                        : '1px solid transparent',
                    backgroundColor: isSelected ? '#38bdf8' : 'transparent',
                    color,
                    fontSize: 12,
                    fontWeight: isSelected ? 700 : 500,
                    cursor: dayDisabled ? 'not-allowed' : 'pointer',
                    padding: 0,
                  }}
                >
                  {date.getDate()}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default SelectDate;