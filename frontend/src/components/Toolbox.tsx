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

// --- Resize configuration ---------------------------------------------------
const MIN_WIDTH = 200;
const MIN_HEIGHT = 220;
// Width of the invisible drag strips that line each edge; corners get a
// slightly larger square so they're easy to grab.
const EDGE = 8;
const CORNER = 14;

const handleBase: React.CSSProperties = {
  position: 'absolute',
  zIndex: 2,
  // Stop touch scrolling from hijacking a resize drag on touch devices.
  touchAction: 'none',
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
  draftPoints,
  draftIsSimple,
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

  // --- Resizable panel state ------------------------------------------------
  // `height: null` means "size to content" (keeps the original auto-height +
  // maxHeight behaviour until the user drags a vertical edge for the first
  // time). Once resized, an explicit pixel height takes over.
  const panelRef = React.useRef<HTMLDivElement>(null);
  const [box, setBox] = React.useState<{
    top: number;
    left: number;
    width: number;
    height: number | null;
  }>({ top: 20, left: 20, width: 240, height: null });

  // `dir` is any combination of n/s/e/w. Dragging an edge that isn't anchored
  // to the panel's top-left corner (west/north) also shifts left/top so the
  // opposite edge stays put while the box grows or shrinks.
  const startResize = React.useCallback(
    (dir: string) => (e: React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const rect = panelRef.current?.getBoundingClientRect();
      const start = {
        top: box.top,
        left: box.left,
        width: rect?.width ?? box.width,
        height: rect?.height ?? box.height ?? MIN_HEIGHT,
      };
      const startX = e.clientX;
      const startY = e.clientY;
      const rightEdge = start.left + start.width;
      const bottomEdge = start.top + start.height;

      const onMove = (ev: PointerEvent) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        let { top, left, width, height } = start;

        if (dir.includes('e')) width = Math.max(MIN_WIDTH, start.width + dx);
        if (dir.includes('w')) {
          width = Math.max(MIN_WIDTH, start.width - dx);
          left = rightEdge - width; // keep the right edge fixed
        }
        if (dir.includes('s')) height = Math.max(MIN_HEIGHT, start.height + dy);
        if (dir.includes('n')) {
          height = Math.max(MIN_HEIGHT, start.height - dy);
          top = bottomEdge - height; // keep the bottom edge fixed
        }

        setBox({ top, left, width, height });
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      };

      // Prevent text selection / cursor flicker while dragging.
      document.body.style.userSelect = 'none';
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    },
    [box],
  );

  const selectedTool = React.useMemo(
    () => TOOLBOX_ITEMS.find((item) => item.type === toolType) ?? null,
    [toolType],
  );

  // Polygon tools are the only ones whose ring can self-intersect; point tools
  // are never blocked by the simple-polygon check below.
  const isPolygonTool = selectedTool?.kind === 'polygon';

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
  // For polygon tools the drawn ring must also be simple (non-self-intersecting);
  // isPolygonSimple returns true for empty/short rings, so this only blocks once
  // an actual crossing exists.
  const canSaveTool =
    citySelected &&
    Boolean(selectedTool) &&
    toolName.trim() !== '' &&
    toolColor.trim() !== '' &&
    allParamsFilled &&
    (toolActiveFrom ?? '').trim() !== '' &&
    (toolActiveTo ?? '').trim() !== '' &&
    (!isPolygonTool || draftIsSimple);

  return (
    <div
      ref={panelRef}
      style={{
        position: 'absolute',
        top: box.top,
        left: box.left,
        zIndex: 30,
        width: box.width,
        height: box.height ?? undefined,
        // Keep the original clamp only while auto-sizing; once the user sets an
        // explicit height, that wins.
        maxHeight: box.height == null ? 'calc(100% - 40px)' : undefined,
        border: '1px solid rgba(148, 163, 184, 0.45)',
        backgroundColor: 'rgba(2, 8, 23, 0.9)',
        borderRadius: 10,
        color: '#f1f5f9',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
        display: 'flex',
        flexDirection: 'column',
        // Clip the inner scroll area to the rounded corners; also clips the
        // edge handles so they don't spill past the border.
        overflow: 'hidden',
      }}
    >
      {/* --- Scrollable content ------------------------------------------- */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '12px 14px',
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
                      if (item.kind === 'polygon') {
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

            {/* --- Polygon coordinates + self-intersection warning ---
                Only shown for polygon tools. draftPoints are stored [lng, lat];
                displayed as "lat, lng" to match the hover tooltip's convention. */}
            {isPolygonTool && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 12, color: '#cbd5e1' }}>Polygon Coordinates</div>

                <div
                  style={{
                    maxHeight: 132,
                    overflowY: 'auto',
                    border: '1px solid rgba(148, 163, 184, 0.35)',
                    borderRadius: 6,
                    padding: '6px 8px',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                    fontSize: 12,
                  }}
                >
                  {draftPoints.length === 0 ? (
                    <div style={{ color: '#64748b' }}>No points yet</div>
                  ) : (
                    draftPoints.map(([lng, lat], i) => (
                      <div
                        key={i}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: 12,
                          color: '#cbd5e1',
                          padding: '1px 0',
                        }}
                      >
                        <span style={{ color: '#64748b' }}>#{i + 1}</span>
                        <span>
                          {lat.toFixed(6)}, {lng.toFixed(6)}
                        </span>
                      </div>
                    ))
                  )}
                </div>

                {!draftIsSimple && (
                  <div
                    role="alert"
                    style={{
                      padding: '8px 10px',
                      borderRadius: 6,
                      border: '1px solid rgba(245, 158, 11, 0.5)',
                      backgroundColor: 'rgba(245, 158, 11, 0.12)',
                      color: '#fbbf24',
                      fontSize: 12,
                      lineHeight: 1.4,
                    }}
                  >
                    This polygon&apos;s edges cross each other. Adjust the points so
                    the outline doesn&apos;t overlap before saving.
                  </div>
                )}
              </div>
            )}

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
                  : isPolygonTool && !draftIsSimple
                    ? 'Fix the self-intersecting polygon before saving'
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
                onClick={() => {
                  placedObjectsControls?.clearPendingPlacedObject?.();
                  onCancelDrawing();
                }}
                disabled={!citySelected}
                title={!citySelected ? 'Select a city on the map first' : undefined}
                style={{
                  ...toolbarButtonStyle,
                  backgroundColor: 'rgba(30, 41, 59, 0.9)',
                  color: '#fca5a5',
                }}
              >
                <Trash2 size={15} /> Clear object
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

        {!isDrawing || isPolygonTool ? (
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

            {/* Reuse the same crossing warning for the POI-area draw flow. */}
            {pointCount >= 3 && !draftIsSimple && (
              <div
                role="alert"
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  border: '1px solid rgba(245, 158, 11, 0.5)',
                  backgroundColor: 'rgba(245, 158, 11, 0.12)',
                  color: '#fbbf24',
                  fontSize: 12,
                  lineHeight: 1.4,
                }}
              >
                This area&apos;s edges cross each other. Fix the outline before
                finishing.
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={onFinishArea}
                disabled={!citySelected || pointCount < 3 || !draftIsSimple}
                style={{
                  ...toolbarButtonStyle,
                  backgroundColor:
                    citySelected && pointCount >= 3 && draftIsSimple
                      ? '#16a34a'
                      : 'rgba(71, 85, 105, 0.6)',
                  color: '#f8fafc',
                  cursor:
                    citySelected && pointCount >= 3 && draftIsSimple
                      ? 'pointer'
                      : 'not-allowed',
                }}
                title={
                  !citySelected
                    ? 'Select a city on the map first'
                    : pointCount >= 3 && !draftIsSimple
                      ? 'Fix the self-intersecting area before finishing'
                      : undefined
                }
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

      {/* --- Resize handles: four edges + four corners -------------------- */}
      {/* Edges */}
      <div
        onPointerDown={startResize('n')}
        style={{ ...handleBase, top: 0, left: CORNER, right: CORNER, height: EDGE, cursor: 'ns-resize' }}
      />
      <div
        onPointerDown={startResize('s')}
        style={{ ...handleBase, bottom: 0, left: CORNER, right: CORNER, height: EDGE, cursor: 'ns-resize' }}
      />
      <div
        onPointerDown={startResize('w')}
        style={{ ...handleBase, left: 0, top: CORNER, bottom: CORNER, width: EDGE, cursor: 'ew-resize' }}
      />
      <div
        onPointerDown={startResize('e')}
        style={{ ...handleBase, right: 0, top: CORNER, bottom: CORNER, width: EDGE, cursor: 'ew-resize' }}
      />
      {/* Corners (sit above the edges) */}
      <div
        onPointerDown={startResize('nw')}
        style={{ ...handleBase, top: 0, left: 0, width: CORNER, height: CORNER, cursor: 'nwse-resize', zIndex: 3 }}
      />
      <div
        onPointerDown={startResize('ne')}
        style={{ ...handleBase, top: 0, right: 0, width: CORNER, height: CORNER, cursor: 'nesw-resize', zIndex: 3 }}
      />
      <div
        onPointerDown={startResize('sw')}
        style={{ ...handleBase, bottom: 0, left: 0, width: CORNER, height: CORNER, cursor: 'nesw-resize', zIndex: 3 }}
      />
      <div
        onPointerDown={startResize('se')}
        style={{ ...handleBase, bottom: 0, right: 0, width: CORNER, height: CORNER, cursor: 'nwse-resize', zIndex: 3 }}
      />
    </div>
  );
};

export default Toolbox;