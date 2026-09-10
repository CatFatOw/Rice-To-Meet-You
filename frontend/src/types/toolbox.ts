
import type { Geometry } from './simulation';

// ../types/toolbox
export interface VegetationParams   { coverPct: number; lai: number; irrigation: number }
export interface HighAlbedoParams   { albedo: number; coverage: number; emissivity: number }
export interface ShadeParams        { opacity: number; coverage: number }
export interface EvaporativeParams  { flowRate: number; radius: number; activeFraction: number }

export type ArchetypeType =
  | 'Vegetation'
  | 'High-albedo surface'
  | 'Shade structure'
  | 'Evaporative / water';

type ToolboxItemBase = {
  intervention: string;
  color: string;
  market_code?: string;
  geometry?: Geometry;
  activeFrom?: string;
  activeTo?: string;
  Icon: React.ComponentType<{ size?: number | string; color?: string }>;
  category: ArchetypeType;
  kind: 'polygon' | 'point';
};

export type ToolboxItemDef =
  | (ToolboxItemBase & { params: VegetationParams })
  | (ToolboxItemBase & { params: HighAlbedoParams })
  | (ToolboxItemBase & { params: ShadeParams })
  | (ToolboxItemBase & { params: EvaporativeParams });



// Distributes Omit across each union member so the discriminant/params pairing survives.
type DistributiveOmit<T, K extends keyof any> = T extends unknown ? Omit<T, K> : never;

// Same as ToolboxItemDef but without `category` — the archetype is already the record key.
export type ToolboxItemDefWithoutCategory = DistributiveOmit<ToolboxItemDef, 'category'>;

export type ToolboxItemsByArchetype = Record<ArchetypeType, ToolboxItemDef[]>;

export type AddToolboxItemInput = ToolboxItemDef;

// A placed instance of a toolbox item, positioned in map (lng/lat) space.
export interface PlacedObject {
  id: string;
  name?: string;
  type?: string;
  intervention?: string;
  category?: string;
  color?: string;
  market_code?: string;
  geometry: Geometry;
  params?: Record<string, number>;
  activeFrom?: string;
  activeTo?: string;
}
