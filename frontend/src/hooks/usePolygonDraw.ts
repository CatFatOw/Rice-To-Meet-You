// hooks/usePolygonDraw.ts
import { useState, useCallback, useMemo } from 'react';

export type Ring = [number, number][];

export function usePolygonDraw(minPoints = 3, initialColor = '#22c55e') {
  const [isDrawing, setIsDrawing] = useState(false);
  const [draftPoints, setDraftPoints] = useState<Ring>([]);
  const [draftColor, setDraftColor] = useState<string>(initialColor);

  const startDrawing = useCallback(() => {
    setDraftPoints([]);
    setIsDrawing(true);
  }, []);

  const addDraftPoint = useCallback((lng: number, lat: number) => {
    setDraftPoints((prev) => [...prev, [lng, lat]]);
  }, []);

  const undoDraftPoint = useCallback(
    () => setDraftPoints((prev) => prev.slice(0, -1)),
    [],
  );

  const cancelDrawing = useCallback(() => {
    setDraftPoints([]);
    setIsDrawing(false);
  }, []);

  // Hands the finished ring back; the caller decides what to build from it.
  const commitDrawing = useCallback((): Ring | null => {
    if (draftPoints.length < minPoints) return null;
    setDraftPoints([]);
    setIsDrawing(false);
    return draftPoints;
  }, [draftPoints, minPoints]);

  const canCommitDrawing = draftPoints.length >= minPoints;

  return useMemo(
    () => ({
      isDrawing,
      setIsDrawing,
      draftPoints,
      setDraftPoints,
      draftColor,
      setDraftColor,
      startDrawing,
      addDraftPoint,
      undoDraftPoint,
      cancelDrawing,
      commitDrawing,
      canCommitDrawing,
    }),
    [
      isDrawing,
      draftPoints,
      draftColor,
      startDrawing,
      addDraftPoint,
      undoDraftPoint,
      cancelDrawing,
      commitDrawing,
      canCommitDrawing,
    ],
  );
}

export type PolygonDraw = ReturnType<typeof usePolygonDraw>;