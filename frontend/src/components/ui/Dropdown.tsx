import { ReactNode, useRef, useState, useEffect, createContext, useContext } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DropdownContextValue {
  isOpen: boolean;
  setIsOpen: (value: boolean) => void;
  close: () => void;
}

const DropdownContext = createContext<DropdownContextValue | undefined>(undefined);

const useDropdown = () => {
  const context = useContext(DropdownContext);
  if (!context) {
    throw new Error('Dropdown components must be used within a Dropdown');
  }
  return context;
};

export interface DropdownProps {
  children: ReactNode;
  className?: string;
}

const Dropdown = ({ children, className }: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const close = () => setIsOpen(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        close();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <DropdownContext.Provider value={{ isOpen, setIsOpen, close }}>
      <div ref={dropdownRef} className={cn('relative', className)}>
        {children}
      </div>
    </DropdownContext.Provider>
  );
};

interface DropdownTriggerProps {
  children: ReactNode;
  className?: string;
}

const DropdownTrigger = ({ children, className }: DropdownTriggerProps) => {
  const { isOpen, setIsOpen } = useDropdown();

  return (
    <button
      onClick={() => setIsOpen(!isOpen)}
      className={cn(
        'inline-flex items-center justify-between gap-2 px-3 py-2 border border-border rounded-md bg-white text-text-primary hover:bg-gray-50 transition-colors',
        className
      )}
    >
      {children}
      <ChevronDown className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
    </button>
  );
};

interface DropdownContentProps {
  children: ReactNode;
  className?: string;
  align?: 'start' | 'end';
}

const DropdownContent = ({ children, className, align = 'start' }: DropdownContentProps) => {
  const { isOpen } = useDropdown();

  if (!isOpen) return null;

  return (
    <div
      className={cn(
        'absolute z-10 min-w-[8rem] overflow-hidden rounded-md border border-border bg-white shadow-lg mt-1',
        align === 'start' && 'left-0',
        align === 'end' && 'right-0',
        className
      )}
    >
      {children}
    </div>
  );
};

interface DropdownItemProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  disabled?: boolean;
}

const DropdownItem = ({ children, onClick, className, disabled }: DropdownItemProps) => {
  const { close } = useDropdown();

  return (
    <button
      onClick={() => {
        if (!disabled) {
          onClick?.();
          close();
        }
      }}
      disabled={disabled}
      className={cn(
        'w-full text-left px-3 py-2 text-sm text-text-primary hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        className
      )}
    >
      {children}
    </button>
  );
};

Dropdown.Trigger = DropdownTrigger;
Dropdown.Content = DropdownContent;
Dropdown.Item = DropdownItem;

export default Dropdown;
