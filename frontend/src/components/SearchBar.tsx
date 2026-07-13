import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { Search, MapPin, Crosshair, Loader2, X } from 'lucide-react';
import { cities, type City } from '../data/hostCities';
import type { GeocodeResult } from '../types/search';
import type { SearchBarProps } from '../types/components';

// A single resolved place from the geocoder (or a coordinate/city match).
export type { GeocodeResult };

// Parse a "lat, lng" string into [lng, lat] deck.gl order, or null if it isn't
// a valid coordinate pair. Tolerates degree symbols and optional hemisphere
// letters, e.g. "29.717154, -95.404182°", "29.71° N, 95.40° W".
function parseCoordinates(query: string): [number, number] | null {
  const match = query
    .trim()
    .match(
      /^\s*(-?\d+(?:\.\d+)?)\s*°?\s*([NSns])?\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*°?\s*([EWew])?\s*$/,
    );
  if (!match) return null;

  let lat = parseFloat(match[1]);
  let lng = parseFloat(match[3]);
  const latHem = match[2]?.toUpperCase();
  const lngHem = match[4]?.toUpperCase();

  if (latHem === 'S') lat = -Math.abs(lat);
  if (latHem === 'N') lat = Math.abs(lat);
  if (lngHem === 'W') lng = -Math.abs(lng);
  if (lngHem === 'E') lng = Math.abs(lng);

  if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
    return [lng, lat];
  }
  return null;
}

