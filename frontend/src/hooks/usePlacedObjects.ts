import { useCallback, useEffect, useState } from 'react';
import type React from 'react';
import type maplibregl from 'maplibre-gl';
import { TOOLBOX_DRAG_MIME } from '../services/toolbox';
import type { Geometry } from '../types/simulation';
import { addPlacedObjects } from '../api/tool';
import { TOOLBOX_ITEMS } from '../data/toolboxItems';
import type { ArchetypeType, ToolboxItemDef } from '../types/toolbox';

// Design params carried by a placed object (albedo, flowRate, coverPct, ...).
// Kept as a numeric record here so the hook stays archetype-agnostic; concrete
// placed-object types can narrow this to a per-archetype shape by extending
// BasePlacedObject (see note at bottom of file).
export type PlacedObjectParams = Record<string, number>;

// The archetype buckets a placed object can belong to. Same four categories the
// Toolbox / TOOLBOX_ITEMS use, so an object's category lines up 1:1 with the
// archetype it was placed from.
export type PlacedObjectCategory =
  | 'Vegetation'
  | 'High-albedo surface'
  | 'Shade structure'
  | 'Evaporative / water';

// Canonical iteration order and a stable list of every category. Used to build
// empty collections and to sweep all buckets during id-based lookups.
export const PLACED_OBJECT_CATEGORIES: PlacedObjectCategory[] = [
  'Vegetation',
  'High-albedo surface',
  'Shade structure',
  'Evaporative / water',
];

export interface BasePlacedObject {
  // Only COMMITTED objects carry an id. It's assigned in commitPendingPlacedObject,
  // never while the object is still pending/staged.
  id: string;
  // Toolbox-facing type identifier used by the simulation/rendering path.
  type?: string;
  // Category is optional so the hook can carry both toolbox objects and mock
  // API objects without forcing every caller to populate it.
  category?: string;
  name?: string;
  color?: string;
  market_code?: string;
  geometry: Geometry;
  params?: PlacedObjectParams;
  // Active window as ISO date strings (e.g. '2025-07-01'). Optional because an
  // object is staged before the user picks its window; the Toolbox fills these
  // via updatePendingPlacedObject before commit.
  activeFrom?: string;
  activeTo?: string;
}

// The staged/pending shape: a BasePlacedObject (which already includes
// `category`) with the id omitted, since the id doesn't exist until commit.
// Stays generic so a narrowed placed-object type keeps its extra fields while
// still dropping only the id.
export type PendingPlacedObject<TPlacedObject extends BasePlacedObject> = Omit<
  TPlacedObject,
  'id'
>;

// Placed objects grouped by archetype category: each category maps to the list
// of committed objects that belong to it. This is the shape of `placedObjects`.
export type BasePlacedObjectCategorized<
  TPlacedObject extends BasePlacedObject = BasePlacedObject,
> = Record<PlacedObjectCategory, TPlacedObject[]>;

// Convenience for consumers that just need one flat list (e.g. rendering every
// object on the map) out of the categorized collection.
export function flattenCategorized<TPlacedObject extends BasePlacedObject>(
  categorized: BasePlacedObjectCategorized<TPlacedObject>,
): TPlacedObject[] {
  return PLACED_OBJECT_CATEGORIES.flatMap((category) => categorized[category]);
}

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

  // Remove is targeted by id.
  removePlacedObject: (id: string) => void;
  // Empties the list at once.
  clearPlacedObjects: () => void;
  // Patch is targeted by id.
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

function isArchetypeType(value: unknown): value is ArchetypeType {
  return (
    value === 'Vegetation' ||
    value === 'High-albedo surface' ||
    value === 'Shade structure' ||
    value === 'Evaporative / water'
  );
}



/**
 * Owns the map toolbox object lifecycle:
 * - a single pending (staged) object, seeded by the Toolbox on drag start
 * - dragover / drop only REPOSITION that staged object (they never create one)
 * - patch / remove / clear operations, including per-param patching
 * - optional upstream sync callback when objects change
 *
 * `placedObjects` is a flat list of committed objects. The only path that
 * adds a committed object is commitPendingPlacedObject (there is no
 * free-standing add helper); remove/patch target objects by id.
 *
 * The pending object is id-less (PendingPlacedObject); the id is minted in
 * commitPendingPlacedObject when the object becomes a real placed object.
 *
 * Active window (activeFrom / activeTo) are plain top-level fields, so they're
 * set/edited through updatePendingPlacedObject / patchPlacedObject — no
 * dedicated helper needed (unlike the nested params).
 */
