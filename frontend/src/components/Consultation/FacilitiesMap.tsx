import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Facility } from '../../services/apiService';

// Fix Leaflet's default icon path issues with webpack
delete (L.Icon.Default.prototype as any)._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png')
});

interface FacilitiesMapProps {
  facilities: Facility[];
}

const ChangeView = ({ center, zoom }: { center: [number, number], zoom: number }) => {
  const map = useMap();
  map.setView(center, zoom);
  return null;
}

const FacilitiesMap: React.FC<FacilitiesMapProps> = ({ facilities }) => {
  const [center, setCenter] = useState<[number, number]>([20.5937, 78.9629]); // Default India center
  const [zoom, setZoom] = useState(5);

  useEffect(() => {
    if (facilities.length > 0) {
      // Find first facility with valid coords to center the map
      const validFacility = facilities.find(f => f.latitude && f.longitude);
      if (validFacility && validFacility.latitude && validFacility.longitude) {
        setCenter([validFacility.latitude, validFacility.longitude]);
        setZoom(13);
      }
    }
  }, [facilities]);

  const validFacilities = facilities.filter(f => f.latitude && f.longitude);

  if (validFacilities.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-card border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] p-4 text-sm text-[var(--medaid-ink-muted)]">
        <p>No map data available for these facilities.</p>
      </div>
    );
  }

  return (
    <div className="relative z-0 h-64 w-full overflow-hidden rounded-card border border-[var(--medaid-border)]">
      <MapContainer center={center} zoom={zoom} scrollWheelZoom={false} style={{ height: '100%', width: '100%', zIndex: 0 }}>
        <ChangeView center={center} zoom={zoom} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {validFacilities.map((facility, index) => (
          facility.latitude && facility.longitude ? (
            <Marker key={index} position={[facility.latitude, facility.longitude]}>
              <Popup>
                <div className="text-sm">
                  <strong>{facility.name}</strong><br />
                  {facility.address}<br />
                  {facility.distance_km && <>{facility.distance_km.toFixed(1)} km away<br /></>}
                  {facility.phone && <>{facility.phone}</>}
                </div>
              </Popup>
            </Marker>
          ) : null
        ))}
      </MapContainer>
    </div>
  );
};

export default FacilitiesMap;
