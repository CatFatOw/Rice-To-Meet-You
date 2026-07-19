import React from 'react';
import { Pencil, Check, Undo2, X, Trash2, Crosshair, MapPin, type LucideIcon } from 'lucide-react';
import { TOOLBOX_DRAG_MIME } from '../services/toolbox';
import {
  getToolboxItems,
  type ArchetypeType,
  type ToolboxItemsByArchetype,
  type ToolboxItemDef,
  TOOLBOX_ICONS,
  ARCHETYPE_PARAMS,
} from '../data/toolboxItems';
import type { ToolboxProps } from '../types/components';
import SelectDate from './SelectDate';
import { addToolboxItems } from '../data/toolboxItems';
import { createPOIArea } from '../api/statistics';

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

// Shared input/select styling for the dark panel.
const fieldStyle: React.CSSProperties = {
  padding: '6px 8px',
  borderRadius: 6,
  border: '1px solid rgba(148, 163, 184, 0.45)',
  backgroundColor: 'rgba(15, 23, 42, 0.9)',
  color: '#f1f5f9',
  fontSize: 13,
  width: '100%',
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

type ArchetypeKey = ArchetypeType;
type CustomCategoryKey = keyof typeof ARCHETYPE_PARAMS;

const ARCHETYPE_KEYS: ArchetypeKey[] = [
  'Vegetation',
  'High-albedo surface',
  'Shade structure',
  'Evaporative / water',
];
const CUSTOM_CATEGORY_KEYS = Object.keys(ARCHETYPE_PARAMS) as CustomCategoryKey[];
const ICON_ENTRIES = Object.entries(TOOLBOX_ICONS) as [string, LucideIcon][];

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
  placedCount: _placedCount,
  onClearObjects: _onClearObjects,
  isDrawing,
  draftPointCount,
  draftIsSimple,
  onStartDrawing,
  onFinishArea,
  onUndoLastPoint,
  onCancelDrawing,
  onClearMyAreas,
  onSetDraftColor,
  placedObjectsControls,
  onCommitDrawing: _onCommitDrawing,
  draftPoints,
}) => {
  const pointCount = draftPointCount;
  const citySelected = Boolean(selectedCity);
  const pendingPlacedObject = placedObjectsControls?.pendingPlacedObject ?? null;
  const setPendingPlacedObject = placedObjectsControls?.setPendingPlacedObject;
  const updatePendingPlacedObject = placedObjectsControls?.updatePendingPlacedObject;
  const toolColor = pendingPlacedObject?.color ?? '';
  const toolActiveFrom = pendingPlacedObject?.activeFrom ?? null;
  const toolActiveTo = pendingPlacedObject?.activeTo ?? null;

  // --- Urban-interventions selection state ----------------------------------
  // Which archetype the dropdown points at, and which intervention icon within
  // it is active. The pending object no longer carries a tool `type`, so these
  // live here as local UI state.
  const [selectedArchetype, setSelectedArchetype] = React.useState<ArchetypeKey | ''>('');
  const [selectedInterventionId, setSelectedInterventionId] = React.useState<string | null>(null);
  const [toolboxItems, setToolboxItems] = React.useState<ToolboxItemsByArchetype>({
    Vegetation: [],
    'High-albedo surface': [],
    'Shade structure': [],
    'Evaporative / water': [],
  });

  // --- Custom-intervention form state ---------------------------------------
  const [customIconName, setCustomIconName] = React.useState<keyof typeof TOOLBOX_ICONS | ''>('');
  const [customName, setCustomName] = React.useState<string>('');
  const [customCategory, setCustomCategory] = React.useState<CustomCategoryKey | ''>('');
  const [customParams, setCustomParams] = React.useState<Record<string, number>>({});
  const [customColor, setCustomColor] = React.useState<string>('#22c55e');

  React.useEffect(() => {
    let ignore = false;

    void getToolboxItems()
      .then((items) => {
        if (!ignore) setToolboxItems(items);
      })
      .catch((error) => {
        if (!ignore) {
          console.error('Failed to load toolbox items', error);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

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

  // Interventions in the chosen archetype, and the one currently selected.
  const interventions: ToolboxItemDef[] = selectedArchetype ? toolboxItems[selectedArchetype] : [];
  const selectedTool = React.useMemo(
    () => interventions.find((item) => item.id === selectedInterventionId) ?? null,
    [interventions, selectedInterventionId],
  );

  // Polygon tools are the only ones whose ring can self-intersect; point tools
  // are never blocked by the simple-polygon check below.
  const isPolygonTool = selectedTool?.kind === 'polygon';

  // Keep the map's draft color in step with the (editable) polygon color.
  React.useEffect(() => {
    if (isPolygonTool && toolColor) onSetDraftColor(toolColor);
  }, [isPolygonTool, toolColor, onSetDraftColor]);

  // Stage a fresh pending object for the clicked intervention. Dates already
  // entered are carried across so switching interventions doesn't wipe them.
  const handleSelectIntervention = React.useCallback(
    (item: ToolboxItemDef) => {
      if (!citySelected || !selectedArchetype) return;
      setSelectedInterventionId(item.id);
      setPendingPlacedObject?.({
        type: item.type,
        category: selectedArchetype,
        name: item.label,
        color: item.color,
        params: { ...item.params },
        activeFrom: pendingPlacedObject?.activeFrom,
        activeTo: pendingPlacedObject?.activeTo,
        geometry:
          item.kind === 'polygon'
            ? { kind: 'polygon', ring: [] }
            : { kind: 'point', longitude: 0, latitude: 0 },
      });
      if (item.kind === 'polygon') {
        onStartDrawing();
        onSetDraftColor(item.color);
      }
    },
    [citySelected, selectedArchetype, setPendingPlacedObject, pendingPlacedObject, onStartDrawing, onSetDraftColor],
  );

  const handleClearObject = React.useCallback(() => {
    placedObjectsControls?.clearPendingPlacedObject?.();
    onCancelDrawing();
    setSelectedInterventionId(null);
  }, [placedObjectsControls, onCancelDrawing]);


  const handlePOISubmit = React.useCallback(async () => {
    try {
      await createPOIArea(draftName, draftColorHex, draftPoints);
      // Resolve logic: the create succeeded, so tear the draft down here.
      // draftPoints and drawing mode are parent-owned, so onCancelDrawing is
      // what clears the placed points and exits the draw flow.
      setDraftName('');
      setDraftColorHex('#2563eb');
      onCancelDrawing();
    } catch (error) {
      console.error('Failed to create POI area', error);
    }
  }, [draftName, draftColorHex, draftPoints, setDraftName, setDraftColorHex, onCancelDrawing]);

  // Save gate for the selected intervention: a city, an intervention, both
  // dates, and — for polygons only — a color plus a valid (simple, 3+ point)
  // ring. Point interventions have no color/ring requirement.
  const canSaveTool =
    citySelected &&
    Boolean(selectedTool) &&
    (toolActiveFrom ?? '').trim() !== '' &&
    (toolActiveTo ?? '').trim() !== '' &&
    (isPolygonTool ? toolColor.trim() !== '' && pointCount >= 3 && draftIsSimple : true);

  // --- Custom intervention validity -----------------------------------------
  const customParamKeys: readonly string[] = customCategory ? ARCHETYPE_PARAMS[customCategory] : [];
  const allCustomParamsFilled = customParamKeys.every(
    (key) => typeof customParams[key] === 'number' && Number.isFinite(customParams[key]),
  );
  const canAddCustom =
    citySelected &&
    customIconName !== '' &&
    customName.trim() !== '' &&
    customCategory !== '' &&
    customParamKeys.length > 0 &&
    allCustomParamsFilled;

  const handleAddCustom = React.useCallback(async () => {
    if (!canAddCustom || !customCategory) return;
    const payload = {
      id: `custom-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      label: customName.trim(),
      iconName: customIconName,
      Icon: TOOLBOX_ICONS[customIconName as keyof typeof TOOLBOX_ICONS],
      color: customColor,
      category: customCategory,
      params: { ...customParams },
    };
    await addToolboxItems(payload);

    setCustomIconName('');
    setCustomName('');
    setCustomColor('#22c55e');
    setCustomCategory('');
    setCustomParams({});
  }, [canAddCustom, customCategory, customName, customIconName, customColor, customParams]);

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

        {/* --- Urban Interventions (full toolbox layout only) --- */}
        {displayToolbox && (
          <>
            <div style={{ fontSize: 13, fontWeight: 700 }}>Urban Interventions</div>

            {/* --- Choose archetype --- */}
            <label
              style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}
            >
              Choose archetype
              <select
                value={selectedArchetype}
                disabled={!citySelected}
                onChange={(e) => {
                            setSelectedArchetype((e.target.value || '') as ArchetypeKey | '');
                  setSelectedInterventionId(null);
                  placedObjectsControls?.clearPendingPlacedObject?.();
                }}
                style={{
                  ...fieldStyle,
                  cursor: citySelected ? 'pointer' : 'not-allowed',
                  opacity: citySelected ? 1 : 0.6,
                }}
              >
                <option value="">Select archetype…</option>
                {ARCHETYPE_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>

            {/* --- Choose intervention (only after an archetype is picked) --- */}
            {selectedArchetype && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 12, color: '#cbd5e1' }}>Choose intervention</div>
                {interventions.length === 0 ? (
                  <div style={{ fontSize: 11, color: '#94a3b8' }}>
                    No interventions in this archetype yet.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {interventions.map((item) => {
                      const Icon = item.Icon;
                      const isPoint = item.kind === 'point';
                      const isSelected = selectedInterventionId === item.id;
                      return (
                        <div
                          key={item.id}
                          draggable={isPoint && citySelected}
                          onDragStart={(e) => {
                            if (!isPoint || !citySelected) return;
                            e.dataTransfer.setData(TOOLBOX_DRAG_MIME, item.id);
                            e.dataTransfer.setData(
                              'application/x-toolbox-params',
                              JSON.stringify(item.params),
                            );
                            e.dataTransfer.effectAllowed = 'copy';
                            handleSelectIntervention(item);
                          }}
                          onClick={() => handleSelectIntervention(item)}
                          title={isPoint ? `Place ${item.label}` : `Draw ${item.label}`}
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
                )}
              </div>
            )}

            {/* --- Intervention config (only after an icon is clicked) --- */}
            {selectedTool && (
              <>
                {/* Active window */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ fontSize: 12, color: '#cbd5e1' }}>Start date</div>
                  <SelectDate
                    label="Start date"
                    value={toolActiveFrom}
                    onChange={(isoDate) => updatePendingPlacedObject?.({ activeFrom: isoDate })}
                    availableDates={availableDates}
                    disabled={!citySelected}
                    variant="bare"
                    style={{ width: '100%' }}
                  />
                  <div style={{ fontSize: 12, color: '#cbd5e1' }}>End date</div>
                  <SelectDate
                    label="End date"
                    value={toolActiveTo}
                    onChange={(isoDate) => updatePendingPlacedObject?.({ activeTo: isoDate })}
                    availableDates={availableDates}
                    disabled={!citySelected}
                    variant="bare"
                    style={{ width: '100%' }}
                  />
                </div>

                {/* Polygon coordinates. draftPoints are stored [lng, lat] and
                    displayed "lat, lng" to match the hover tooltip. */}
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

                  {isPolygonTool && !draftIsSimple && (
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
                      This polygon&apos;s edges cross each other. Adjust the points so the
                      outline doesn&apos;t overlap before saving.
                    </div>
                  )}
                </div>

                {/* Draw POI (polygon) vs Choose Point (point) */}
                {isPolygonTool ? (
                  <button
                    type="button"
                    onClick={onStartDrawing}
                    disabled={!citySelected}
                    style={{
                      ...toolbarButtonStyle,
                      backgroundColor: citySelected ? '#2563eb' : 'rgba(71, 85, 105, 0.6)',
                      color: '#f8fafc',
                      cursor: citySelected ? 'pointer' : 'not-allowed',
                    }}
                    title={!citySelected ? 'Select a city on the map first' : undefined}
                  >
                    <Pencil size={15} /> Draw POI
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleSelectIntervention(selectedTool)}
                    disabled={!citySelected}
                    style={{
                      ...toolbarButtonStyle,
                      backgroundColor: citySelected ? '#2563eb' : 'rgba(71, 85, 105, 0.6)',
                      color: '#f8fafc',
                      cursor: citySelected ? 'pointer' : 'not-allowed',
                    }}
                    title={!citySelected ? 'Select a city on the map first' : undefined}
                  >
                    <MapPin size={15} /> Choose Point
                  </button>
                )}

                {/* Color input only for polygon interventions */}
                {isPolygonTool && (
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: 12,
                      color: '#cbd5e1',
                    }}
                  >
                    Color
                    <input
                      type="color"
                      value={toolColor || selectedTool.color}
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
                )}

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
                          ? 'Fill in the dates (and color/polygon for POIs) before saving'
                          : undefined
                  }
                >
                  <Check size={15} /> Save Changes
                </button>

                <button
                  type="button"
                  onClick={handleClearObject}
                  disabled={!citySelected}
                  title={!citySelected ? 'Select a city on the map first' : undefined}
                  style={{
                    ...toolbarButtonStyle,
                    backgroundColor: 'rgba(30, 41, 59, 0.9)',
                    color: '#fca5a5',
                    cursor: citySelected ? 'pointer' : 'not-allowed',
                  }}
                >
                  <Trash2 size={15} /> Clear Object
                </button>
              </>
            )}

            <div style={dividerStyle} />

            {/* --- Custom interventions --- */}
            <div style={{ fontSize: 13, fontWeight: 700 }}>Custom Interventions</div>

            {/* Choose icon */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ fontSize: 12, color: '#cbd5e1' }}>Choose icon</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6 }}>
                {ICON_ENTRIES.map(([name, IconComp]) => {
                  const isSelected = customIconName === name;
                  return (
                    <button
                      key={name}
                      type="button"
                      disabled={!citySelected}
                      onClick={() => setCustomIconName(name as keyof typeof TOOLBOX_ICONS)}
                      title={name}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: 8,
                        borderRadius: 8,
                        border: isSelected
                          ? '1px solid #38bdf8'
                          : '1px solid rgba(148, 163, 184, 0.35)',
                        backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.15)' : 'rgba(15, 23, 42, 0.9)',
                        cursor: citySelected ? 'pointer' : 'not-allowed',
                        opacity: citySelected ? 1 : 0.6,
                      }}
                    >
                      <IconComp size={16} color={isSelected ? '#e0f2fe' : '#cbd5e1'} />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Name */}
            <label
              style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}
            >
              Name
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                disabled={!citySelected}
                placeholder="Enter intervention name"
                style={fieldStyle}
              />
            </label>

            {/* Choose color */}
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: 12,
                color: '#cbd5e1',
              }}
            >
              Choose color
              <input
                type="color"
                value={customColor}
                onChange={(e) => setCustomColor(e.target.value)}
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

            {/* Choose category */}
            <label
              style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}
            >
              Choose category
              <select
                value={customCategory}
                disabled={!citySelected}
                onChange={(e) => {
                  setCustomCategory((e.target.value || '') as CustomCategoryKey | '');
                  setCustomParams({});
                }}
                style={{
                  ...fieldStyle,
                  cursor: citySelected ? 'pointer' : 'not-allowed',
                  opacity: citySelected ? 1 : 0.6,
                }}
              >
                <option value="">Select category…</option>
                {CUSTOM_CATEGORY_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>

            {/* Params for the chosen category */}
            {customCategory && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 12, color: '#cbd5e1' }}>Params</div>
                {ARCHETYPE_PARAMS[customCategory].map((paramKey) => {
                  const raw = customParams[paramKey];
                  const isBlank = typeof raw !== 'number' || !Number.isFinite(raw);
                  return (
                    <label
                      key={paramKey}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 8,
                      }}
                    >
                      <span style={{ fontSize: 12, color: '#cbd5e1' }}>{paramKey}</span>
                      <input
                        type="number"
                        value={isBlank ? '' : raw}
                        disabled={!citySelected}
                        onChange={(e) => {
                          const nextValue = e.target.value === '' ? Number.NaN : Number(e.target.value);
                          setCustomParams((prev) => ({ ...prev, [paramKey]: nextValue }));
                        }}
                        style={{
                          width: 92,
                          padding: '4px 6px',
                          borderRadius: 6,
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
                })}
              </div>
            )}

            <button
              type="button"
              disabled={!canAddCustom}
              onClick={handleAddCustom}
              title={
                !citySelected
                  ? 'Select a city on the map first'
                  : !canAddCustom
                    ? 'Choose an icon, name, category, and fill every param first'
                    : undefined
              }
              style={{
                ...toolbarButtonStyle,
                backgroundColor: canAddCustom ? 'rgba(14, 116, 144, 0.85)' : 'rgba(71, 85, 105, 0.6)',
                color: '#e0f2fe',
                cursor: canAddCustom ? 'pointer' : 'not-allowed',
                opacity: canAddCustom ? 1 : 0.6,
              }}
            >
              <Check size={15} /> Add Intervention
            </button>

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
                onClick={() => {
                  void handlePOISubmit();
                }}
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