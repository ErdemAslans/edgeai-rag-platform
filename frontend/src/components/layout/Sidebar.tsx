import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FileText, MessageSquare, Bot, Settings, LogOut, BarChart3, TrendingUp, Network, Users, Share2 } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { ROUTES } from '@/lib/constants';
import { getInitials } from '@/lib/utils';
import { NotificationDropdown } from '../collaboration';

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const navItems = [
    { path: ROUTES.DASHBOARD, label: 'Dashboard', icon: LayoutDashboard },
    { path: ROUTES.DOCUMENTS, label: 'Documents', icon: FileText },
    { path: ROUTES.CHAT, label: 'Chat', icon: MessageSquare },
    { path: ROUTES.AGENTS, label: 'Agents', icon: Bot },
    { path: '/knowledge-graph', label: 'Knowledge Graph', icon: Network },
    { path: '/shared-with-me', label: 'Shared With Me', icon: Share2 },
    { path: '/analytics', label: 'Learning', icon: BarChart3 },
    { path: '/analytics/advanced', label: 'Analytics', icon: TrendingUp },
    { path: ROUTES.SETTINGS, label: 'Settings', icon: Settings },
  ];

  const handleLogout = () => {
    logout();
    localStorage.removeItem('edgeai_token');
    localStorage.removeItem('edgeai_user');
    navigate(ROUTES.LOGIN, { replace: true });
  };

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-white border-r border-border flex flex-col z-40">
      <div className="p-6 border-b border-border">
        <h1 className="text-xl font-bold text-text-primary">EdgeAI</h1>
      </div>

      <nav className="flex-1 px-3 py-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            
            return (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive: isNavLinkActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isNavLinkActive
                        ? 'bg-accent/10 text-accent'
                        : 'text-text-secondary hover:bg-gray-100 hover:text-text-primary'
                    }`
                  }
                >
                  <Icon className="w-5 h-5" />
                  {item.label}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      {user && (
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center text-accent text-sm font-medium">
              {getInitials(user.full_name || user.email)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary truncate">
                {user.full_name || 'User'}
              </p>
              <p className="text-xs text-text-secondary truncate">
                {user.email}
              </p>
            </div>
            <NotificationDropdown />
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-text-secondary hover:text-error hover:bg-error/5 rounded-md transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