export function usePlacedObjects<TPlacedObject extends BasePlacedObject = BasePlacedObject>({
  initialObjects,
  onChange,
  mapRef,
  mapContainerRef,
  dragMime = TOOLBOX_DRAG_MIME,
}: UsePlacedObjectsOptions<TPlacedObject> = {}): UsePlacedObjectsReturn<TPlacedObject> {
  const [placedObjects, setPlacedObjects] = useState<TPlacedObject[]>(() => initialObjects ?? []);
  const [pendingPlacedObject, setPendingPlacedObject] =
    useState<PendingPlacedObject<TPlacedObject> | null>(null);

  useEffect(() => {
    console.log('pendingPlacedObject changed:', pendingPlacedObject);
  }, [pendingPlacedObject]);

  useEffect(() => {
    onChange?.(placedObjects);
  }, [onChange, placedObjects]);

 



  // Drop the object from the flat list by id.
  const removePlacedObject = useCallback((id: string) => {
    setPlacedObjects((prev) => prev.filter((obj) => obj.id !== id));
  }, []);

  // Empty the list in one shot.
  const clearPlacedObjects = useCallback(() => {
    setPlacedObjects([]);
  }, []);


  // Shallow field patch on a COMMITTED object located by id.
  const patchPlacedObject = useCallback((id: string, patch: Partial<TPlacedObject>) => {
    setPlacedObjects((prev) => prev.map((obj) => (obj.id === id ? { ...obj, ...patch } : obj)));
  }, []);

  // Merge a partial into a committed object's params, preserving untouched keys.
  const patchPlacedObjectParams = useCallback((id: string, paramsPatch: Partial<PlacedObjectParams>) => {
    setPlacedObjects((prev) =>
      prev.map((obj) =>
        obj.id === id
          ? ({ ...obj, params: { ...(obj.params ?? {}), ...paramsPatch } } as TPlacedObject)
          : obj,
      ),
    );
  }, []);

  // Merge a partial into the current pending object. No-op if nothing is staged.
  // Cannot touch id (it's not part of the pending shape). This is how the
  // Toolbox writes activeFrom / activeTo (and name/color/category) before commit.
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

  // Mint the id, persist, drop the now-complete object into the flat list,
  // and clear the pending slot. Reads the latest pending value through the
  // functional setter so it doesn't need pending in its deps. This is the ONLY
  // way a committed object enters placedObjects.
const commitPendingPlacedObject = useCallback(async () => {
  console.groupCollapsed("[commitPendingPlacedObject] Called");

  try {
    console.log("Pending object:", pendingPlacedObject);

    const toCommit = pendingPlacedObject;

    if (!toCommit) {
      console.warn("Commit stopped: pendingPlacedObject is null or undefined.");
      return;
    }

    const committed = {
      ...toCommit,
      id: makePlacedId(),
    } as TPlacedObject;

    console.log("Committed object created:", committed);

    const pendingMeta = toCommit as {
      intervention?: string;
      type?: string;
      category?: string;
      color?: string;
      market_code?: string;
      geometry?: Geometry;
    };

    console.log("Extracted metadata:", pendingMeta);

    const interventionKey =
      pendingMeta.intervention ?? pendingMeta.type;

    console.log("Resolved intervention key:", interventionKey);
    console.log(
      "Is valid archetype category:",
      isArchetypeType(pendingMeta.category),
    );

    if (!interventionKey) {
      console.warn(
        "addPlacedObjects skipped: no intervention or type was provided.",
      );
    } else if (!isArchetypeType(pendingMeta.category)) {
      console.warn(
        "addPlacedObjects skipped: invalid archetype category.",
        pendingMeta.category,
      );
    } else {
      console.log(
        "Available toolbox items:",
        TOOLBOX_ITEMS[pendingMeta.category],
      );

      const baseItem = TOOLBOX_ITEMS[pendingMeta.category].find(
        (item) => item.intervention === interventionKey,
      );

      console.log("Matching base toolbox item:", baseItem);

      if (!baseItem) {
        console.warn(
          "addPlacedObjects skipped: no matching toolbox item.",
          {
            category: pendingMeta.category,
            interventionKey,
          },
        );
      } else {
        const payload: ToolboxItemDef = {
          ...baseItem,
          color: pendingMeta.color ?? baseItem.color,
          market_code: pendingMeta.market_code,
          geometry: pendingMeta.geometry,
          params: toCommit.params ?? baseItem.params,
          activeFrom: toCommit.activeFrom,
          activeTo: toCommit.activeTo,
          kind:
            pendingMeta.geometry?.kind === "point"
              ? "point"
              : "polygon",
        };

        console.log("Calling addPlacedObjects with payload:", payload);

        await addPlacedObjects(payload);

        console.log("addPlacedObjects completed successfully.");
      }
    }

    setPlacedObjects((prev) => {
      const updated = [...prev, committed];

      console.log("Previous placed objects:", prev);
      console.log("Updated placed objects:", updated);

      return updated;
    });

    setPendingPlacedObject(null);
    console.log("Pending placed object cleared.");
  } catch (error) {
    console.error(
      "[commitPendingPlacedObject] Failed to commit object:",
      error,
    );
    throw error;
  } finally {
    console.groupEnd();
  }
}, [pendingPlacedObject, addPlacedObjects]);

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
      // category, and params seeded on drag start are preserved. No-op if
      // nothing staged.
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
    removePlacedObject,
    clearPlacedObjects,
    patchPlacedObject,
    patchPlacedObjectParams,
    handleObjectDragOver,
    handleObjectDrop,
  };
}

export default usePlacedObjects;