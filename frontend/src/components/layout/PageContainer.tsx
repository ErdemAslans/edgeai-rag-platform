import { ReactNode } from 'react';
import Sidebar from './Sidebar';

interface PageContainerProps {
  children: ReactNode;
}

const PageContainer = ({ children }: PageContainerProps) => {
  return (
    <div className="min-h-screen bg-secondary">
      <Sidebar />
      <main className="ml-60 p-8">
        {children}
      </main>
    </div>
  );
};

export default PageContainer;
