import { useCallback, useEffect, useState } from 'react';
import type React from 'react';
import type maplibregl from 'maplibre-gl';
import { TOOLBOX_DRAG_MIME } from '../services/toolbox';
import type { Geometry } from '../types/simulation';

// Design params carried by a placed object (albedo, flowRate, coverPct, ...).
// Kept as a numeric record here so the hook stays archetype-agnostic; concrete
// placed-object types can narrow this to a per-archetype shape by extending
// BasePlacedObject (see note at bottom of file).
export type PlacedObjectParams = Record<string, number>;

export interface BasePlacedObject {
  // Only COMMITTED objects carry an id. It's assigned in commitPendingPlacedObject,
  // never while the object is still pending/staged.
  id: string;
  type: string;
  name: string;
  color?: string;
  geometry: Geometry;
  params?: PlacedObjectParams;
  // Active window as ISO date strings (e.g. '2025-07-01'). Optional because an
  // object is staged before the user picks its window; the Toolbox fills these
  // via updatePendingPlacedObject before commit.
  activeFrom?: string;
  activeTo?: string;
}

// The staged/pending shape: everything a placed object has EXCEPT the id, which
// doesn't exist until commit. The pending slot and its editors use this type.
export type PendingPlacedObject<TPlacedObject extends BasePlacedObject> = Omit<
  TPlacedObject,
  'id'
>;

export interface UsePlacedObjectsOptions<TPlacedObject extends BasePlacedObject> {
  initialObjects?: TPlacedObject[];
  onChange?: (objects: TPlacedObject[]) => void;
  mapRef?: React.MutableRefObject<maplibregl.Map | null>;
  mapContainerRef?: React.RefObject<HTMLDivElement | null>;
  dragMime?: string;
}

export interface UsePlacedObjectsReturn<TPlacedObject extends BasePlacedObject> {
  placedObjects: TPlacedObject[];
  setPlacedObjects: React.Dispatch<React.SetStateAction<TPlacedObject[]>>;
  pendingPlacedObject: PendingPlacedObject<TPlacedObject> | null;
  setPendingPlacedObject: React.Dispatch<
    React.SetStateAction<PendingPlacedObject<TPlacedObject> | null>
  >;
  updatePendingPlacedObject: (patch: Partial<PendingPlacedObject<TPlacedObject>>) => void;
  updatePendingPlacedObjectParams: (paramsPatch: Partial<PlacedObjectParams>) => void;
  commitPendingPlacedObject: () => Promise<void>;
  clearPendingPlacedObject: () => void;
  addPlacedObject: (object: TPlacedObject) => void;
  removePlacedObject: (id: string) => void;
  clearPlacedObjects: () => void;
  patchPlacedObject: (id: string, patch: Partial<TPlacedObject>) => void;
  patchPlacedObjectParams: (id: string, paramsPatch: Partial<PlacedObjectParams>) => void;
  handleObjectDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  handleObjectDrop: (e: React.DragEvent<HTMLDivElement>) => void;
}

