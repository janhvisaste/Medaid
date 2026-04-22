import React, { Suspense } from 'react';
import Spline from '@splinetool/react-spline';

interface InteractiveCanvasProps {
  sceneUrl: string;
  className?: string;
}

export const InteractiveCanvas: React.FC<InteractiveCanvasProps> = ({ sceneUrl, className }) => {
  return (
    <div className={`relative w-full h-full ${className || ''}`}>
      <Suspense fallback={
        <div className="absolute inset-0 flex items-center justify-center bg-gray-950/20 backdrop-blur-sm">
          <div className="w-8 h-8 rounded-full border-t-2 border-r-2 border-blue-500 animate-spin"></div>
        </div>
      }>
        <Spline scene={sceneUrl} className="w-full h-full" />
      </Suspense>
    </div>
  );
};
