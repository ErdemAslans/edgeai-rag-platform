import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { login, register, getMe } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';
import { useToast } from '@/components/ui/Toast';

export const useAuth = () => {
  const navigate = useNavigate();
  const { setAuth, logout: storeLogout, setUser, token } = useAuthStore();
  const { addToast } = useToast();
  const [isInitialized, setIsInitialized] = useState(false);

  // Check if there's a token in localStorage or store
  const hasToken = token || localStorage.getItem('edgeai_token');

  // Initialize auth on mount - only if there's a token
  const { data, isFetched } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      try {
        const user = await getMe();
        return user;
      } catch (error) {
        return null;
      }
    },
    retry: false,
    enabled: !!hasToken, // Only run query if there's a token
  });

  // Handle initialization state
  useEffect(() => {
    // If there's no token, consider initialized immediately
    if (!hasToken) {
      setIsInitialized(true);
      return;
    }
    
    if (isFetched) {
      setIsInitialized(true);
      if (data) {
        setUser(data);
      }
    }
  }, [isFetched, data, setUser, hasToken]);

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      setAuth(data.user, data.access_token);
      localStorage.setItem('edgeai_token', data.access_token);
      addToast('Login successful!', 'success');
      // Navigation handled by Login component's useEffect
    },
    onError: (error: any) => {
      addToast(error.response?.data?.detail || 'Login failed. Please try again.', 'error');
    },
  });

  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: (data) => {
      setAuth(data.user, data.access_token);
      localStorage.setItem('edgeai_token', data.access_token);
      addToast('Account created successfully!', 'success');
      navigate('/');
    },
    onError: (error: any) => {
      addToast(error.response?.data?.detail || 'Registration failed. Please try again.', 'error');
    },
  });

  const logout = () => {
    storeLogout();
    localStorage.removeItem('edgeai_token');
    addToast('Logged out successfully.', 'info');
    navigate('/login');
  };

  return {
    login: loginMutation.mutate,
    register: registerMutation.mutate,
    logout,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
    isInitialized,
  };
};
