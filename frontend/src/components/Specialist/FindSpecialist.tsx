import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Search,
  Heart,
  Brain,
  Activity,
  Stethoscope,
  Eye,
  Bone,
  Baby,
  Pill,
  Clock,
  Star,
  MapPin,
  ChevronLeft,
  Phone,
  Mail
} from 'lucide-react';

interface Doctor {
  id: number;
  name: string;
  specialization: string;
  hospital: string;
  rating: number;
  experience: number;
  availability: string;
  image: string;
  consultationFee: number;
  address: string;
  phone: string;
  email: string;
}

interface FindSpecialistProps {
  theme: 'light' | 'dark';
  onBack: () => void;
  user?: {
    first_name?: string;
    last_name?: string;
    email?: string;
  } | null;
}

const FindSpecialist: React.FC<FindSpecialistProps> = ({ theme, onBack, user }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSpecialty, setSelectedSpecialty] = useState<string | null>(null);

  const specialties = [
    {
      name: 'Cardiology',
      icon: Heart,
      color: 'from-orange-400 to-pink-500',
      bgColor: theme === 'dark' ? 'bg-orange-500/10' : 'bg-orange-100',
      description: 'Heart & Cardiovascular'
    },
    {
      name: 'Gastrology',
      icon: Activity,
      color: 'from-cyan-400 to-blue-500',
      bgColor: theme === 'dark' ? 'bg-cyan-500/10' : 'bg-cyan-100',
      description: 'Digestive System'
    },
    {
      name: 'Neurology',
      icon: Brain,
      color: 'from-pink-400 to-orange-500',
      bgColor: theme === 'dark' ? 'bg-pink-500/10' : 'bg-pink-100',
      description: 'Brain & Nervous System'
    },
    {
      name: 'Orthopedics',
      icon: Bone,
      color: 'from-purple-400 to-indigo-500',
      bgColor: theme === 'dark' ? 'bg-purple-500/10' : 'bg-purple-100',
      description: 'Bones & Joints'
    },
    {
      name: 'Pediatrics',
      icon: Baby,
      color: 'from-green-400 to-teal-500',
      bgColor: theme === 'dark' ? 'bg-green-500/10' : 'bg-green-100',
      description: 'Child Healthcare'
    },
    {
      name: 'Ophthalmology',
      icon: Eye,
      color: 'from-blue-400 to-cyan-500',
      bgColor: theme === 'dark' ? 'bg-blue-500/10' : 'bg-blue-100',
      description: 'Eye Care'
    }
  ];

  const topDoctors: Doctor[] = [
    {
      id: 1,
      name: 'Prof. Dr. Kevin Williams',
      specialization: 'Heart Surgeon',
      hospital: 'United Hospital',
      rating: 4.9,
      experience: 15,
      availability: '10:40 AM - 2:40 PM',
      image: 'doctor1',
      consultationFee: 150,
      address: 'United Hospital, Medical District',
      phone: '+1-555-0123',
      email: 'kevin.williams@united.health'
    },
    {
      id: 2,
      name: 'Dr. Jane Foster',
      specialization: 'Cardiologist',
      hospital: 'Apollo Hospital',
      rating: 4.8,
      experience: 12,
      availability: '10:40 AM - 2:40 PM',
      image: 'doctor2',
      consultationFee: 120,
      address: 'Apollo Hospital, Central Avenue',
      phone: '+1-555-0124',
      email: 'jane.foster@apollo.health'
    },
    {
      id: 3,
      name: 'Brandi Guarino',
      specialization: 'Heart Surgeon',
      hospital: 'United Hospital',
      rating: 4.7,
      experience: 10,
      availability: '10:40 AM - 2:40 PM',
      image: 'doctor3',
      consultationFee: 140,
      address: 'United Hospital, Medical District',
      phone: '+1-555-0125',
      email: 'brandi.guarino@united.health'
    },
    {
      id: 4,
      name: 'Dr. Sarah Johnson',
      specialization: 'Gastroenterologist',
      hospital: 'City Medical Center',
      rating: 4.8,
      experience: 14,
      availability: '9:00 AM - 1:00 PM',
      image: 'doctor4',
      consultationFee: 130,
      address: 'City Medical Center, Downtown',
      phone: '+1-555-0126',
      email: 'sarah.johnson@citymed.health'
    },
    {
      id: 5,
      name: 'Dr. Michael Chen',
      specialization: 'Neurologist',
      hospital: 'Brain & Spine Institute',
      rating: 4.9,
      experience: 18,
      availability: '2:00 PM - 6:00 PM',
      image: 'doctor5',
      consultationFee: 180,
      address: 'Brain & Spine Institute, Medical Plaza',
      phone: '+1-555-0127',
      email: 'michael.chen@brainspine.health'
    }
  ];

  const filteredDoctors = topDoctors.filter(doctor => {
    const matchesSearch = 
      doctor.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doctor.specialization.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doctor.hospital.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesSpecialty = !selectedSpecialty || 
      doctor.specialization.toLowerCase().includes(selectedSpecialty.toLowerCase());
    
    return matchesSearch && matchesSpecialty;
  });

  const getDoctorAvatar = (doctorId: number) => {
    const colors = [
      'from-orange-400 to-pink-500',
      'from-cyan-400 to-blue-500',
      'from-purple-400 to-indigo-500',
      'from-green-400 to-teal-500',
      'from-blue-400 to-cyan-500'
    ];
    return colors[doctorId % colors.length];
  };

  return (
    <div className={`flex-1 ${theme === 'dark' ? 'bg-[#0f0f0f]' : 'bg-gradient-to-br from-orange-50 via-white to-blue-50'} overflow-hidden flex flex-col`}>
      {/* Header */}
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
                Find your specialist
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Search Bar */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex items-center gap-3`}
          >
            <div className={`flex-1 flex items-center ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} rounded-2xl px-4 py-3 shadow-lg`}>
              <Search className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-400'} mr-3`} />
              <input
                type="text"
                placeholder="Search doctor"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={`flex-1 bg-transparent ${theme === 'dark' ? 'text-white placeholder:text-gray-500' : 'text-gray-900 placeholder:text-gray-400'} focus:outline-none`}
              />
            </div>
            <button className="p-3 bg-gradient-to-br from-orange-400 to-pink-500 rounded-2xl shadow-lg hover:shadow-xl transition-all">
              <Activity className="w-6 h-6 text-white" />
            </button>
          </motion.div>

          {/* Specialty Cards */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Specialties
              </h2>
              <button 
                onClick={() => setSelectedSpecialty(null)}
                className="text-orange-500 font-medium text-sm hover:text-orange-600 transition-colors"
              >
                See all
              </button>
            </div>

            <div className="grid grid-cols-3 gap-5">
              {specialties.map((specialty, index) => (
                <motion.button
                  key={specialty.name}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.05 }}
                  onClick={() => setSelectedSpecialty(specialty.name)}
                  className={`${specialty.bgColor} rounded-3xl p-8 hover:scale-105 transition-all shadow-md hover:shadow-xl ${
                    selectedSpecialty === specialty.name ? 'ring-2 ring-orange-500' : ''
                  }`}
                >
                  <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${specialty.color} flex items-center justify-center mb-4 mx-auto shadow-lg`}>
                    <specialty.icon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className={`font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'} text-lg mb-2`}>
                    {specialty.name}
                  </h3>
                  <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} leading-relaxed`}>
                    {specialty.description}
                  </p>
                </motion.button>
              ))}
            </div>
          </div>

          {/* Top Doctors */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Top Doctor
              </h2>
              <button className="text-orange-500 font-medium text-sm hover:text-orange-600 transition-colors">
                See all
              </button>
            </div>

            <div className="space-y-4">
              {filteredDoctors.map((doctor, index) => (
                <motion.div
                  key={doctor.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className={`${theme === 'dark' ? 'bg-[#1a1a1a]' : 'bg-white'} rounded-2xl p-5 shadow-lg hover:shadow-xl transition-all`}
                >
                  <div className="flex items-center gap-4">
                    {/* Doctor Avatar */}
                    <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${getDoctorAvatar(doctor.id)} flex items-center justify-center flex-shrink-0`}>
                      <span className="text-3xl">👨‍⚕️</span>
                    </div>

                    {/* Doctor Info */}
                    <div className="flex-1">
                      <h3 className={`text-lg font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'} mb-1`}>
                        {doctor.name}
                      </h3>
                      <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} mb-2`}>
                        {doctor.specialization} - {doctor.hospital}
                      </p>
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                          <span className={`${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'} font-semibold`}>
                            {doctor.rating}
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`} />
                          <span className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                            {doctor.availability}
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Stethoscope className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`} />
                          <span className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                            {doctor.experience} yrs exp
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Appointment Button */}
                    <button 
                      className={`px-6 py-2 rounded-xl font-semibold transition-all ${
                        index % 2 === 0 
                          ? 'bg-gradient-to-br from-orange-400 to-pink-500 text-white hover:shadow-lg' 
                          : 'bg-gradient-to-br from-cyan-400 to-blue-500 text-white hover:shadow-lg'
                      }`}
                    >
                      Appointment
                    </button>
                  </div>

                  {/* Expanded Details */}
                  <details className="mt-4">
                    <summary className={`cursor-pointer text-sm font-medium ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} hover:text-orange-500 transition-colors`}>
                      View more details
                    </summary>
                    <div className={`mt-4 pt-4 border-t ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'} space-y-3`}>
                      <div className="flex items-start gap-3">
                        <MapPin className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'} flex-shrink-0`} />
                        <div>
                          <p className={`text-sm font-medium ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>Address</p>
                          <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>{doctor.address}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <Phone className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'} flex-shrink-0`} />
                        <div>
                          <p className={`text-sm font-medium ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>Phone</p>
                          <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>{doctor.phone}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <Mail className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'} flex-shrink-0`} />
                        <div>
                          <p className={`text-sm font-medium ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>Email</p>
                          <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>{doctor.email}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <Pill className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'} flex-shrink-0`} />
                        <div>
                          <p className={`text-sm font-medium ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>Consultation Fee</p>
                          <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>${doctor.consultationFee}</p>
                        </div>
                      </div>
                    </div>
                  </details>
                </motion.div>
              ))}
            </div>

            {filteredDoctors.length === 0 && (
              <div className="text-center py-12">
                <Stethoscope className={`w-16 h-16 ${theme === 'dark' ? 'text-gray-700' : 'text-gray-300'} mx-auto mb-4`} />
                <p className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                  No doctors found matching your criteria
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FindSpecialist;
