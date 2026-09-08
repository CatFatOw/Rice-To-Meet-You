import { ChevronDown, MapPin, Trash2 } from 'lucide-react';
import { useState } from 'react';
import SelectDate from './SelectDate';
import type { PlacedObject } from '../types/toolbox';
import { polygonCenter } from '../services/toolbox';

export interface ToolboxTableProps {
  placedObjects?: PlacedObject[];
  onPlacedObjectsChange?: (objects: PlacedObject[]) => void;
  availableDates?: string[];
  title?: string;
}

/** One-line summary of whatever geometry an intervention carries. */
function describeGeometry(geometry: unknown): string {
  if (!geometry) return '—';

  // Bare array of points — treat as a polygon ring.
  if (Array.isArray(geometry)) {
    return `polygon · ${geometry.length} pts`;
  }

  const g = geometry as Record<string, unknown>;

  // Discriminated union used across the app: { kind: 'point' | 'line' | 'polygon' }.
  if (typeof g.kind === 'string') {
    switch (g.kind) {
      case 'point':
        return typeof g.longitude === 'number' && typeof g.latitude === 'number'
          ? `point · ${(g.latitude as number).toFixed(4)}, ${(g.longitude as number).toFixed(4)}`
          : 'point';
      case 'polygon': {
        const ring = Array.isArray(g.ring) ? (g.ring as [number, number][]) : [];
        if (ring.length === 0) return 'polygon · 0 pts';
        const total = ring.reduce(
          (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
          { lng: 0, lat: 0 },
        );
        const centerLng = total.lng / ring.length;
        const centerLat = total.lat / ring.length;
        return `polygon · ${ring.length} pts · ${centerLat.toFixed(4)}, ${centerLng.toFixed(4)}`;
      }
      case 'line': {
        const coords = Array.isArray(g.coordinates) ? g.coordinates : [];
        return `line · ${coords.length} pts`;
      }
      default:
        return g.kind;
    }
  }

  // --- Legacy / loose fallbacks (kept so non-union shapes still describe) ---
  if (typeof g.longitude === 'number' && typeof g.latitude === 'number') {
    return `point · ${(g.latitude as number).toFixed(4)}, ${(g.longitude as number).toFixed(4)}`;
  }

  if (Array.isArray(g.coordinates)) {
    const kind = typeof g.type === 'string' ? g.type.toLowerCase() : 'shape';
    return `${kind} · ${g.coordinates.length} pts`;
  }

  if (typeof g.radiusMeters === 'number') {
    return `circle · r=${g.radiusMeters}m`;
  }

  return 'custom';
}

/** Format a lng/lat pair (from polygonCenter or a point) as a readable string. */
function formatLngLat(value: unknown): string {
  if (Array.isArray(value) && value.length >= 2) {
    const [lng, lat] = value as [number, number];
    return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  }
  if (value && typeof value === 'object') {
    const v = value as Record<string, unknown>;
    if (typeof v.latitude === 'number' && typeof v.longitude === 'number') {
      return `${v.latitude.toFixed(4)}, ${v.longitude.toFixed(4)}`;
    }
    if (typeof v.lat === 'number' && typeof v.lng === 'number') {
      return `${v.lat.toFixed(4)}, ${v.lng.toFixed(4)}`;
    }
  }
  return String(value ?? '—');
}

/**
 * Destination is the point the intervention acts on:
 * the centroid for a polygon, or the coordinates for a point.
 */
function describeDestination(geometry: unknown): string {
  if (!geometry || typeof geometry !== 'object') return '—';
  const g = geometry as Record<string, unknown>;

  if (g.kind === 'polygon' && Array.isArray(g.ring)) {
    return formatLngLat(polygonCenter(g.ring as [number, number][]));
  }

  if (g.kind === 'point' && typeof g.longitude === 'number' && typeof g.latitude === 'number') {
    return `${(g.latitude as number).toFixed(4)}, ${(g.longitude as number).toFixed(4)}`;
  }

  return '—';
}

/** Params differ per intervention type, so edit them generically by key. */
function paramEntries(params: unknown): [string, unknown][] {
  if (!params || typeof params !== 'object') return [];
  return Object.entries(params as Record<string, unknown>);
}

function humanizeKey(key: string): string {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (c) => c.toUpperCase())
    .trim();
}

/**
 * Lists every intervention currently on the map and lets the planner retune it:
 * name, params, and the window it's active for. Geometry and destination are
 * read-only here — geometry gets edited on the map itself.
 */
