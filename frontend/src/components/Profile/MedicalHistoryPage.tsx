import React from 'react';
import { Link } from 'react-router-dom';
import { Lightbulb, UserRound } from 'lucide-react';
import { medaidClasses } from '../../styles/medaidTokens';
import MedicalHistoryForm from './MedicalHistoryForm';

// The route used to render the bare form. Every other patient page opens with
// the same eyebrow / title / subtitle header, so this one does too.
const MedicalHistoryPage: React.FC = () => (
  <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 md:px-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className={medaidClasses.eyebrow}>Your health profile</p>
        <h2 className={medaidClasses.dashboardTitle}>Medical history</h2>
        <p className={`mt-2 max-w-xl ${medaidClasses.bodySmall}`}>
          Conditions you've been diagnosed with, plus anything else worth knowing. Assessments use this
          context, so keeping it current makes the guidance you get more accurate.
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link to="/medical-history-insights" className={`${medaidClasses.buttonSecondary} px-4 py-2.5`}>
          <Lightbulb className="h-4 w-4" /> Report insights
        </Link>
        <Link to="/profile" className={`${medaidClasses.buttonSecondary} px-4 py-2.5`}>
          <UserRound className="h-4 w-4" /> Profile
        </Link>
      </div>
    </header>
    <MedicalHistoryForm />
  </div>
);

export default MedicalHistoryPage;
