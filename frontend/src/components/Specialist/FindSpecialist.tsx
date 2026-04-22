import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import apiService, { Facility } from '../../services/apiService';
import FacilitiesMap from '../Consultation/FacilitiesMap';
import {
  Search,
  Activity,
  MapPin,
  ChevronLeft,
  Phone,
  ExternalLink,
} from 'lucide-react';

interface FindSpecialistProps {
  theme: 'light' | 'dark';
  onBack: () => void;
  user?: {
    first_name?: string;
    last_name?: string;
    email?: string;
  } | null;
  location?: string;
}

const FindSpecialist: React.FC<FindSpecialistProps> = ({ theme, onBack, user, location }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [nearbyFacilities, setNearbyFacilities] = useState<Facility[]>([]);
  const [loadingFacilities, setLoadingFacilities] = useState(false);

  useEffect(() => {
    const fetchFacilities = async () => {
      if (!location) {
        setNearbyFacilities([]);
        return;
      }

      setLoadingFacilities(true);
      try {
        const response = await apiService.getNearbyFacilities({ location });
        setNearbyFacilities(Array.isArray(response) ? response : []);
      } catch (err) {
        console.error('Error fetching facilities:', err);
        setNearbyFacilities([]);
      } finally {
        setLoadingFacilities(false);
      }
    };

    fetchFacilities();
  }, [location]);

  const filteredFacilities = nearbyFacilities.filter((facility) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return true;

    return (
      (facility.name || '').toLowerCase().includes(query) ||
      (facility.address || '').toLowerCase().includes(query)
    );
  });

  return (
    <div className={`flex-1 ${theme === 'dark' ? 'bg-[#0f0f0f]' : 'bg-gradient-to-br from-orange-50 via-white to-blue-50'} overflow-hidden flex flex-col`}>
      <div className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white/80 backdrop-blur-sm border-gray-200'} border-b px-6 py-4`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
            >
              <ChevronLeft className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
            <div>
              <h1 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Hello {user?.first_name || 'Guest'}!
              </h1>
              <p className={`text-lg ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} font-medium`}>
                Find nearby hospitals
              </p>
            </div>
          </div>

          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center shadow-lg">
            <span className="text-white font-bold text-lg">
              {user?.first_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'G'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {location && (
            <div className={`p-4 rounded-xl ${theme === 'dark' ? 'bg-[#1a1a1a] border border-gray-800' : 'bg-white border border-gray-100 shadow-sm'}`}>
              <h2 className={`text-lg font-bold mb-4 ${theme === 'dark' ? 'text-white' : 'text-gray-900'} flex items-center gap-2`}>
                <MapPin className="text-blue-500" />
                Nearby Hospitals & Clinics near {location}
              </h2>
              {loadingFacilities ? (
                <div className="h-64 flex items-center justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                </div>
              ) : nearbyFacilities.length > 0 ? (
                <div className="h-64 rounded-lg overflow-hidden relative z-0">
                  <FacilitiesMap facilities={nearbyFacilities} />
                </div>
              ) : (
                <div className="h-40 flex items-center justify-center text-gray-500">
                  <p>No facilities found near this location.</p>
                </div>
              )}
            </div>
          )}

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3"
          >
            <div className={`flex-1 flex items-center ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} rounded-2xl px-4 py-3 shadow-lg`}>
              <Search className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-400'} mr-3`} />
              <input
                type="text"
                placeholder="Search hospital by name or address"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={`flex-1 bg-transparent ${theme === 'dark' ? 'text-white placeholder:text-gray-500' : 'text-gray-900 placeholder:text-gray-400'} focus:outline-none`}
              />
            </div>
            <button className="p-3 bg-gradient-to-br from-orange-400 to-pink-500 rounded-2xl shadow-lg hover:shadow-xl transition-all">
              <Activity className="w-6 h-6 text-white" />
            </button>
          </motion.div>

          {location && (
            <div>
              <div className={`${theme === 'dark' ? 'bg-gradient-to-r from-blue-900/30 to-purple-900/20 border-gray-800' : 'bg-gradient-to-r from-blue-50 to-purple-50 border-blue-100'} rounded-2xl p-4 border mb-4`}>
                <div className="flex items-center justify-between">
                  <h2 className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'} flex items-center gap-2`}>
                    <MapPin className="w-5 h-5 text-blue-500" />
                    Nearby Hospitals
                  </h2>
                  <span className={`text-sm px-3 py-1 rounded-full ${theme === 'dark' ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                    {filteredFacilities.length} results
                  </span>
                </div>
                <p className={`text-sm mt-2 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                  Live OpenStreetMap hospitals around {location}
                </p>
              </div>

              {loadingFacilities ? (
                <div className="h-24 flex items-center justify-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                </div>
              ) : filteredFacilities.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredFacilities.map((facility, index) => (
                    <motion.div
                      key={`${facility.name}-${facility.latitude}-${facility.longitude}-${index}`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.03 }}
                      className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800 hover:border-blue-500/40' : 'bg-white border-gray-100 hover:border-blue-200'} rounded-2xl p-4 shadow-sm border transition-all`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'} truncate`}>
                            {facility.name}
                          </h3>
                          <div className="flex items-start gap-2 mt-2">
                            <MapPin className={`w-4 h-4 mt-0.5 flex-shrink-0 ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`} />
                            <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                              {facility.address || 'Address unavailable'}
                            </p>
                          </div>
                          {facility.phone && (
                            <div className="flex items-center gap-2 mt-2">
                              <Phone className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`} />
                              <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                                {facility.phone}
                              </p>
                            </div>
                          )}
                        </div>
                        {typeof facility.distance_km === 'number' && (
                          <div className="px-3 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-500 whitespace-nowrap">
                            {facility.distance_km.toFixed(1)} km
                          </div>
                        )}
                      </div>
                      {facility.maps_url && (
                        <a
                          href={facility.maps_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-3 inline-flex items-center gap-1 text-sm text-blue-500 hover:text-blue-600 transition-colors"
                        >
                          Open in map <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                  No hospitals found for this location.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FindSpecialist;
