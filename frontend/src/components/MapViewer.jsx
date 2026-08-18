import React, { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

function ChangeView({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
    }
  }, [bounds, map]);
  return null;
}

// Continuous color interpolator for temperature
const getContinuousColorForTemp = (temp, minTemp, maxTemp) => {
  if (temp === null || temp === undefined || isNaN(temp)) return '#94a3b8';
  const span = Math.max(0.5, maxTemp - minTemp);
  const norm = Math.max(0, Math.min(1, (temp - minTemp) / span));
  if (norm < 0.33) return '#3b82f6';  // Cool Blue
  if (norm < 0.66) return '#06b6d4';  // Cyan / Aqua
  if (norm < 0.85) return '#f59e0b';  // Amber
  return '#ef4444';                   // Warm Red
};

// Continuous color interpolator for salinity (Indigo -> Cyan -> Emerald -> Amber)
const getContinuousColorForSal = (sal, minSal, maxSal) => {
  if (sal === null || sal === undefined || isNaN(sal)) return '#94a3b8';
  const span = Math.max(0.2, maxSal - minSal);
  const norm = Math.max(0, Math.min(1, (sal - minSal) / span));
  if (norm < 0.25) return '#6366f1';  // Low salinity (coastal / Bay of Bengal fresh influx)
  if (norm < 0.55) return '#06b6d4';  // Moderate open ocean
  if (norm < 0.80) return '#10b981';  // Typical saline
  return '#f59e0b';                   // High salinity (Arabian Sea / evaporation zones)
};

const MapViewer = ({ data, parameter = 'temperature' }) => {
  const [bounds, setBounds] = useState([]);
  const isSalinity = parameter === 'salinity';

  // Aggregate by unique float profile (float_id + cycle_number)
  const profiles = useMemo(() => {
    if (!data || data.length === 0) return [];
    
    const profileMap = new Map();
    data.forEach(row => {
      const key = `${row.float_id}_${row.cycle_number}`;
      if (!profileMap.has(key)) {
        profileMap.set(key, {
          float_id: row.float_id,
          cycle_number: row.cycle_number,
          lat: row.lat,
          lon: row.lon,
          timestamp: row.timestamp,
          temps: [],
          sals: [],
          depths: []
        });
      }
      const item = profileMap.get(key);
      if (row.temperature !== null) item.temps.push(row.temperature);
      if (row.salinity !== null) item.sals.push(row.salinity);
      if (row.depth_m !== null) item.depths.push(row.depth_m);
    });

    return Array.from(profileMap.values()).map(p => ({
      ...p,
      avg_temp: p.temps.length ? parseFloat((p.temps.reduce((a,b) => a+b, 0) / p.temps.length).toFixed(1)) : null,
      avg_sal: p.sals.length ? parseFloat((p.sals.reduce((a,b) => a+b, 0) / p.sals.length).toFixed(2)) : null,
      min_depth: p.depths.length ? Math.min(...p.depths).toFixed(0) : 0,
      max_depth: p.depths.length ? Math.max(...p.depths).toFixed(0) : 0
    }));
  }, [data]);

  // Compute actual dynamic range from the result set
  const rangeStats = useMemo(() => {
    const validSals = profiles.map(p => p.avg_sal).filter(v => v !== null);
    const validTemps = profiles.map(p => p.avg_temp).filter(v => v !== null);
    return {
      minSal: validSals.length ? Math.min(...validSals) : 34.0,
      maxSal: validSals.length ? Math.max(...validSals) : 37.0,
      minTemp: validTemps.length ? Math.min(...validTemps) : 15.0,
      maxTemp: validTemps.length ? Math.max(...validTemps) : 30.0,
    };
  }, [profiles]);

  useEffect(() => {
    if (profiles.length > 0) {
      const lats = profiles.map(p => p.lat);
      const lons = profiles.map(p => p.lon);
      setBounds([
        [Math.min(...lats), Math.min(...lons)],
        [Math.max(...lats), Math.max(...lons)]
      ]);
    }
  }, [profiles]);

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <MapContainer 
        center={[10, 75]} 
        zoom={4} 
        style={{ height: '100%', width: '100%', background: '#050914' }}
        zoomControl={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        
        {bounds.length > 0 && <ChangeView bounds={bounds} />}

        {profiles.map((p, i) => {
          let markerColor = '#06b6d4';
          if (isSalinity) {
            markerColor = getContinuousColorForSal(p.avg_sal, rangeStats.minSal, rangeStats.maxSal);
          } else {
            markerColor = getContinuousColorForTemp(p.avg_temp, rangeStats.minTemp, rangeStats.maxTemp);
          }

          return (
            <CircleMarker
              key={i}
              center={[p.lat, p.lon]}
              radius={7}
              pathOptions={{
                color: '#070c1e',
                fillColor: markerColor,
                fillOpacity: 0.9,
                weight: 1.5
              }}
            >
              <Popup>
                <div style={{ color: '#0f172a', fontFamily: 'sans-serif', fontSize: '0.85rem' }}>
                  <strong style={{ color: '#0284c7' }}>Float ID: {p.float_id}</strong> (Cycle {p.cycle_number})<br/>
                  <strong>Date:</strong> {p.timestamp ? p.timestamp.slice(0, 10) : 'N/A'}<br/>
                  <strong>Position:</strong> {p.lat.toFixed(3)}°N, {p.lon.toFixed(3)}°E<br/>
                  <strong>Mean Temp:</strong> {p.avg_temp !== null ? `${p.avg_temp} °C` : 'N/A'}<br/>
                  <strong>Mean Salinity:</strong> {p.avg_sal !== null ? `${p.avg_sal} psu` : 'N/A'}<br/>
                  <strong>Depth Span:</strong> {p.min_depth} – {p.max_depth} m
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Map Legend Overlay with continuous gradient */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        right: '20px',
        zIndex: 1000,
        background: 'rgba(15, 23, 42, 0.9)',
        border: '1px solid rgba(255,255,255,0.15)',
        padding: '0.75rem 1rem',
        borderRadius: '8px',
        backdropFilter: 'blur(10px)',
        fontSize: '0.75rem',
        color: '#f8fafc',
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        minWidth: '220px'
      }}>
        <div style={{ fontWeight: 600, marginBottom: '0.4rem', color: '#06b6d4', display: 'flex', justifyContent: 'space-between' }}>
          <span>{isSalinity ? 'Salinity (psu)' : 'Temperature (°C)'}</span>
          <span style={{ color: '#94a3b8', fontSize: '0.7rem' }}>{profiles.length} floats</span>
        </div>

        {/* Continuous Gradient Bar */}
        <div style={{
          height: '8px',
          borderRadius: '4px',
          background: isSalinity
            ? 'linear-gradient(90deg, #6366f1 0%, #06b6d4 40%, #10b981 75%, #f59e0b 100%)'
            : 'linear-gradient(90deg, #3b82f6 0%, #06b6d4 40%, #f59e0b 75%, #ef4444 100%)',
          marginBottom: '0.35rem'
        }}></div>

        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1', fontSize: '0.7rem' }}>
          <span>{isSalinity ? `${rangeStats.minSal.toFixed(2)} psu` : `${rangeStats.minTemp.toFixed(1)} °C`}</span>
          <span>{isSalinity ? `${rangeStats.maxSal.toFixed(2)} psu` : `${rangeStats.maxTemp.toFixed(1)} °C`}</span>
        </div>
      </div>
    </div>
  );
};

export default MapViewer;

