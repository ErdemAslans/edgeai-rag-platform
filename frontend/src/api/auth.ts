import api from './client';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  requires_2fa?: boolean;
  user?: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  permissions: string[];
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  is_email_verified: boolean;
  two_factor_enabled: boolean;
  created_at: string;
  updated_at: string;
  roles: Role[];
  permissions: string[];
}

export interface TwoFactorSetupResponse {
  secret: string;
  uri: string;
  backup_codes: string[];
}

export interface TwoFactorVerifyRequest {
  user_id: string;
  code: string;
  is_backup_code?: boolean;
}

export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);
  
  const response = await api.post<LoginResponse>('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

export const register = async (data: RegisterRequest): Promise<LoginResponse> => {
  const response = await api.post<LoginResponse>('/auth/register', data);
  return response.data;
};

export const getMe = async (): Promise<User> => {
  const response = await api.get<User>('/auth/me');
  return response.data;
};

export const logout = async (): Promise<void> => {
  await api.post('/auth/logout');
};

export const refreshToken = async (refreshToken: string): Promise<LoginResponse> => {
  const response = await api.post<LoginResponse>('/auth/refresh', {
    refresh_token: refreshToken,
  });
  return response.data;
};

export const changePassword = async (currentPassword: string, newPassword: string): Promise<void> => {
  await api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
};

export const updateProfile = async (data: { full_name?: string }): Promise<User> => {
  const response = await api.patch<User>('/auth/me', data);
  return response.data;
};

// Email verification
export const verifyEmail = async (token: string): Promise<void> => {
  await api.post('/auth/verify-email', { token });
};

export const resendVerificationEmail = async (): Promise<void> => {
  await api.post('/auth/resend-verification');
};

// 2FA
export const setup2FA = async (): Promise<TwoFactorSetupResponse> => {
  const response = await api.post<TwoFactorSetupResponse>('/auth/2fa/setup');
  return response.data;
};

export const enable2FA = async (code: string): Promise<void> => {
  await api.post('/auth/2fa/enable', { code });
};

export const disable2FA = async (password: string, code: string): Promise<void> => {
  await api.post('/auth/2fa/disable', { password, code });
};

export const verify2FA = async (userId: string, code: string, isBackupCode: boolean = false): Promise<LoginResponse> => {
  const response = await api.post<LoginResponse>('/auth/verify-2fa', {
    user_id: userId,
    code,
    is_backup_code: isBackupCode,
  });
  return response.data;
};
