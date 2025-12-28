import api from './client';
import { RegisterRequest, TokenResponse, User } from '@/types';

export const login = async (data: { email: string; password: string }): Promise<{ user: User; access_token: string; refresh_token: string }> => {
  // Backend uses OAuth2PasswordRequestForm which expects form data with 'username' field
  const formData = new URLSearchParams();
  formData.append('username', data.email);
  formData.append('password', data.password);
  
  const tokenResponse = await api.post<TokenResponse>('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  
  // Store token temporarily to get user info
  const token = tokenResponse.data.access_token;
  
  // Get user info with the new token
  const userResponse = await api.get<User>('/auth/me', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  
  return {
    user: userResponse.data,
    access_token: tokenResponse.data.access_token,
    refresh_token: tokenResponse.data.refresh_token,
  };
};

export const register = async (data: RegisterRequest): Promise<{ user: User; access_token: string; refresh_token: string }> => {
  // First register the user
  const userResponse = await api.post<User>('/auth/register', data);
  
  // Then login to get tokens
  const formData = new URLSearchParams();
  formData.append('username', data.email);
  formData.append('password', data.password);
  
  const tokenResponse = await api.post<TokenResponse>('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  
  return {
    user: userResponse.data,
    access_token: tokenResponse.data.access_token,
    refresh_token: tokenResponse.data.refresh_token,
  };
};

export const getMe = async (): Promise<User> => {
  const response = await api.get<User>('/auth/me');
  return response.data;
};
