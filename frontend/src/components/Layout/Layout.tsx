import React from 'react';
import Navigation from './Navigation';

interface LayoutProps {
  children: React.ReactNode;
  showNavigation?: boolean;
}

const Layout: React.FC<LayoutProps> = ({ children, showNavigation = true }) => {
  return (
    <div className="min-h-screen bg-gray-50">
      {showNavigation && <Navigation />}
      <main className="py-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;
