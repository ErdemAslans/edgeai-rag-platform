import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Bell, Shield, Eye, EyeOff } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { useAuthStore } from '@/stores/authStore';
import api from '@/api/client';

const Settings = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [name, setName] = useState(user?.name || '');
  const [email] = useState(user?.email || '');
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [pushNotifications, setPushNotifications] = useState(true);
  const [agentAlerts, setAgentAlerts] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');

  const [is2FAModalOpen, setIs2FAModalOpen] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);
    try {
      await api.patch('/auth/me', { full_name: name });
      setSaveMessage({ type: 'success', text: 'Settings saved successfully!' });
    } catch {
      setSaveMessage({ type: 'error', text: 'Failed to save settings.' });
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const validatePassword = (password: string): string[] => {
    const errors: string[] = [];
    if (password.length < 8) errors.push('At least 8 characters');
    if (!/[A-Z]/.test(password)) errors.push('One uppercase letter');
    if (!/[a-z]/.test(password)) errors.push('One lowercase letter');
    if (!/[0-9]/.test(password)) errors.push('One number');
    return errors;
  };

  const handleChangePassword = async () => {
    setPasswordError('');
    setPasswordSuccess('');

    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordError('All fields are required');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match');
      return;
    }

    const validationErrors = validatePassword(newPassword);
    if (validationErrors.length > 0) {
      setPasswordError(`Password must have: ${validationErrors.join(', ')}`);
      return;
    }

    setIsChangingPassword(true);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess('Password changed successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        setIsPasswordModalOpen(false);
        setPasswordSuccess('');
      }, 2000);
    } catch (error: any) {
      setPasswordError(error.response?.data?.detail || 'Failed to change password');
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <PageContainer>
      <Header
        title="Settings"
        subtitle="Manage your account and preferences"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <div className="flex items-center gap-4 mb-6">
            <div className="p-3 bg-accent/10 rounded-full">
              <User className="w-8 h-8 text-accent" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary">
                Profile Information
              </h3>
              <p className="text-sm text-text-secondary">
                Update your personal information
              </p>
            </div>
          </div>

          <form className="space-y-4">
            <Input
              id="name"
              type="text"
              label="Full Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />

            <div>
              <Input
                id="email"
                type="email"
                label="Email Address"
                value={email}
                disabled
              />
              <p className="text-xs text-text-secondary mt-1">
                Email cannot be changed
              </p>
            </div>

            {saveMessage && (
              <p className={`text-sm ${saveMessage.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                {saveMessage.text}
              </p>
            )}

            <Button
              type="button"
              variant="primary"
              onClick={handleSave}
              isLoading={isSaving}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </form>
        </Card>

        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 bg-accent/10 rounded-full">
                <Bell className="w-8 h-8 text-accent" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-primary">
                  Notifications
                </h3>
                <p className="text-sm text-text-secondary">
                  Manage your notification preferences
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm font-medium text-text-primary">
                  Email Notifications
                </span>
                <input
                  type="checkbox"
                  checked={emailNotifications}
                  onChange={(e) => setEmailNotifications(e.target.checked)}
                  className="w-5 h-5 text-accent focus:ring-accent"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm font-medium text-text-primary">
                  Push Notifications
                </span>
                <input
                  type="checkbox"
                  checked={pushNotifications}
                  onChange={(e) => setPushNotifications(e.target.checked)}
                  className="w-5 h-5 text-accent focus:ring-accent"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm font-medium text-text-primary">
                  Agent Execution Alerts
                </span>
                <input
                  type="checkbox"
                  checked={agentAlerts}
                  onChange={(e) => setAgentAlerts(e.target.checked)}
                  className="w-5 h-5 text-accent focus:ring-accent"
                />
              </label>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 bg-accent/10 rounded-full">
                <Shield className="w-8 h-8 text-accent" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-primary">
                  Security
                </h3>
                <p className="text-sm text-text-secondary">
                  Manage your security settings
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-text-primary mb-2">
                  Password
                </p>
                <p className="text-xs text-text-secondary mb-2">
                  Strong password recommended (8+ chars, uppercase, number)
                </p>
              </div>

              <Button
                variant="secondary"
                className="w-full"
                onClick={() => setIsPasswordModalOpen(true)}
              >
                Change Password
              </Button>

              <div className="pt-4 border-t border-border">
                <p className="text-sm font-medium text-text-primary mb-2">
                  Two-Factor Authentication
                </p>
                <p className="text-xs text-text-secondary mb-3">
                  Not enabled - Add extra security to your account
                </p>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => setIs2FAModalOpen(true)}
                >
                  Enable 2FA
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <Modal
        isOpen={isPasswordModalOpen}
        onClose={() => {
          setIsPasswordModalOpen(false);
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
          setPasswordError('');
          setPasswordSuccess('');
        }}
        title="Change Password"
      >
        <div className="space-y-4">
          <div className="relative">
            <Input
              id="current-password"
              type={showCurrentPassword ? 'text' : 'password'}
              label="Current Password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <button
              type="button"
              className="absolute right-3 top-8 text-text-secondary hover:text-text-primary"
              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
            >
              {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <div className="relative">
            <Input
              id="new-password"
              type={showNewPassword ? 'text' : 'password'}
              label="New Password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <button
              type="button"
              className="absolute right-3 top-8 text-text-secondary hover:text-text-primary"
              onClick={() => setShowNewPassword(!showNewPassword)}
            >
              {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <Input
            id="confirm-password"
            type="password"
            label="Confirm New Password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />

          <div className="text-xs text-text-secondary">
            Password must have: 8+ characters, uppercase, lowercase, number
          </div>

          {passwordError && (
            <p className="text-sm text-red-600">{passwordError}</p>
          )}
          {passwordSuccess && (
            <p className="text-sm text-green-600">{passwordSuccess}</p>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              variant="secondary"
              onClick={() => setIsPasswordModalOpen(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleChangePassword}
              isLoading={isChangingPassword}
              className="flex-1"
            >
              Change Password
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={is2FAModalOpen}
        onClose={() => setIs2FAModalOpen(false)}
        title="Two-Factor Authentication"
      >
        <div className="space-y-4">
          <p className="text-text-secondary">
            Two-factor authentication adds an extra layer of security to your account.
            When enabled, you'll need to enter a code from your authenticator app in addition to your password.
          </p>
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-sm text-yellow-800">
              2FA setup is coming soon. This feature is under development.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => setIs2FAModalOpen(false)}
            className="w-full"
          >
            Close
          </Button>
        </div>
      </Modal>
    </PageContainer>
  );
};

export default Settings;