export default function ToolboxTable({
  placedObjects = [],
  onPlacedObjectsChange,
  availableDates,
  title = 'Tools on map'
}: ToolboxTableProps) {
  const readOnly = !onPlacedObjectsChange;
  const [isOpen, setIsOpen] = useState(true);

  const patchObject = (id: string, patch: Partial<PlacedObject>) => {
    onPlacedObjectsChange?.(
      placedObjects.map((obj) => (obj.id === id ? { ...obj, ...patch } : obj)),
    );
  };

  const patchParam = (id: string, key: string, value: unknown) => {
    onPlacedObjectsChange?.(
      placedObjects.map((obj) =>
        obj.id === id
          ? { ...obj, params: { ...(obj.params as object), [key]: value } }
          : obj,
      ) as PlacedObject[],
    );
  };

  return (
    <div className="shrink-0">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className="mb-3 flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
          <ChevronDown
            size={14}
            className={`transition-transform ${isOpen ? '' : '-rotate-90'}`}
          />
          {title}
        </span>
        <span className="text-xs text-[var(--text-muted)]">
          {placedObjects.length} placed
        </span>
      </button>

      {isOpen && (
      <div className="max-h-64 overflow-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        {placedObjects.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-5 py-8 text-center">
            <MapPin size={20} className="text-[var(--text-muted)]" />
            <p className="text-sm text-[var(--text-muted)]">
              Drag a tool from the map toolbox to start building a scenario.
            </p>
          </div>
        ) : (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-muted)]">
                <th className="px-5 py-3 font-semibold">Id</th>
                <th className="px-5 py-3 font-semibold">Name</th>
                <th className="px-5 py-3 font-semibold">Type</th>
                <th className="px-5 py-3 font-semibold">Destination</th>
                <th className="px-5 py-3 font-semibold">Geometry</th>
                <th className="px-5 py-3 font-semibold">Params</th>
                <th className="px-5 py-3 font-semibold">Active from</th>
                <th className="px-5 py-3 font-semibold">Active until</th>
                <th className="px-5 py-3 font-semibold">Actions</th>
              </tr>
            </thead>

            <tbody>
              {placedObjects.map((obj) => (
                <tr
                  key={obj.id}
                  className="border-b border-[var(--border-subtle)] align-top transition-colors last:border-b-0 hover:bg-white/4"
                >
                  {/* Id: stable identifier, read-only */}
                  <td className="px-5 py-4 text-sm font-mono text-[var(--text-muted)]">
                    {obj.id}
                  </td>

                  {/* Name: the planner's own name for it */}
                  <td className="px-5 py-4">
                    <input
                      value={obj.name ?? ''}
                      placeholder={obj.type}
                      disabled={readOnly}
                      onChange={(e) =>
                        patchObject(obj.id, { name: e.target.value })
                      }
                      className="w-40 rounded-md border border-[var(--border-strong)] bg-[var(--surface-muted)] px-2 py-1 text-sm font-medium text-[var(--text-primary)] outline-none transition-colors focus:border-sky-400 disabled:opacity-60"
                    />
                  </td>

                  {/* Type: fixed intervention type */}
                  <td className="px-5 py-4 text-sm uppercase tracking-wide text-[var(--text-muted)]">
                    {obj.type}
                  </td>

                  {/* Destination: centroid for polygons, coords for points */}
                  <td className="px-5 py-4 text-sm text-[var(--text-secondary)]">
                    {describeDestination(obj.geometry)}
                  </td>

                  {/* Geometry: edited on the map, shown here for orientation */}
                  <td className="px-5 py-4 text-sm text-[var(--text-secondary)]">
                    {describeGeometry(obj.geometry)}
                  </td>

                  {/* Params: shape varies by type, so render one labelled input per key */}
                  <td className="px-5 py-4">
                    {paramEntries(obj.params).length === 0 ? (
                      <span className="text-sm text-[var(--text-muted)]">—</span>
                    ) : (
                      <div className="flex flex-col gap-1.5">
                        {paramEntries(obj.params).map(([key, value]) => (
                          <label
                            key={key}
                            className="flex items-center gap-2 text-xs text-[var(--text-secondary)]"
                          >
                            <span className="w-28 shrink-0">
                              {humanizeKey(key)}
                            </span>

                            {typeof value === 'boolean' ? (
                              <input
                                type="checkbox"
                                checked={value}
                                disabled={readOnly}
                                onChange={(e) =>
                                  patchParam(obj.id, key, e.target.checked)
                                }
                                className="h-4 w-4 accent-sky-400"
                              />
                            ) : (
                              <input
                                type={typeof value === 'number' ? 'number' : 'text'}
                                value={String(value ?? '')}
                                disabled={readOnly}
                                onChange={(e) =>
                                  patchParam(
                                    obj.id,
                                    key,
                                    typeof value === 'number'
                                      ? Number(e.target.value)
                                      : e.target.value,
                                  )
                                }
                                className="w-24 rounded-md border border-[var(--border-strong)] bg-[var(--surface-muted)] px-2 py-1 text-sm text-[var(--text-primary)] outline-none transition-colors focus:border-sky-400 disabled:opacity-60"
                              />
                            )}
                          </label>
                        ))}
                      </div>
                    )}
                  </td>

                  <td className="px-5 py-4">
                    <SelectDate
                      label="Active from"
                      value={obj.activeFrom ?? null}
                      onChange={(isoDate) =>
                        patchObject(obj.id, { activeFrom: isoDate })
                      }
                      availableDates={availableDates}
                      variant="bare"
                      className="w-36"
                    />
                  </td>

                  <td className="px-5 py-4">
                    <SelectDate
                      label="Active until"
                      value={obj.activeTo ?? null}
                      onChange={(isoDate) =>
                        patchObject(obj.id, { activeTo: isoDate })
                      }
                      availableDates={availableDates}
                      variant="bare"
                      className="w-36"
                    />
                  </td>

                  {/* Actions: delete icon — no-op for now */}
                  <td className="px-5 py-4">
                    <button
                      type="button"
                      disabled={readOnly}
                      onClick={() => {
                        /* TODO: wire up delete */
                      }}
                      aria-label={`Remove ${obj.name ?? obj.type}`}
                      className="text-[var(--text-muted)] transition-colors hover:text-red-400 disabled:opacity-40"
                    >
                      <Trash2 size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      )}
    </div>
  );
}