// Free-form place lookup via OpenStreetMap Nominatim. Swap this out for
// MapTiler / Mapbox / Google Geocoding in production (rate limits + API key).
async function geocode(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(
    query,
  )}`;
  const res = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  if (!res.ok) return [];
  const data = (await res.json()) as Array<{ display_name: string; lon: string; lat: string }>;
  return data.map((d) => ({
    label: d.display_name,
    lng: parseFloat(d.lon),
    lat: parseFloat(d.lat),
  }));
}

const SearchBar: React.FC<SearchBarProps> = ({
  searchQuery,
  setSearchQuery,
  geoResults,
  setGeoResults,
  isSearching,
  setIsSearching,
  showSuggestions,
  setShowSuggestions,
  flyTo,
}) => {
  const blurTimeoutRef = useRef<number | null>(null);

  // Local matches against the known host cities (instant, no network).
  const cityMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return cities.filter((c) => c.name.toLowerCase().includes(q)).slice(0, 5);
  }, [searchQuery]);

  const parsedCoords = useMemo(() => parseCoordinates(searchQuery), [searchQuery]);

  // Debounced geocoding for free-form destinations (skipped for coords / short
  // queries). Aborts stale requests so only the latest query resolves.
  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 3 || parseCoordinates(q)) {
      setGeoResults([]);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        setIsSearching(true);
        const results = await geocode(q, controller.signal);
        setGeoResults(results);
      } catch {
        /* aborted or failed — ignore */
      } finally {
        setIsSearching(false);
      }
    }, 350);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery]);

  const selectCity = useCallback(
    (city: City) => {
      flyTo(city.longitude, city.latitude, 10, city.name);
      setSearchQuery(city.name);
      setShowSuggestions(false);
    },
    [flyTo, setSearchQuery, setShowSuggestions],
  );

  const selectPlace = useCallback(
    (place: GeocodeResult) => {
      flyTo(place.lng, place.lat, 12);
      setSearchQuery(place.label);
      setShowSuggestions(false);
    },
    [flyTo, setSearchQuery, setShowSuggestions],
  );

  // Enter / search-button: resolve in priority order coords -> city -> geocode.
  const handleSearchSubmit = useCallback(async () => {
    const q = searchQuery.trim();
    if (!q) return;

    if (parsedCoords) {
      flyTo(parsedCoords[0], parsedCoords[1], 12);
      setShowSuggestions(false);
      return;
    }
    if (cityMatches.length > 0) {
      selectCity(cityMatches[0]);
      return;
    }
    if (geoResults.length > 0) {
      selectPlace(geoResults[0]);
      return;
    }

    // Nothing cached yet — geocode synchronously on submit.
    try {
      setIsSearching(true);
      const results = await geocode(q);
      if (results.length > 0) selectPlace(results[0]);
    } catch {
      /* ignore */
    } finally {
      setIsSearching(false);
      setShowSuggestions(false);
    }
  }, [
    searchQuery,
    parsedCoords,
    cityMatches,
    geoResults,
    flyTo,
    selectCity,
    selectPlace,
    setIsSearching,
    setShowSuggestions,
  ]);

  const clearSearch = useCallback(() => {
    setSearchQuery('');
    setGeoResults([]);
    setShowSuggestions(false);
  }, [setSearchQuery, setGeoResults, setShowSuggestions]);

  const hasSuggestions =
    parsedCoords !== null || cityMatches.length > 0 || geoResults.length > 0;

  return (
    <div
      style={{
        position: 'absolute',
        top: 20,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 35,
        width: 360,
        maxWidth: 'calc(100% - 320px)',
      }}
      onBlur={() => {
        // Delay so a click on a suggestion still registers before closing.
        blurTimeoutRef.current = window.setTimeout(() => setShowSuggestions(false), 120);
      }}
      onFocus={() => {
        if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
        setShowSuggestions(true);
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          borderRadius: 10,
          border: '1px solid rgba(148, 163, 184, 0.45)',
          backgroundColor: 'rgba(2, 8, 23, 0.92)',
          boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
        }}
      >
        {isSearching ? (
          <Loader2 size={16} color="#94a3b8" style={{ animation: 'spin 1s linear infinite' }} />
        ) : (
          <Search size={16} color="#94a3b8" />
        )}
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setShowSuggestions(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearchSubmit();
            if (e.key === 'Escape') setShowSuggestions(false);
          }}
          placeholder="Search city, place, or lat, lng"
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            color: '#f1f5f9',
            fontSize: 14,
          }}
        />
        {searchQuery && (
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={clearSearch}
            aria-label="Clear search"
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: 2,
            }}
          >
            <X size={15} />
          </button>
        )}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && searchQuery.trim() && hasSuggestions && (
        <div
          style={{
            marginTop: 6,
            borderRadius: 10,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            backgroundColor: 'rgba(2, 8, 23, 0.96)',
            boxShadow: '0 6px 18px rgba(0, 0, 0, 0.4)',
            overflow: 'hidden',
          }}
        >
          {parsedCoords && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                flyTo(parsedCoords[0], parsedCoords[1], 12);
                setShowSuggestions(false);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                color: '#f1f5f9',
                cursor: 'pointer',
                fontSize: 13,
                textAlign: 'left',
              }}
            >
              <Crosshair size={15} color="#38bdf8" />
              Go to {parsedCoords[1].toFixed(4)}, {parsedCoords[0].toFixed(4)}
            </button>
          )}

          {cityMatches.map((city) => (
            <button
              key={`city-${city.name}`}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => selectCity(city)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                color: '#f1f5f9',
                cursor: 'pointer',
                fontSize: 13,
                textAlign: 'left',
              }}
            >
              <MapPin size={15} color="#f87171" />
              <span>{city.name}</span>
              <span style={{ marginLeft: 'auto', fontSize: 11, color: '#64748b' }}>City</span>
            </button>
          ))}

          {geoResults.map((place, i) => (
            <button
              key={`geo-${i}`}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => selectPlace(place)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                borderBottom:
                  i === geoResults.length - 1 ? 'none' : '1px solid rgba(148, 163, 184, 0.2)',
                color: '#cbd5e1',
                cursor: 'pointer',
                fontSize: 13,
                textAlign: 'left',
              }}
            >
              <Search size={14} color="#94a3b8" style={{ flexShrink: 0 }} />
              <span
                style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {place.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchBar;