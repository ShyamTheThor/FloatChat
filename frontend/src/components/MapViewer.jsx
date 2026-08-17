import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Helper component to auto-zoom to bounds of the data
function ChangeView({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [bounds, map]);
  return null;
}

const MapViewer = ({ data }) => {
  const [bounds, setBounds] = useState([]);

  useEffect(() => {
    if (data && data.length > 0) {
      // Calculate bounding box for all points
      const lats = data.map(d => d.lat);
      const lons = data.map(d => d.lon);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const minLon = Math.min(...lons);
      const maxLon = Math.max(...lons);
      
      setBounds([
        [minLat, minLon],
        [maxLat, maxLon]
      ]);
    }
  }, [data]);

  // For a large number of rows (e.g. 1000s), we should just plot unique (lat, lon) pairs
  // representing the float profiles, rather than every single depth level
  const uniqueProfiles = [];
  const seenIds = new Set();
  
  data.forEach(row => {
    const key = `${row.float_id}_${row.cycle_number}`;
    if (!seenIds.has(key)) {
      seenIds.add(key);
      uniqueProfiles.push(row);
    }
  });

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative', zIndex: 1 }}>
      <MapContainer 
        center={[0, 70]} 
        zoom={3} 
        style={{ height: '100%', width: '100%', background: '#0a0a0a' }}
        zoomControl={false}
      >
        {/* Dark theme base map (CartoDB Dark Matter) */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        
        {bounds.length > 0 && <ChangeView bounds={bounds} />}

        {uniqueProfiles.map((profile, i) => (
          <CircleMarker
            key={i}
            center={[profile.lat, profile.lon]}
            radius={6}
            pathOptions={{
              color: '#3b82f6',
              fillColor: '#60a5fa',
              fillOpacity: 0.7,
              weight: 1
            }}
          >
            <Popup>
              <div style={{ color: '#333' }}>
                <strong>Float ID:</strong> {profile.float_id}<br/>
                <strong>Cycle:</strong> {profile.cycle_number}<br/>
                <strong>Date:</strong> {new Date(profile.timestamp).toLocaleDateString()}<br/>
                <strong>Lat/Lon:</strong> {profile.lat.toFixed(3)}, {profile.lon.toFixed(3)}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
};

export default MapViewer;
