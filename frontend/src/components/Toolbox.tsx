import React from 'react';
import { Pencil, Check, Undo2, X, Trash2, Crosshair } from 'lucide-react';
import { TOOLBOX_ITEMS, TOOLBOX_DRAG_MIME, type ToolboxItemDef } from '../services/toolbox';
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
  selectedCity,
  draftName,
  setDraftName,
  draftColorHex,
  setDraftColorHex,
  hasUserAreasInCity,
  editingAreaId,
  onFinishEdit,
  placedCount,
  onClearObjects: _onClearObjects,
  isDrawing,
  draftPointCount,
  onStartDrawing,
  onFinishArea,
  onUndoLastPoint,
  onCancelDrawing,
  onClearMyAreas,
  onSetDraftColor,
  placedObjectsControls,
  onCommitDrawing: _onCommitDrawing,
  draftPoints: _draftPoints,
}) => {
  const pointCount = draftPointCount;
  const citySelected = Boolean(selectedCity);
  const pendingPlacedObject = placedObjectsControls?.pendingPlacedObject ?? null;
  const setPendingPlacedObject = placedObjectsControls?.setPendingPlacedObject;
  const updatePendingPlacedObject = placedObjectsControls?.updatePendingPlacedObject;
  const toolType = pendingPlacedObject?.type ?? null;
  const toolName = pendingPlacedObject?.name ?? '';
  const toolColor = pendingPlacedObject?.color ?? '';
  const toolParams = pendingPlacedObject?.params ?? {};
  const toolActiveFrom = pendingPlacedObject?.activeFrom ?? null;
  const toolActiveTo = pendingPlacedObject?.activeTo ?? null;

  const selectedTool = React.useMemo(
    () => TOOLBOX_ITEMS.find((item) => item.type === toolType) ?? null,
    [toolType],
  );

  React.useEffect(() => {
    if (!selectedTool) return;
    updatePendingPlacedObject?.({
      name: selectedTool.label,
      color: selectedTool.color,
      params: { ...selectedTool.params },
    });
  }, [selectedTool, updatePendingPlacedObject]);

  React.useEffect(() => {
    if (!selectedTool) return;
    onSetDraftColor(selectedTool.color);
  }, [selectedTool, onSetDraftColor]);

  const toolParamEntries = React.useMemo(
    () =>
      Object.keys(selectedTool?.params ?? {}).map(
        (key) => [key, toolParams[key]] as const,
      ),
    [selectedTool, toolParams],
  );

  // A param counts as "filled" only if it's non-blank and a real number.
  // Vacuously true for tools with no params (there's nothing left unfilled).
  const allParamsFilled = React.useMemo(
    () => toolParamEntries.every(([, raw]) => typeof raw === 'number' && Number.isFinite(raw)),
    [toolParamEntries],
  );

  // Single source of truth for whether the tool can be saved. Every editable
  // input must be present: a city, a selected tool, a name, a color, all
  // params, and both active-window dates. "0" passes (it's filled); "" fails.
  const canSaveTool =
    citySelected &&
    Boolean(selectedTool) &&
    toolName.trim() !== '' &&
    toolColor.trim() !== '' &&
    allParamsFilled &&
    (toolActiveFrom ?? '').trim() !== '' &&
    (toolActiveTo ?? '').trim() !== '';

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
      {!citySelected && (
        <div
          style={{
            fontSize: 12,
            color: '#fca5a5',
            backgroundColor: 'rgba(127, 29, 29, 0.25)',
            border: '1px solid rgba(248, 113, 113, 0.35)',
            borderRadius: 6,
            padding: '6px 8px',
          }}
        >
          Select a city on the map to enable all toolbox inputs.
        </div>
      )}

      {/* --- Date selector (drives selected heatmap day) --- */}
      <div style={{ fontSize: 13, fontWeight: 700 }}>Date</div>
      <SelectDate
        label="Date"
        value={selectedDate}
        onChange={(isoDate) => setSelectedDate(isoDate)}
        availableDates={availableDates}
        disabled={!citySelected}
        variant="bare"
        style={{ width: '100%' }}
      />
      <div style={dividerStyle} />

      {/* --- Metric toggle (always visible, regardless of selected city) --- */}
      <div style={{ fontSize: 13, fontWeight: 700 }}>Metric</div>
      <button
        type="button"
        onClick={onToggleMetric}
        disabled={!citySelected || !canToggleMetric}
        title="Toggle metric"
        style={{
          ...toolbarButtonStyle,
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          color: '#e2e8f0',
          cursor: citySelected && canToggleMetric ? 'pointer' : 'not-allowed',
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
            Drag point tools onto the map. Click polygon tools to start drawing them on the map.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {TOOLBOX_ITEMS.map((item: ToolboxItemDef) => {
              const Icon = item.Icon;
              const isPoint = item.kind === 'point';
              const isSelected = citySelected && toolType === item.type;
              return (
                <div
                  key={item.type}
                  draggable={isPoint && citySelected}
                  onDragStart={(e) => {
                    if (!isPoint || !citySelected) return;
                    e.dataTransfer.setData(TOOLBOX_DRAG_MIME, item.type);
                    e.dataTransfer.setData(
                      'application/x-toolbox-params',
                      JSON.stringify(item.params),
                    );
                    e.dataTransfer.effectAllowed = 'copy';
                    // Seed a pending object so dragover has something to reposition.
                    setPendingPlacedObject?.({
                 
                      type: item.type,
                      name: item.label,
                      color: item.color,
                      params: { ...item.params },
                      geometry: { kind: 'point', longitude: 0, latitude: 0 },
                    });
                  }}
                  onClick={() => {
                    if (!citySelected) return;
                    setPendingPlacedObject?.({

                      type: item.type,
                      name: pendingPlacedObject?.name?.trim() ? pendingPlacedObject.name : item.label,
                      color: pendingPlacedObject?.color ?? item.color,
                      params:
                        pendingPlacedObject?.type === item.type && pendingPlacedObject.params
                          ? pendingPlacedObject.params
                          : { ...item.params },
                      activeFrom: pendingPlacedObject?.activeFrom,
                      activeTo: pendingPlacedObject?.activeTo,
                      geometry: { kind: 'polygon', ring: [] },
                    });
                    if (item.kind === 'polygon'){
                      onStartDrawing();
                      onSetDraftColor(pendingPlacedObject?.color ?? item.color);
                      
                      
                    }
                    // Pass the whole item: the ring it produces becomes a placed
                    // object of this type, not a POI area.
                    
                    
                  }}
                  title={isPoint ? `Drag to place ${item.label}` : `Click to draw ${item.label}`}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 6,
                    padding: '10px 6px',
                    borderRadius: 8,
                    border: isSelected
                      ? `1px solid ${item.color}`
                      : '1px solid rgba(148, 163, 184, 0.35)',
                    backgroundColor: isSelected ? `${item.color}22` : 'rgba(15, 23, 42, 0.9)',
                    boxShadow: isSelected ? `0 0 0 1px ${item.color}` : 'none',
                    cursor: !citySelected ? 'not-allowed' : isPoint ? 'grab' : 'pointer',
                    userSelect: 'none',
                    textAlign: 'center',
                    opacity: citySelected ? 1 : 0.6,
                    pointerEvents: citySelected ? 'auto' : 'none',
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

          <label
            style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}
          >
            Tool Name
            <input
              type="text"
              value={toolName}
              onChange={(e) => updatePendingPlacedObject?.({ name: e.target.value })}
              disabled={!citySelected}
              placeholder="Enter tool name"
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
            Tool Color
            <input
              type="color"
              value={toolColor}
              onChange={(e) => updatePendingPlacedObject?.({ color: e.target.value })}
              disabled={!citySelected}
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 12, color: '#cbd5e1' }}>Tool Params</div>
            {toolParamEntries.length === 0 ? (
              <div style={{ fontSize: 11, color: '#94a3b8' }}>Select a tool to edit params.</div>
            ) : (
              toolParamEntries.map(([paramKey, paramValue]) => {
                const isBlank = typeof paramValue !== 'number' || !Number.isFinite(paramValue);
                return (
                  <label
                    key={paramKey}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}
                  >
                    <span style={{ fontSize: 12, color: '#cbd5e1' }}>{paramKey}</span>
                    <input
                      type="number"
                      value={isBlank ? '' : paramValue}
                      disabled={!citySelected}
                      onChange={(e) => {
                        const nextValue = e.target.value === '' ? Number.NaN : Number(e.target.value);
                        updatePendingPlacedObject?.({
                          params: { ...toolParams, [paramKey]: nextValue },
                        });
                      }}
                      style={{
                        width: 92,
                        padding: '4px 6px',
                        borderRadius: 6,
                        // Flag empty/invalid params so the user sees what's blocking Save.
                        border: isBlank
                          ? '1px solid rgba(248, 113, 113, 0.7)'
                          : '1px solid rgba(148, 163, 184, 0.45)',
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        color: '#f1f5f9',
                        fontSize: 12,
                      }}
                    />
                  </label>
                );
              })
            )}
          </div>

          {/* --- Active window: both dates required before Save is enabled --- */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 12, color: '#cbd5e1' }}>Active From</div>
            <SelectDate
              label="Active From"
              value={toolActiveFrom}
              onChange={(isoDate) => updatePendingPlacedObject?.({ activeFrom: isoDate })}
              availableDates={availableDates}
              disabled={!citySelected}
              variant="bare"
              style={{ width: '100%' }}
            />
            <div style={{ fontSize: 12, color: '#cbd5e1' }}>Active To</div>
            <SelectDate
              label="Active To"
              value={toolActiveTo}
              onChange={(isoDate) => updatePendingPlacedObject?.({ activeTo: isoDate })}
              availableDates={availableDates}
              disabled={!citySelected}
              variant="bare"
              style={{ width: '100%' }}
            />
          </div>

          <button
            type="button"
            style={{
              ...toolbarButtonStyle,
              backgroundColor: canSaveTool ? 'rgba(14, 116, 144, 0.85)' : 'rgba(71, 85, 105, 0.6)',
              color: '#e0f2fe',
              cursor: canSaveTool ? 'pointer' : 'not-allowed',
              opacity: canSaveTool ? 1 : 0.6,
            }}
            onClick={() => {
              if (!canSaveTool) return;
              void placedObjectsControls?.commitPendingPlacedObject?.();
            }}
            disabled={!canSaveTool}
            title={
              !citySelected
                ? 'Select a city on the map first'
                : !canSaveTool
                  ? 'Fill in the tool name, params, and active dates before saving'
                  : undefined
            }
          >
            <Check size={15} /> Save Changes
          </button>

          {placedCount > 0 && (
            <button
              type="button"
              onClick={() => placedObjectsControls?.clearPendingPlacedObject?.()}
              disabled={!citySelected}
              title={!citySelected ? 'Select a city on the map first' : undefined}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                color: '#fca5a5',
              }}
            >
              <Trash2 size={15} /> Clear objects 
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
          disabled={!citySelected}
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
          disabled={!citySelected}
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
          title={!citySelected ? 'Select a city on the map first' : undefined}
        >
          <Pencil size={15} /> Draw new area
        </button>
      ) : (
        <>
          <div style={{ fontSize: 12, color: '#cbd5e1' }}>
            Click the map to add points ({pointCount} placed, need 3+).
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={onFinishArea}
              disabled={!citySelected || pointCount < 3}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: citySelected && pointCount >= 3 ? '#16a34a' : 'rgba(71, 85, 105, 0.6)',
                color: '#f8fafc',
                cursor: citySelected && pointCount >= 3 ? 'pointer' : 'not-allowed',
              }}
              title={!citySelected ? 'Select a city on the map first' : undefined}
            >
              <Check size={15} /> Finish
            </button>
            <button
              type="button"
              onClick={onUndoLastPoint}
              disabled={!citySelected || pointCount === 0}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                color: '#e2e8f0',
                cursor: citySelected && pointCount > 0 ? 'pointer' : 'not-allowed',
              }}
              title={!citySelected ? 'Select a city on the map first' : undefined}
            >
              <Undo2 size={15} /> Undo
            </button>
          </div>
          <button
            type="button"
            onClick={onCancelDrawing}
            disabled={!citySelected}
            style={{
              ...toolbarButtonStyle,
              backgroundColor: 'rgba(30, 41, 59, 0.9)',
              color: '#fca5a5',
              cursor: citySelected ? 'pointer' : 'not-allowed',
            }}
            title={!citySelected ? 'Select a city on the map first' : undefined}
          >
            <X size={15} /> Cancel
          </button>
        </>
      )}

      {hasUserAreasInCity && (
        <button
          type="button"
          onClick={onClearMyAreas}
          disabled={!citySelected}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: 'rgba(30, 41, 59, 0.9)',
            color: '#fca5a5',
            cursor: citySelected ? 'pointer' : 'not-allowed',
          }}
          title={!citySelected ? 'Select a city on the map first' : undefined}
        >
          <Trash2 size={15} /> Clear my areas
        </button>
      )}

      {editingAreaId && (
        <button
          type="button"
          onClick={onFinishEdit}
          disabled={!citySelected}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: 'rgba(14, 116, 144, 0.85)',
            color: '#e0f2fe',
            cursor: citySelected ? 'pointer' : 'not-allowed',
          }}
          title={!citySelected ? 'Select a city on the map first' : undefined}
        >
          <Check size={15} /> Finish Edit
        </button>
      )}
    </div>
  );
};

export default Toolbox;