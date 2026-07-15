import { useCallback, useEffect, useState } from 'react';
import type React from 'react';
import type maplibregl from 'maplibre-gl';
import { TOOLBOX_DRAG_MIME } from '../utils/toolbox';
import type { Geometry } from '../types/simulation';

export interface BasePlacedObject {
  id: string;
  type: string;
  name: string;
  color?: string;
  geometry: Geometry;
}

export interface BuildPlacedObjectArgs {
  id: string;
  type: string;
  name: string;
  color?: string;
  geometry: Geometry;
  previousCount: number;
}

export interface UsePlacedObjectsOptions<TPlacedObject extends BasePlacedObject> {
  initialObjects?: TPlacedObject[];
  onChange?: (objects: TPlacedObject[]) => void;
  mapRef?: React.MutableRefObject<maplibregl.Map | null>;
  mapContainerRef?: React.RefObject<HTMLDivElement | null>;
  buildPlacedObject?: (args: BuildPlacedObjectArgs) => TPlacedObject;
  dragMime?: string;
}

export interface UsePlacedObjectsReturn<TPlacedObject extends BasePlacedObject> {
  placedObjects: TPlacedObject[];
  setPlacedObjects: React.Dispatch<React.SetStateAction<TPlacedObject[]>>;
  addPlacedObject: (object: TPlacedObject) => void;
  removePlacedObject: (id: string) => void;
  clearPlacedObjects: () => void;
  patchPlacedObject: (id: string, patch: Partial<TPlacedObject>) => void;
  handleObjectDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  handleObjectDrop: (e: React.DragEvent<HTMLDivElement>) => void;
}

function defaultBuildPlacedObject(args: BuildPlacedObjectArgs): BasePlacedObject {
  return {
    id: args.id,
    type: args.type,
    name: args.name,
    color: args.color,
    geometry: args.geometry,
  };
}

/**
 * Owns the map toolbox object lifecycle:
 * - drop from HTML5 drag payload -> lng/lat placement
 * - add / patch / remove / clear operations
 * - optional upstream sync callback when objects change
 */
export function usePlacedObjects<TPlacedObject extends BasePlacedObject = BasePlacedObject>({
  initialObjects = [],
  onChange,
  mapRef,
  mapContainerRef,
  buildPlacedObject = defaultBuildPlacedObject as (args: BuildPlacedObjectArgs) => TPlacedObject,
  dragMime = TOOLBOX_DRAG_MIME,
}: UsePlacedObjectsOptions<TPlacedObject> = {}): UsePlacedObjectsReturn<TPlacedObject> {
  const [placedObjects, setPlacedObjects] = useState<TPlacedObject[]>(initialObjects);

  console.log(placedObjects)

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

  const patchPlacedObject = useCallback((id: string, patch: Partial<TPlacedObject>) => {
    setPlacedObjects((prev) =>
      prev.map((obj) => (obj.id === id ? { ...obj, ...patch } : obj)),
    );
  }, []);

  const handleObjectDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (e.dataTransfer.types.includes(dragMime)) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
      }
    },
    [dragMime],
  );

  const handleObjectDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      const type = e.dataTransfer.getData(dragMime);
      if (!type) return;
      e.preventDefault();

      const map = mapRef?.current;
      const container = mapContainerRef?.current;
      if (!map || !container) return;

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const { lng, lat } = map.unproject([x, y]);

      setPlacedObjects((prev) => {
        const next = buildPlacedObject({
          id: `placed-${Date.now()}-${prev.length + 1}`,
          type,
          name: type,
          // Adjust this line if your Geometry type isn't GeoJSON-shaped:
          geometry: { kind: 'point', longitude: lng, latitude: lat } as Geometry,
          previousCount: prev.length,
        });
        return [...prev, next];
      });
    },
    [buildPlacedObject, dragMime, mapRef, mapContainerRef],
  );

  return {
    placedObjects,
    setPlacedObjects,
    addPlacedObject,
    removePlacedObject,
    clearPlacedObjects,
    patchPlacedObject,
    handleObjectDragOver,
    handleObjectDrop,
  };
}

export default usePlacedObjects;