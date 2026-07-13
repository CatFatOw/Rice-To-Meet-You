import React from 'react';
import { Pencil, Check, Undo2, X, Trash2, Crosshair } from 'lucide-react';
import { TOOLBOX_ITEMS, TOOLBOX_DRAG_MIME, type ToolboxItemDef } from '../utils/toolbox';
import type { ToolboxProps } from '../types/components';
import SelectDate from './SelectDate';

const toolbarButtonStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid rgba(148, 163, 184, 0.45)',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  width: '100%',
};

const dividerStyle: React.CSSProperties = {
  height: 1,
  backgroundColor: 'rgba(148, 163, 184, 0.3)',
  margin: '2px 0',
};

const Toolbox: React.FC<ToolboxProps> = ({
  displayToolbox,
  selectedDate,
  setSelectedDate,
  availableDates,
  metricLabel,
  canToggleMetric,
  onToggleMetric,
  placedCount,
  onClearObjects,
  selectedCity,
  draftName,
  setDraftName,
  draftColorHex,
  setDraftColorHex,
  isDrawing,
  draftPointCount,
  onStartDrawing,
  onFinishArea,
  onUndoLastPoint,
  onCancelDrawing,
  hasUserAreasInCity,
  onClearMyAreas,
  editingAreaId,
  onFinishEdit,
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        top: 20,
        left: 20,
        zIndex: 30,
        width: 240,
        maxHeight: 'calc(100% - 40px)',
        overflowY: 'auto',
        border: '1px solid rgba(148, 163, 184, 0.45)',
        backgroundColor: 'rgba(2, 8, 23, 0.9)',
        borderRadius: 10,
        padding: '12px 14px',
        color: '#f1f5f9',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      {/* --- Date selector (drives selected heatmap day) --- */}
      <div style={{ fontSize: 13, fontWeight: 700 }}>Date</div>
      <SelectDate
        label="Date"
        value={selectedDate}
        onChange={(isoDate) => setSelectedDate(isoDate)}
        availableDates={availableDates}
        variant="bare"
        style={{ width: '100%' }}
      />
      <div style={dividerStyle} />

      {/* --- Metric toggle (always visible, regardless of selected city) --- */}
      <div style={{ fontSize: 13, fontWeight: 700 }}>Metric</div>
      <button
        type="button"
        onClick={onToggleMetric}
        disabled={!canToggleMetric}
        title="Toggle metric"
        style={{
          ...toolbarButtonStyle,
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          color: '#e2e8f0',
          cursor: canToggleMetric ? 'pointer' : 'default',
        }}
      >
        <Crosshair size={14} />
        <span>{metricLabel}</span>
      </button>
      <div style={dividerStyle} />

      {/* --- Placeable objects palette (full toolbox layout only) --- */}
      {displayToolbox && (
        <>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Toolbox</div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginTop: -4 }}>
            Drag an item onto the map to place it. Click a placed pin to remove it.
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {TOOLBOX_ITEMS.map((item: ToolboxItemDef) => {
              const Icon = item.Icon;
              return (
                <div
                  key={item.type}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData(TOOLBOX_DRAG_MIME, item.type);
                    e.dataTransfer.effectAllowed = 'copy';
                  }}
                  title={`Drag to place ${item.label}`}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 6,
                    padding: '10px 6px',
                    borderRadius: 8,
                    border: '1px solid rgba(148, 163, 184, 0.35)',
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    cursor: 'grab',
                    userSelect: 'none',
                    textAlign: 'center',
                  }}
                >
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 30,
                      height: 30,
                      borderRadius: 999,
                      backgroundColor: `${item.color}22`,
                      border: `1px solid ${item.color}`,
                    }}
                  >
                    <Icon size={17} color={item.color} />
                  </span>
                  <span style={{ fontSize: 11, lineHeight: 1.2, color: '#e2e8f0' }}>
                    {item.label}
                  </span>
                </div>
              );
            })}
          </div>

          {placedCount > 0 && (
            <button
              type="button"
              onClick={onClearObjects}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                color: '#fca5a5',
              }}
            >
              <Trash2 size={15} /> Clear objects ({placedCount})
            </button>
          )}

          <div style={dividerStyle} />
        </>
      )}

      {/* --- Create POI Area --- */}
      <div style={{ fontSize: 13, fontWeight: 700 }}>Create POI Area</div>

      {!selectedCity && (
        <div style={{ fontSize: 12, color: '#fca5a5' }}>
          Click a city marker first to pick a city.
        </div>
      )}

      {selectedCity && (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>
          City: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{selectedCity}</span>
        </div>
      )}

      <label
        style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}
      >
        Area name
        <input
          type="text"
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          placeholder="e.g. Downtown Core"
          style={{
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            color: '#f1f5f9',
            fontSize: 13,
          }}
        />
      </label>

      <label
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 12,
          color: '#cbd5e1',
        }}
      >
        Area color
        <input
          type="color"
          value={draftColorHex}
          onChange={(e) => setDraftColorHex(e.target.value)}
          style={{
            width: 44,
            height: 28,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            borderRadius: 6,
            background: 'transparent',
            cursor: 'pointer',
          }}
        />
      </label>

      {!isDrawing ? (
        <button
          type="button"
          onClick={onStartDrawing}
          disabled={!selectedCity}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: selectedCity ? '#2563eb' : 'rgba(71, 85, 105, 0.6)',
            color: '#f8fafc',
            cursor: selectedCity ? 'pointer' : 'not-allowed',
          }}
        >
          <Pencil size={15} /> Draw new area
        </button>
      ) : (
        <>
          <div style={{ fontSize: 12, color: '#cbd5e1' }}>
            Click the map to add points ({draftPointCount} placed, need 3+).
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={onFinishArea}
              disabled={draftPointCount < 3}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: draftPointCount >= 3 ? '#16a34a' : 'rgba(71, 85, 105, 0.6)',
                color: '#f8fafc',
                cursor: draftPointCount >= 3 ? 'pointer' : 'not-allowed',
              }}
            >
              <Check size={15} /> Finish
            </button>
            <button
              type="button"
              onClick={onUndoLastPoint}
              disabled={draftPointCount === 0}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                color: '#e2e8f0',
                cursor: draftPointCount === 0 ? 'not-allowed' : 'pointer',
              }}
            >
              <Undo2 size={15} /> Undo
            </button>
          </div>
          <button
            type="button"
            onClick={onCancelDrawing}
            style={{
              ...toolbarButtonStyle,
              backgroundColor: 'rgba(30, 41, 59, 0.9)',
              color: '#fca5a5',
            }}
          >
            <X size={15} /> Cancel
          </button>
        </>
      )}

      {hasUserAreasInCity && (
        <button
          type="button"
          onClick={onClearMyAreas}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: 'rgba(30, 41, 59, 0.9)',
            color: '#fca5a5',
          }}
        >
          <Trash2 size={15} /> Clear my areas
        </button>
      )}

      {editingAreaId && (
        <button
          type="button"
          onClick={onFinishEdit}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: 'rgba(14, 116, 144, 0.85)',
            color: '#e0f2fe',
          }}
        >
          <Check size={15} /> Finish Edit
        </button>
      )}
    </div>
  );
};

export default Toolbox;