import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ROUTES } from '@/lib/constants';
import ToastProvider from '@/components/ui/Toast';
import ProtectedRoute from '@/components/ProtectedRoute';
import Login from '@/pages/auth/Login';
import Register from '@/pages/auth/Register';
import Dashboard from '@/pages/Dashboard';
import Documents from '@/pages/Documents';
import Chat from '@/pages/Chat';
import Agents from '@/pages/Agents';
import Settings from '@/pages/Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});


const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path={ROUTES.LOGIN} element={<Login />} />
            <Route path={ROUTES.REGISTER} element={<Register />} />

            {/* Protected routes */}
            <Route path={ROUTES.DASHBOARD} element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } />
            <Route path={ROUTES.DOCUMENTS} element={
              <ProtectedRoute>
                <Documents />
              </ProtectedRoute>
            } />
            <Route path={ROUTES.CHAT} element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            } />
            <Route path={ROUTES.AGENTS} element={
              <ProtectedRoute>
                <Agents />
              </ProtectedRoute>
            } />
            <Route path={ROUTES.SETTINGS} element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            } />

            {/* Default redirect */}
            <Route path="/" element={<Navigate to={ROUTES.DASHBOARD} replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
};

export default App;
