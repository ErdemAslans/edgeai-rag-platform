import { ReactNode } from 'react';

export interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

const Header = ({ title, subtitle, actions }: HeaderProps) => {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
          {subtitle && (
            <p className="mt-1 text-text-secondary">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex gap-2">{actions}</div>}
      </div>
    </div>
  );
};

export default Header;