// Generates the id assigned to a placed object at commit time. Unique enough
// for client-side placement; swap for a server-issued id if the API returns one.
function makePlacedId(): string {
  return `placed-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// Stubbed persistence call. Swap the body for a real fetch when the endpoint
// exists; the signature (object in, Promise out) is what callers rely on.
async function savePlacedObject<T extends BasePlacedObject>(_object: T): Promise<void> {
  // no-op API — resolves immediately
}

/**
 * Owns the map toolbox object lifecycle:
 * - a single pending (staged) object, seeded by the Toolbox on drag start
 * - dragover / drop only REPOSITION that staged object (they never create one)
 * - add / patch / remove / clear operations, including per-param patching
 * - optional upstream sync callback when objects change
 *
 * The pending object is id-less (PendingPlacedObject); the id is minted in
 * commitPendingPlacedObject when the object becomes a real placed object.
 *
 * Active window (activeFrom / activeTo) are plain top-level fields, so they're
 * set/edited through updatePendingPlacedObject / patchPlacedObject — no
 * dedicated helper needed (unlike the nested params).
 */
export function usePlacedObjects<TPlacedObject extends BasePlacedObject = BasePlacedObject>({
  initialObjects = [],
  onChange,
  mapRef,
  mapContainerRef,
  dragMime = TOOLBOX_DRAG_MIME,
}: UsePlacedObjectsOptions<TPlacedObject> = {}): UsePlacedObjectsReturn<TPlacedObject> {
  const [placedObjects, setPlacedObjects] = useState<TPlacedObject[]>(initialObjects);
  const [pendingPlacedObject, setPendingPlacedObject] =
    useState<PendingPlacedObject<TPlacedObject> | null>(null);

  
  console.log(pendingPlacedObject)
  useEffect(() => {
    onChange?.(placedObjects);
  }, [onChange, placedObjects]);

  const addPlacedObject = useCallback((object: TPlacedObject) => {
    setPlacedObjects((prev) => [...prev, object]);
  }, []);

  const removePlacedObject = useCallback((id: string) => {
    setPlacedObjects((prev) => prev.filter((obj) => obj.id !== id));
  }, []);

  const clearPlacedObjects = useCallback(() => {
    setPlacedObjects([]);
  }, []);

  // Shallow field patch on a COMMITTED object (keyed by id). Good for flat
  // fields including activeFrom / activeTo. NOTE: passing { params } here
  // REPLACES the whole params object — use patchPlacedObjectParams instead.
  const patchPlacedObject = useCallback((id: string, patch: Partial<TPlacedObject>) => {
    setPlacedObjects((prev) =>
      prev.map((obj) => (obj.id === id ? { ...obj, ...patch } : obj)),
    );
  }, []);

  // Merge a partial into a committed object's params, preserving untouched keys.
  // The cast is safe: we overlay a partial onto the object's existing full
  // params, so every required key is still present at runtime.
  const patchPlacedObjectParams = useCallback(
    (id: string, paramsPatch: Partial<PlacedObjectParams>) => {
      setPlacedObjects((prev) =>
        prev.map((obj) =>
          obj.id === id
            ? ({ ...obj, params: { ...(obj.params ?? {}), ...paramsPatch } } as TPlacedObject)
            : obj,
        ),
      );
    },
    [],
  );

  // Merge a partial into the current pending object. No-op if nothing is staged.
  // Cannot touch id (it's not part of the pending shape). This is how the
  // Toolbox writes activeFrom / activeTo (and name/color) before committing.
  const updatePendingPlacedObject = useCallback(
    (patch: Partial<PendingPlacedObject<TPlacedObject>>) => {
      setPendingPlacedObject((pending) =>
        pending ? { ...pending, ...patch } : pending,
      );
    },
    [],
  );

  // Same, but scoped to params so a single slider edit doesn't drop siblings.
  const updatePendingPlacedObjectParams = useCallback(
    (paramsPatch: Partial<PlacedObjectParams>) => {
      setPendingPlacedObject((pending) =>
        pending
          ? ({
              ...pending,
              params: { ...(pending.params ?? {}), ...paramsPatch },
            } as PendingPlacedObject<TPlacedObject>)
          : pending,
      );
    },
    [],
  );

  // Mint the id, persist, move the now-complete object into placedObjects, and
  // clear the pending slot. Reads the latest pending value through the
  // functional setter so it doesn't need pending in its deps.
  const commitPendingPlacedObject = useCallback(async () => {
    // Capture the current pending object without a stale closure.
    let toCommit: PendingPlacedObject<TPlacedObject> | null = null;
    setPendingPlacedObject((pending) => {
      toCommit = pending;
      return pending;
    });

    if (!toCommit) return;

    // id is added HERE — this is the moment a pending object becomes a real one.
    const committed = {
      ...(toCommit as PendingPlacedObject<TPlacedObject>),
      id: makePlacedId(),
    } as TPlacedObject;

    await savePlacedObject(committed);

    setPlacedObjects((prev) => [...prev, committed]);
    setPendingPlacedObject(null);
  }, []);

  // Discard the staged object without persisting. Cancel counterpart to commit.
  const clearPendingPlacedObject = useCallback(() => {
    setPendingPlacedObject(null);
  }, []);

  const handleObjectDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (!e.dataTransfer.types.includes(dragMime)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';

      const map = mapRef?.current;
      const container = mapContainerRef?.current;
      if (!map || !container) return;

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const { lng, lat } = map.unproject([x, y]);

      // Move the staged object to follow the cursor. Only repositions an object
      // that already exists (seeded by the Toolbox on drag start).
      setPendingPlacedObject((pending) =>
        pending
          ? {
              ...pending,
              geometry: { kind: 'point', longitude: lng, latitude: lat } as Geometry,
            }
          : pending,
      );
    },
    [dragMime, mapRef, mapContainerRef],
  );

  const handleObjectDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (!e.dataTransfer.types.includes(dragMime)) return;
      e.preventDefault();

      const map = mapRef?.current;
      const container = mapContainerRef?.current;
      if (!map || !container) return;

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const { lng, lat } = map.unproject([x, y]);

      // Like dragover, drop ONLY updates the already-staged pending object with
      // its final position — it never rebuilds/creates one, so the name, color,
      // and params seeded on drag start are preserved. No-op if nothing staged.
      setPendingPlacedObject((pending) =>
        pending
          ? {
              ...pending,
              geometry: { kind: 'point', longitude: lng, latitude: lat } as Geometry,
            }
          : pending,
      );
    },
    [dragMime, mapRef, mapContainerRef],
  );

  return {
    placedObjects,
    setPlacedObjects,
    pendingPlacedObject,
    setPendingPlacedObject,
    updatePendingPlacedObject,
    updatePendingPlacedObjectParams,
    commitPendingPlacedObject,
    clearPendingPlacedObject,
    addPlacedObject,
    removePlacedObject,
    clearPlacedObjects,
    patchPlacedObject,
    patchPlacedObjectParams,
    handleObjectDragOver,
    handleObjectDrop,
  };
}

export default usePlacedObjects;