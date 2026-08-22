export interface MetricConfig {
  power: number;
  scales: Record<string, number>; // date -> value scale
  options?: { attachIndividualMetrics?: boolean; rippleAmp?: number };
}
