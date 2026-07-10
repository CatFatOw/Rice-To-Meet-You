import { useEffect, useState } from 'react';
import { Clock, MapPin, Search } from 'lucide-react';
import { lookupFoursquarePlaces, type FoursquarePlace } from '../api/foursquare';
import { getGooglePoiAnalytics, type GooglePoiAnalyticsResponse } from '../api/googleAnalytics';

interface FoursquareLookupProps {
  latitude?: string;
  longitude?: string;
  onPlaceSelect: (place: FoursquarePlace) => void;
}

export default function FoursquareLookup({
  latitude = '29.717154',
  longitude = '-95.404182',
  onPlaceSelect,
}: FoursquareLookupProps) {
  const [latitudeInput, setLatitudeInput] = useState(latitude);
  const [longitudeInput, setLongitudeInput] = useState(longitude);
  const [time, setTime] = useState(new Date().toISOString().slice(0, 16));
  const [places, setPlaces] = useState<FoursquarePlace[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trafficByPlace, setTrafficByPlace] = useState<Record<string, GooglePoiAnalyticsResponse>>({});
  const [trafficLoadingId, setTrafficLoadingId] = useState<string | null>(null);

  useEffect(() => {
    if (latitude) setLatitudeInput(latitude);
    if (longitude) setLongitudeInput(longitude);
  }, [latitude, longitude]);

  const lookup = async () => {
    const lat = Number.parseFloat(latitudeInput);
    const lon = Number.parseFloat(longitudeInput);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError('Enter a valid latitude and longitude.');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const result = await lookupFoursquarePlaces(lat, lon, time);
      setPlaces(result.places);
      setTrafficByPlace({});
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : 'Foursquare lookup failed.',
      );
    } finally {
      setIsLoading(false);
    }
  };

  const loadTrafficScore = async (place: FoursquarePlace) => {
    try {
      setTrafficLoadingId(place.fsq_place_id);
      setError(null);
      const traffic = await getGooglePoiAnalytics(
        place.name,
        place.latitude,
        place.longitude,
        place.category,
      );
      setTrafficByPlace((previous) => ({ ...previous, [place.fsq_place_id]: traffic }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Google analytics lookup failed.');
    } finally {
      setTrafficLoadingId(null);
    }
  };

  const handlePlaceSelect = (place: FoursquarePlace) => {
    onPlaceSelect(place);
    void loadTrafficScore(place);
  };

  const renderGoogleTrafficSummary = (traffic: GooglePoiAnalyticsResponse) => {
    const routeSamples = (traffic.route_samples ?? []).slice(0, 4);
    const notes = traffic.data_notes ?? [];

    return (
      <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-2 grid grid-cols-3 gap-1.5">
          <div className="rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
            <div className="text-[9px] uppercase text-slate-500">Traffic</div>
            <div className="mt-0.5 text-sm font-bold text-sky-200">
              {traffic.traffic_score ?? '-'}%
            </div>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
            <div className="text-[9px] uppercase text-slate-500">Status</div>
            <div className="mt-0.5 truncate text-[11px] font-semibold text-emerald-200">
              {traffic.traffic_status}
            </div>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
            <div className="text-[9px] uppercase text-slate-500">Nearby</div>
            <div className="mt-0.5 truncate text-[11px] font-semibold text-slate-300">
              {traffic.nearby_place_count ?? '-'} {traffic.nearby_place_type ?? 'places'}
            </div>
          </div>
        </div>

        {routeSamples.length > 0 && (
          <div className="space-y-1">
            <div className="mb-1 flex items-center justify-between text-[10px] text-slate-500">
              <span>Google Routes approach delay</span>
              <span>{traffic.average_delay_seconds ?? 0}s avg</span>
            </div>
            {routeSamples.map((sample) => (
              <div key={sample.label}>
                <div className="mb-0.5 flex items-center justify-between gap-2 text-[11px]">
                  <span className="truncate text-slate-300">{sample.label}</span>
                  <span className="shrink-0 text-sky-200">{sample.congestion_percent}%</span>
                </div>
                <div
                  className="h-1.5 overflow-hidden rounded-full bg-slate-800"
                  title={`${sample.delay_seconds}s delay vs static travel time`}
                >
                  <div
                    className="h-full rounded-full bg-sky-400"
                    style={{ width: `${Math.max(4, sample.congestion_percent)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {notes[0] && (
          <div className="mt-2 text-[10px] leading-4 text-slate-500">{notes[0]}</div>
        )}
      </div>
    );
  };

  return (
    <div className="shrink-0 rounded-lg border border-slate-800 bg-[#07111f] p-4 shadow-lg">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Live Foursquare POIs
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-100">
            Current places near a coordinate
          </div>
        </div>
        <MapPin size={18} className="shrink-0 text-sky-300" />
      </div>

      <div className="mb-2 grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-400">
          Latitude
          <input
            value={latitudeInput}
            onChange={(event) => setLatitudeInput(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-sky-500"
          />
        </label>
        <label className="text-xs text-slate-400">
          Longitude
          <input
            value={longitudeInput}
            onChange={(event) => setLongitudeInput(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-sky-500"
          />
        </label>
      </div>

      <input
        type="datetime-local"
        value={time}
        onChange={(event) => setTime(event.target.value)}
        className="mb-2 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-sky-500"
      />

      <button
        type="button"
        onClick={() => void lookup()}
        disabled={isLoading}
        className="mb-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-sky-500/40 bg-sky-500/15 px-3 py-2 text-sm font-semibold text-sky-100 transition hover:bg-sky-500/25 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Search size={15} />
        {isLoading ? 'Looking up...' : 'Find nearby POIs'}
      </button>

      <p className="mb-2 text-[11px] leading-4 text-slate-500">
        Select a place to load Google route traffic and nearby-place density. Google does not expose per-venue visitor counts here.
      </p>

      {error && (
        <div className="mb-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-100">
          {error}
        </div>
      )}

      <div className="max-h-72 overflow-y-auto rounded-md border border-slate-800">
        {places.length === 0 ? (
          <div className="px-3 py-3 text-xs text-slate-500">No Foursquare results loaded</div>
        ) : (
          places.map((place) => {
            const traffic = trafficByPlace[place.fsq_place_id];
            return (
              <div
                key={place.fsq_place_id}
                className="border-b border-slate-800 px-3 py-2 text-xs last:border-0"
              >
                <button
                  type="button"
                  onClick={() => handlePlaceSelect(place)}
                  className="block w-full text-left transition hover:text-sky-100"
                >
                  <span className="block truncate font-semibold text-slate-200">{place.name}</span>
                  <span className="mt-0.5 block truncate text-slate-500">
                    {place.category ?? 'Uncategorized'} · {place.distance_m} m
                  </span>
                  {place.address && (
                    <span className="mt-0.5 block truncate text-slate-600">{place.address}</span>
                  )}
                </button>

                {trafficLoadingId === place.fsq_place_id && (
                  <div className="mt-2 flex items-center gap-1.5 text-[11px] font-semibold text-emerald-300">
                    <Clock size={12} />
                    Loading Google traffic analytics...
                  </div>
                )}

                {traffic && renderGoogleTrafficSummary(traffic)}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
