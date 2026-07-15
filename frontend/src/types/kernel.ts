import type { HeatmapMetricValue } from './heatmap';

type IndividualMetrics = HeatmapMetricValue['individual_metrics'];

type SpatialKernel = (distanceMeters: number) => number;
type ResponseKernel = (baseValue: number) => number;
type SuitabilityKernel = (metrics: IndividualMetrics) => number;
type EnvironmentalKernel = (metrics: IndividualMetrics, time: string) => number;

export interface MetricEffectModel {
  intensity: number;
  floor: number;
  spatial: SpatialKernel;
  response: ResponseKernel;
  suitability?: SuitabilityKernel;
  environmental?: EnvironmentalKernel;
}

export interface Tool {
  id: string;
  toolType: string;
  location: [number, number];
  placedAt: string;
  activeHours: number;
  effects: Record<string, MetricEffectModel>;
}

export type KernelModel = Record<string, Record<string, MetricEffectModel>>;
