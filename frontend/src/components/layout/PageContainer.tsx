import { ReactNode } from 'react';
import Sidebar from './Sidebar';

interface PageContainerProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
}

const PageContainer = ({ children, title, subtitle }: PageContainerProps) => {
  return (
    <div className="min-h-screen bg-secondary">
      <Sidebar />
      <main className="ml-60 p-8">
        {(title || subtitle) && (
          <div className="mb-6">
            {title && <h1 className="text-2xl font-bold text-text-primary">{title}</h1>}
            {subtitle && <p className="text-text-secondary mt-1">{subtitle}</p>}
          </div>
        )}
        {children}
      </main>
    </div>
  );
};

export default PageContainer;
