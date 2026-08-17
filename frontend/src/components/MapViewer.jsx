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

// Color scale interpolator (Blue -> Cyan -> Yellow -> Red)
const getColorForTemp = (temp, minTemp = 10, maxTemp = 30) => {
  if (temp === null || temp === undefined) return '#94a3b8';
  const norm = Math.max(0, Math.min(1, (temp - minTemp) / (maxTemp - minTemp || 1)));
  if (norm < 0.33) return '#3b82f6';  // Cool Blue
  if (norm < 0.66) return '#06b6d4';  // Cyan / Aqua
  if (norm < 0.85) return '#f59e0b';  // Amber
  return '#ef4444';                   // Warm Red
};

const MapViewer = ({ data, parameter: _parameter = 'temperature' }) => {
  const [bounds, setBounds] = useState([]);

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
      avg_temp: p.temps.length ? (p.temps.reduce((a,b) => a+b, 0) / p.temps.length).toFixed(1) : null,
      avg_sal: p.sals.length ? (p.sals.reduce((a,b) => a+b, 0) / p.sals.length).toFixed(1) : null,
      min_depth: p.depths.length ? Math.min(...p.depths).toFixed(0) : 0,
      max_depth: p.depths.length ? Math.max(...p.depths).toFixed(0) : 0
    }));
  }, [data]);

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
          const val = p.avg_temp ? parseFloat(p.avg_temp) : 20;
          const markerColor = getColorForTemp(val);
          return (
            <CircleMarker
              key={i}
              center={[p.lat, p.lon]}
              radius={7}
              pathOptions={{
                color: '#070c1e',
                fillColor: markerColor,
                fillOpacity: 0.85,
                weight: 1.5
              }}
            >
              <Popup>
                <div style={{ color: '#0f172a', fontFamily: 'sans-serif', fontSize: '0.85rem' }}>
                  <strong style={{ color: '#0284c7' }}>Float ID: {p.float_id}</strong> (Cycle {p.cycle_number})<br/>
                  <strong>Date:</strong> {p.timestamp ? p.timestamp.slice(0, 10) : 'N/A'}<br/>
                  <strong>Position:</strong> {p.lat.toFixed(3)}°N, {p.lon.toFixed(3)}°E<br/>
                  <strong>Mean Temp:</strong> {p.avg_temp ? `${p.avg_temp} °C` : 'N/A'}<br/>
                  <strong>Mean Salinity:</strong> {p.avg_sal ? `${p.avg_sal} psu` : 'N/A'}<br/>
                  <strong>Depth Span:</strong> {p.min_depth} – {p.max_depth} m
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Map Legend Overlay */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        right: '20px',
        zIndex: 1000,
        background: 'rgba(15, 23, 42, 0.85)',
        border: '1px solid rgba(255,255,255,0.1)',
        padding: '0.65rem 0.85rem',
        borderRadius: '8px',
        backdropFilter: 'blur(8px)',
        fontSize: '0.75rem',
        color: '#f8fafc'
      }}>
        <div style={{ fontWeight: 600, marginBottom: '0.35rem', color: '#06b6d4' }}>
          ARGO Float Locations ({profiles.length} Profiles)
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.2rem' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#3b82f6' }}></span> Cool (&lt;18°C)
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#06b6d4', marginLeft: '0.4rem' }}></span> Moderate
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444', marginLeft: '0.4rem' }}></span> Warm (&gt;28°C)
        </div>
      </div>
    </div>
  );
};

export default MapViewer;

