
import type { Geometry } from './simulation';

// ../types/toolbox
export interface VegetationParams   { coverPct: number; lai: number; irrigation: number }
export interface HighAlbedoParams   { albedo: number; coverage: number; emissivity: number }
export interface ShadeParams        { opacity: number; coverage: number }
export interface EvaporativeParams  { flowRate: number; radius: number; activeFraction: number }

type ToolboxItemBase = {
  id: string;
  type: string;
  label: string;
  color: string;
  kind: 'polygon' | 'point';
  Icon: React.ComponentType<{ size?: number | string; color?: string }>;
};

export type ToolboxItemDef =
  | (ToolboxItemBase & { type: string; params: VegetationParams })
  | (ToolboxItemBase & { type: string; params: HighAlbedoParams })
  | (ToolboxItemBase & { type: string; params: ShadeParams })
  | (ToolboxItemBase & { type: string; params: EvaporativeParams });

// A placed instance of a toolbox item, positioned in map (lng/lat) space.
export interface PlacedObject {
  id: string;
  type: string;
  category?: string;
  name?: string;
  color?: string;
  geometry: Geometry;
  params?: Record<string, number>;
  activeFrom?: string;
  activeTo?: string;
}
