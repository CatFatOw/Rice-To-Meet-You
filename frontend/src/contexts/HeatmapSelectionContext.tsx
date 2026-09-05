import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

interface HeatmapSelectionContextValue {
  city: string | null;
  date: string | null;
  setSelection: (city: string | null, date: string | null) => void;
}

const HeatmapSelectionContext = createContext<HeatmapSelectionContextValue | null>(null);

export function HeatmapSelectionProvider({ children }: { children: ReactNode }) {
  const [city, setCity] = useState<string | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const setSelection = useCallback((nextCity: string | null, nextDate: string | null) => {
    setCity(nextCity);
    setDate(nextDate);
  }, []);

  return (
    <HeatmapSelectionContext.Provider
      value={{
        city,
        date,
        setSelection,
      }}
    >
      {children}
    </HeatmapSelectionContext.Provider>
  );
}

export function useHeatmapSelection() {
  const context = useContext(HeatmapSelectionContext);
  if (!context) {
    throw new Error('useHeatmapSelection must be used within HeatmapSelectionProvider');
  }
  return context;
}
