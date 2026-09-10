import React from 'react';
import { Pencil, Check, Undo2, X, Trash2, MapPin, type LucideIcon } from 'lucide-react';
import { TOOLBOX_DRAG_MIME, polygonParseFromRingToComma } from '../services/toolbox';
import {
  TOOLBOX_ICONS,
  ARCHETYPE_PARAMS,
} from '../data/toolboxItems';
import type {
  ArchetypeType,
  ToolboxItemDef,
  ToolboxItemsByArchetype,
} from '../types/toolbox';
import type { ToolboxProps } from '../types/components';
import SelectDate from './SelectDate';
import { createNewUrbanIntervention, fetchCustomUrbanInterventions } from '../api/tool';
import { TOOLBOX_ITEMS } from '../data/toolboxItems';
import { cities } from '../data/hostCities';
import { createPOI, type CreatePOIInput } from '../api/map';

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
const US_STATE_CODES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN',
  'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV',
  'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN',
  'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
];
function normalizePolygonWkt(value: string): string {
  const text = value.trim();
  if (/^(POLYGON|MULTIPOLYGON)\s*\(/i.test(text)) return text;

  const pairs = text.split(',').map((pair) => pair.trim().split(/\s+/));
  if (pairs.length < 3 || pairs.some((pair) => pair.length !== 2 || pair.some((part) => !Number.isFinite(Number(part))))) {
    return '';
  }

  const coordinates = pairs.map(([longitude, latitude]) => `${longitude} ${latitude}`);
  if (coordinates[0] !== coordinates[coordinates.length - 1]) {
    coordinates.push(coordinates[0]);
  }
  return `POLYGON((${coordinates.join(', ')}))`;
}

function formatInterventionLabel(intervention: string): string {
  return intervention
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}


async function getToolboxItems(): Promise<ToolboxItemsByArchetype> {


  // Copy the base items so we don't mutate TOOLBOX_ITEMS.
  const merged = (Object.keys(TOOLBOX_ITEMS) as ArchetypeType[]).reduce((acc, key) => {
    acc[key] = [...TOOLBOX_ITEMS[key]];
    return acc;
  }, {} as ToolboxItemsByArchetype);

  // Append custom interventions into their matching archetype list.
  const custom = await fetchCustomUrbanInterventions();
  (Object.keys(custom) as ArchetypeType[]).forEach((key) => {
    merged[key] = [...merged[key], ...custom[key]];
  });

  return merged;
}

const Toolbox: React.FC<ToolboxProps> = ({
  displayToolbox,
  selectedDate,
  setSelectedDate,
  setBaselineSelectedDate,
  availableDates,
  selectedMetricKey,
  metricOptions,
  onMetricChange,
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
  onFinishArea: _onFinishArea,
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
  const setIsPickingPoint = placedObjectsControls?.setIsPickingPoint;
  const setPendingPlacedObject = placedObjectsControls?.setPendingPlacedObject;
  const updatePendingPlacedObject = placedObjectsControls?.updatePendingPlacedObject;
  const toolColor = pendingPlacedObject?.color ?? '';
  const toolActiveFrom = pendingPlacedObject?.activeFrom ?? null;
  const toolActiveTo = pendingPlacedObject?.activeTo ?? null;
  const handleToolStartDateChange = React.useCallback(
    (isoDate: string) => {
      updatePendingPlacedObject?.({ activeFrom: isoDate });
      if (toolActiveTo && isoDate > toolActiveTo) {
        updatePendingPlacedObject?.({ activeTo: isoDate });
      }
    },
    [toolActiveTo, updatePendingPlacedObject],
  );


  // --- Urban-interventions selection state ----------------------------------
  // Which archetype the dropdown points at, and which intervention icon within
  // it is active. The pending object no longer carries a tool `type`, so these
  // live here as local UI state.
  const [selectedArchetype, setSelectedArchetype] = React.useState<ArchetypeKey | ''>('');
  const [selectedIntervention, setSelectedIntervention] = React.useState<string | null>(null);
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
  const [commitSuccess, setCommitSuccess] = React.useState(false);
  const [isPOIDraw, setIsPOIDraw] = React.useState(false);
  const [poi, setPoi] = React.useState<CreatePOIInput>({
    polygon: '',
    city: selectedCity ?? '',
    location_name: '',
    region: '',
    includes_parking_lot: false,
    color: draftColorHex ?? '#22c55e',
  });
  const [showOptionalPoiFields, setShowOptionalPoiFields] = React.useState(false);

  React.useEffect(() => {
    console.log('poi:', poi);
  }, [poi]);

  React.useEffect(() => {
    if (draftColorHex) {
      setPoi((previous) => ({ ...previous, color: draftColorHex }));
    }
  }, [draftColorHex]);

  React.useEffect(() => {
    if (selectedCity) setPoi((previous) => ({ ...previous, city: selectedCity }));
  }, [selectedCity]);

  const updatePoi = React.useCallback(
    <K extends keyof CreatePOIInput>(field: K, value: CreatePOIInput[K]) => {
      setPoi((previous) => ({ ...previous, [field]: value }));
    },
    [],
  );

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
    () => interventions.find((item) => item.intervention === selectedIntervention) ?? null,
    [interventions, selectedIntervention],
  );

  const isWaterArchetype = selectedArchetype === 'Evaporative / water';

  // Polygon tools are the only ones whose ring can self-intersect; point tools
  // are never blocked by the simple-polygon check below.
  const isPolygonTool = selectedTool?.kind === 'polygon' && !isWaterArchetype;
  const pointGeometry =
    pendingPlacedObject?.geometry?.kind === 'point' ? pendingPlacedObject.geometry : null;
  const hasPointCoordinates =
    pointGeometry !== null && (pointGeometry.longitude !== 0 || pointGeometry.latitude !== 0);

  // Keep the map's draft color in step with the (editable) polygon color.
  React.useEffect(() => {
    if (isPolygonTool && toolColor) onSetDraftColor(toolColor);
  }, [isPolygonTool, toolColor, onSetDraftColor]);

  React.useEffect(() => {
    if (!isDrawing || !isPolygonTool) return;
    updatePendingPlacedObject?.({
      geometry: { kind: 'polygon', ring: draftPoints },
    });
  }, [isDrawing, isPolygonTool, draftPoints, updatePendingPlacedObject]);

  React.useEffect(() => {
    if (!isPOIDraw) return;
    if (draftPoints.length === 0) {
      setPoi((previous) => ({ ...previous, polygon: '' }));
      return;
    }
    try {
      const polygonStr = polygonParseFromRingToComma(draftPoints);
      setPoi((previous) => ({ ...previous, polygon: polygonStr }));
    } catch {
      // ignore
    }
  }, [isPOIDraw, draftPoints]);

  React.useEffect(() => {
    if (!isDrawing && isPOIDraw) {
      setIsPOIDraw(false);
    }
  }, [isDrawing, isPOIDraw]);

  React.useEffect(() => {
    if (!selectedCity) {
      updatePendingPlacedObject?.({ market_code: undefined });
      return;
    }

    const marketCode = selectedCity.trim().toLowerCase().replace(/\s+/g, '_');
    updatePendingPlacedObject?.({ market_code: marketCode });
  }, [selectedCity, updatePendingPlacedObject]);

  // Stage a fresh pending object for the clicked intervention. Dates already
  // entered are carried across so switching interventions doesn't wipe them.
  const handleSelectIntervention = React.useCallback(
    (item: ToolboxItemDef) => {
      if (!citySelected || !selectedArchetype) return;
      setSelectedIntervention(item.intervention);
      
      setPendingPlacedObject?.({
        intervention: item.intervention,
        category: selectedArchetype,
        name: formatInterventionLabel(item.intervention),
        color: item.color,
        market_code: selectedCity ? selectedCity.trim().toLowerCase().replace(/\s+/g, '_') : undefined,
        params: { ...item.params },
        activeFrom: pendingPlacedObject?.activeFrom || '2020-01-01',
        activeTo: pendingPlacedObject?.activeTo || '2020-01-01',
        geometry:
          item.kind === 'polygon' && !isWaterArchetype
            ? { kind: 'polygon', ring: [] }
            : { kind: 'point', longitude: 0, latitude: 0 },
      });

    },
    [citySelected, selectedArchetype, isWaterArchetype, setPendingPlacedObject, pendingPlacedObject],
  );

const handleDrawIntervention = React.useCallback(
  (item: ToolboxItemDef) => {
    if (isWaterArchetype || item.kind !== 'polygon') {
      handleSelectIntervention(item);
      setIsPickingPoint?.(true);
      return;
    }

    onStartDrawing();               // enter draw mode on the map
    onSetDraftColor(item.color);    // match the draft outline to the tool color
    updatePendingPlacedObject?.({   // reset this tool's ring so it starts empty
      geometry: { kind: 'polygon', ring: [] },
    });
  },
  [handleSelectIntervention, isWaterArchetype, onStartDrawing, onSetDraftColor, updatePendingPlacedObject, setIsPickingPoint],
);

  const handleClearObject = React.useCallback(() => {
    placedObjectsControls?.clearPendingPlacedObject?.();
    onCancelDrawing();
    setSelectedIntervention(null);
  }, [placedObjectsControls, onCancelDrawing]);


  React.useEffect(() => {
    placedObjectsControls?.clearPendingPlacedObject?.();
    onCancelDrawing();
  }, [selectedArchetype])

  React.useEffect(() => {
    if (!commitSuccess) return;

    const timeoutId = window.setTimeout(() => setCommitSuccess(false), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [commitSuccess]);

  // Save gate for the selected intervention: a city, an intervention, both
  // dates, and — for polygons only — a color plus a valid (simple, 3+ point)
  // ring. Point interventions have no color/ring requirement.
  const canSaveTool =
    citySelected &&
    Boolean(selectedTool) &&
    (toolActiveFrom ?? '').trim() !== '' &&
    (toolActiveTo ?? '').trim() !== '' &&
    (isPolygonTool ? toolColor.trim() !== '' && pointCount >= 3 && draftIsSimple : true);

  const normalizedPoiPolygonWkt = normalizePolygonWkt(poi.polygon);
  const canCreateCorePoi =
    normalizedPoiPolygonWkt.length >= 10 &&
    poi.city.trim() !== '' &&
    poi.location_name.trim() !== '' &&
    poi.region.trim().length >= 2;

  const handleCreateCorePoi = React.useCallback(async () => {
    if (!canCreateCorePoi) return;

    try {
      await createPOI({ ...poi, polygon: normalizedPoiPolygonWkt });
      setCommitSuccess(true);
    } catch (error) {
      console.error('Failed to create new POI', error);
    }
  }, [
    canCreateCorePoi,
    poi,
    normalizedPoiPolygonWkt,
  ]);

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
    const base = {
      intervention: customName.trim().toLowerCase().replace(/\s+/g, '_'),
      Icon: TOOLBOX_ICONS[customIconName as keyof typeof TOOLBOX_ICONS],
      color: customColor,
      category: customCategory,
      kind: 'polygon' as const,
    };

    let payload: ToolboxItemDef;
    switch (customCategory) {
      case 'Vegetation':
        payload = {
          ...base,
          params: {
            coverPct: customParams.coverPct ?? 0,
            lai: customParams.lai ?? 0,
            irrigation: customParams.irrigation ?? 0,
          },
        };
        break;
      case 'High-albedo surface':
        payload = {
          ...base,
          params: {
            albedo: customParams.albedo ?? 0,
            coverage: customParams.coverage ?? 0,
            emissivity: customParams.emissivity ?? 0,
          },
        };
        break;
      case 'Shade structure':
        payload = {
          ...base,
          params: {
            opacity: customParams.opacity ?? 0,
            coverage: customParams.coverage ?? 0,
          },
        };
        break;
      case 'Evaporative / water':
        payload = {
          ...base,
          params: {
            flowRate: customParams.flowRate ?? 0,
            radius: customParams.radius ?? 0,
            activeFraction: customParams.activeFraction ?? 0,
          },
        };
        break;
      default:
        return;
    }

    await createNewUrbanIntervention(payload);

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
          onChange={(isoDate) => {
            setSelectedDate(isoDate);
            setBaselineSelectedDate?.(isoDate);
          }}
          availableDates={availableDates}
          disabled={!citySelected}
          variant="bare"
          style={{ width: '100%' }}
        />
        <div style={dividerStyle} />

        {/* --- Metric selector --- */}
        <div style={{ fontSize: 13, fontWeight: 700 }}>Metric</div>
        <select
          value={selectedMetricKey}
          onChange={(event) => onMetricChange(event.target.value)}
          disabled={!citySelected || metricOptions.length === 0}
          style={{
            ...fieldStyle,
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            color: '#e2e8f0',
            cursor: citySelected && metricOptions.length > 0 ? 'pointer' : 'not-allowed',
          }}
        >
          {metricOptions.map((metric) => (
            <option key={metric.value} value={metric.value}>
              {metric.label}
            </option>
          ))}
        </select>
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
                  setSelectedIntervention(null);
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
                      const isPoint = isWaterArchetype || item.kind === 'point';
                      const isSelected = selectedIntervention === item.intervention;
                      return (
                        <div
                          key={item.intervention}
                          draggable={isPoint && citySelected}
                          onDragStart={(e) => {
                            if (!isPoint || !citySelected) return;
                            e.dataTransfer.setData(TOOLBOX_DRAG_MIME, item.intervention);
                            e.dataTransfer.setData(
                              'application/x-toolbox-params',
                              JSON.stringify(item.params),
                            );
                            e.dataTransfer.effectAllowed = 'copy';
                            handleSelectIntervention(item);
                          }}
                          onClick={() => handleSelectIntervention(item)}
                          title={
                            isPoint
                              ? `Place ${formatInterventionLabel(item.intervention)}`
                              : `Draw ${formatInterventionLabel(item.intervention)}`
                          }
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
                            {formatInterventionLabel(item.intervention)}
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
                    onChange={handleToolStartDateChange}
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
                  <div style={{ fontSize: 12, color: '#cbd5e1' }}>Coordinates</div>
                  <div
                    style={{
                      maxHeight: 132,
                      overflowY: 'auto',
                      border: '1px solid rgba(148, 163, 184, 0.35)',
                      borderRadius: 6,
                      padding: '6px 8px',
                      fontFamily: 'Inter, sans-serif',
                      fontSize: 12,
                    }}
                  >
                    {!isPolygonTool ? (
                      hasPointCoordinates && pointGeometry ? (
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: 12,
                            color: '#cbd5e1',
                            padding: '1px 0',
                          }}
                        >
                          <span style={{ color: '#64748b' }}>Point</span>
                          <span>
                            {pointGeometry.latitude.toFixed(6)}, {pointGeometry.longitude.toFixed(6)}
                          </span>
                        </div>
                      ) : (
                        <div style={{ color: '#64748b' }}>No coordinate selected</div>
                      )
                    ) : draftPoints.length === 0 ? (
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
                    onClick={() => handleDrawIntervention(selectedTool)}
                    disabled={!citySelected}
                    style={{
                      ...toolbarButtonStyle,
                      backgroundColor: citySelected ? '#2563eb' : 'rgba(71, 85, 105, 0.6)',
                      color: '#f8fafc',
                      cursor: citySelected ? 'pointer' : 'not-allowed',
                    }}
                    title={!citySelected ? 'Select a city on the map first' : undefined}
                  >
                    <Pencil size={15} /> Draw Urban Intervention
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleDrawIntervention(selectedTool)}
                    disabled={!citySelected}
                    style={{
                      ...toolbarButtonStyle,
                      backgroundColor: citySelected ? '#2563eb' : 'rgba(71, 85, 105, 0.6)',
                      color: '#f8fafc',
                      cursor: citySelected ? 'pointer' : 'not-allowed',
                    }}
                    title={!citySelected ? 'Select a city on the map first' : undefined}
                  >
                    <MapPin size={15} /> Choose A Coordinate on Map
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
                    void placedObjectsControls?.commitPendingPlacedObject?.().then(() => {
                      setCommitSuccess(true);
                    });
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

                {commitSuccess && (
                  <div
                    role="status"
                    aria-live="polite"
                    style={{
                      position: 'fixed',
                      right: 20,
                      bottom: 20,
                      zIndex: 40,
                      padding: '10px 14px',
                      borderRadius: 8,
                      border: '1px solid rgba(74, 222, 128, 0.6)',
                      backgroundColor: 'rgba(20, 83, 45, 0.95)',
                      color: '#dcfce7',
                      boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    Urban intervention saved successfully.
                  </div>
                )}

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

            {/* Custom interventions are temporarily disabled. */}
            {false && (
              <>
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
            {customCategory !== '' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 12, color: '#cbd5e1' }}>Params</div>
                {ARCHETYPE_PARAMS[customCategory as CustomCategoryKey].map((paramKey) => {
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
          </>
        )}

        {displayToolbox && (
          <>
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

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
          Polygon coordinates
          <input
            type="text"
            value={poi.polygon}
            onChange={(e) => updatePoi('polygon', e.target.value)}
            placeholder="Enter coordinates comma-separated: -96.80 32.78, -96.79 32.79, ..."
            style={fieldStyle}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
          City
          <select value={poi.city} onChange={(e) => updatePoi('city', e.target.value)} style={fieldStyle}>
            <option value="">Select a US city</option>
            {cities.map((city) => <option key={city.name} value={city.name}>{city.name}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
          Location name
          <input type="text" value={poi.location_name} onChange={(e) => updatePoi('location_name', e.target.value)} style={fieldStyle} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
          Region
          <select value={poi.region} onChange={(e) => updatePoi('region', e.target.value)} style={fieldStyle}>
            <option value="">Select a state</option>
            {US_STATE_CODES.map((state) => <option key={state} value={state}>{state}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#cbd5e1' }}>
          <input type="checkbox" checked={poi.includes_parking_lot} onChange={(e) => updatePoi('includes_parking_lot', e.target.checked)} />
          Includes parking lot
        </label>
        <button
          type="button"
          onClick={() => setShowOptionalPoiFields((visible) => !visible)}
          style={{ ...toolbarButtonStyle, backgroundColor: 'rgba(30, 41, 59, 0.9)', color: '#e2e8f0' }}
        >
          {showOptionalPoiFields ? 'Hide optional POI fields' : 'Show optional POI fields'}
        </button>
        {showOptionalPoiFields && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Brands <input type="text" value={poi.brands?.join(', ') ?? ''} onChange={(e) => updatePoi('brands', e.target.value.split(',').map((value) => value.trim()).filter(Boolean))} placeholder="Comma-separated" style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Category tags <input type="text" value={poi.category_tags?.join(', ') ?? ''} onChange={(e) => updatePoi('category_tags', e.target.value.split(',').map((value) => value.trim()).filter(Boolean))} placeholder="Comma-separated" style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Domains <input type="text" value={poi.domains?.join(', ') ?? ''} onChange={(e) => updatePoi('domains', e.target.value.split(',').map((value) => value.trim()).filter(Boolean))} placeholder="Comma-separated" style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#cbd5e1' }}>
              <input type="checkbox" checked={poi.enclosed ?? false} onChange={(e) => updatePoi('enclosed', e.target.checked)} />
              Enclosed
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              NAICS code <input type="number" value={poi.naics_code ?? ''} onChange={(e) => updatePoi('naics_code', e.target.value === '' ? undefined : Number(e.target.value))} min={100000} max={999999} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              NAICS code 2022 <input type="number" value={poi.naics_code_2022 ?? ''} onChange={(e) => updatePoi('naics_code_2022', e.target.value === '' ? undefined : Number(e.target.value))} min={100000} max={999999} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Opened on <input type="date" value={poi.opened_on ?? ''} onChange={(e) => updatePoi('opened_on', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Open hours (JSON) <input type="text" value={poi.open_hours ? JSON.stringify(poi.open_hours) : ''} onChange={(e) => { try { updatePoi('open_hours', e.target.value ? JSON.parse(e.target.value) : undefined); } catch { /* Wait for valid JSON. */ } }} placeholder='{"Mon":[["9:00","17:00"]]}' style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Phone number <input type="tel" value={poi.phone_number ?? ''} onChange={(e) => updatePoi('phone_number', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Postal code <input type="text" value={poi.postal_code ?? ''} onChange={(e) => updatePoi('postal_code', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Street address <input type="text" value={poi.street_address ?? ''} onChange={(e) => updatePoi('street_address', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Sub-category <input type="text" value={poi.sub_category ?? ''} onChange={(e) => updatePoi('sub_category', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Top category <input type="text" value={poi.top_category ?? ''} onChange={(e) => updatePoi('top_category', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Website <input type="url" value={poi.website ?? ''} onChange={(e) => updatePoi('website', e.target.value || undefined)} style={fieldStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
              Area in square meters <input type="number" value={poi.wkt_area_sq_meters ?? ''} onChange={(e) => updatePoi('wkt_area_sq_meters', e.target.value === '' ? undefined : Number(e.target.value))} min={0} step="any" style={fieldStyle} />
            </label>
          </div>
        )}
        {!isDrawing || isPolygonTool ? (
          <>
            <button
              type="button"
              onClick={() => {
                setIsPOIDraw(true);
                onStartDrawing();
              }}
              disabled={!selectedCity || isPOIDraw}
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
          </>
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
              onClick={() => {
                setIsPOIDraw(false);
                onCancelDrawing();
              }}
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

        <button
          type="button"
          onClick={() => void handleCreateCorePoi()}
          disabled={!canCreateCorePoi}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: canCreateCorePoi ? '#16a34a' : 'rgba(71, 85, 105, 0.6)',
            color: '#f8fafc',
            cursor: canCreateCorePoi ? 'pointer' : 'not-allowed',
            opacity: canCreateCorePoi ? 1 : 0.6,
          }}
        >
          <Check size={15} /> Create New POI
        </button>

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
          </>
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