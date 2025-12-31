import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Bell, Shield, Eye, EyeOff, Copy, Check } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { useAuthStore } from '@/stores/authStore';
import api from '@/api/client';
import { setup2FA, enable2FA, disable2FA, TwoFactorSetupResponse } from '@/api/auth';

const Settings = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuthStore();
  const [name, setName] = useState(user?.full_name || '');
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
  const [is2FADisableModalOpen, setIs2FADisableModalOpen] = useState(false);
  const [twoFactorSetup, setTwoFactorSetup] = useState<TwoFactorSetupResponse | null>(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [is2FALoading, setIs2FALoading] = useState(false);
  const [twoFactorError, setTwoFactorError] = useState('');
  const [twoFactorSuccess, setTwoFactorSuccess] = useState('');
  const [showBackupCodes, setShowBackupCodes] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const is2FAEnabled = user?.two_factor_enabled || false;

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);
    try {
      await api.patch('/auth/me', { full_name: name });
      setSaveMessage({ type: 'success', text: 'Settings saved successfully!' });
      if (refreshUser) await refreshUser();
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

  const handleSetup2FA = async () => {
    setIs2FALoading(true);
    setTwoFactorError('');
    try {
      const setupData = await setup2FA();
      setTwoFactorSetup(setupData);
      setShowBackupCodes(false);
    } catch (error: any) {
      setTwoFactorError(error.response?.data?.detail || 'Failed to setup 2FA');
    } finally {
      setIs2FALoading(false);
    }
  };

  const handleEnable2FA = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      setTwoFactorError('Please enter a valid 6-digit code');
      return;
    }

    setIs2FALoading(true);
    setTwoFactorError('');
    try {
      await enable2FA(verificationCode);
      setTwoFactorSuccess('2FA enabled successfully!');
      setShowBackupCodes(true);
      if (refreshUser) await refreshUser();
    } catch (error: any) {
      setTwoFactorError(error.response?.data?.detail || 'Invalid verification code');
    } finally {
      setIs2FALoading(false);
    }
  };

  const handleDisable2FA = async () => {
    if (!disablePassword || !disableCode) {
      setTwoFactorError('Password and code are required');
      return;
    }

    setIs2FALoading(true);
    setTwoFactorError('');
    try {
      await disable2FA(disablePassword, disableCode);
      setTwoFactorSuccess('2FA disabled successfully!');
      if (refreshUser) await refreshUser();
      setTimeout(() => {
        setIs2FADisableModalOpen(false);
        setTwoFactorSuccess('');
        setDisablePassword('');
        setDisableCode('');
      }, 2000);
    } catch (error: any) {
      setTwoFactorError(error.response?.data?.detail || 'Failed to disable 2FA');
    } finally {
      setIs2FALoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(text);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const open2FAModal = () => {
    setIs2FAModalOpen(true);
    setTwoFactorSetup(null);
    setVerificationCode('');
    setTwoFactorError('');
    setTwoFactorSuccess('');
    setShowBackupCodes(false);
  };

  const close2FAModal = () => {
    setIs2FAModalOpen(false);
    setTwoFactorSetup(null);
    setVerificationCode('');
    setTwoFactorError('');
    setTwoFactorSuccess('');
    setShowBackupCodes(false);
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
                  {is2FAEnabled 
                    ? '✅ Enabled - Your account has extra security'
                    : 'Not enabled - Add extra security to your account'}
                </p>
                <Button
                  variant={is2FAEnabled ? 'secondary' : 'primary'}
                  className="w-full"
                  onClick={() => is2FAEnabled ? setIs2FADisableModalOpen(true) : open2FAModal()}
                >
                  {is2FAEnabled ? 'Disable 2FA' : 'Enable 2FA'}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Password Change Modal */}
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

      {/* 2FA Enable Modal */}
      <Modal
        isOpen={is2FAModalOpen}
        onClose={close2FAModal}
        title="Two-Factor Authentication Setup"
      >
        <div className="space-y-4">
          {!twoFactorSetup ? (
            <>
              <p className="text-text-secondary">
                Two-factor authentication adds an extra layer of security to your account.
                You'll need an authenticator app like Google Authenticator or Authy.
              </p>
              <Button
                variant="primary"
                onClick={handleSetup2FA}
                isLoading={is2FALoading}
                className="w-full"
              >
                Setup 2FA
              </Button>
            </>
          ) : !showBackupCodes ? (
            <>
              <div className="text-center">
                <p className="text-sm text-text-secondary mb-4">
                  Scan this QR code with your authenticator app, or enter the secret key manually:
                </p>
                <div className="bg-gray-100 p-4 rounded-lg inline-block mb-4">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(twoFactorSetup.uri)}`}
                    alt="2FA QR Code"
                    className="mx-auto"
                  />
                </div>
                <div className="bg-gray-100 p-3 rounded-md mb-4">
                  <p className="text-xs text-text-secondary mb-1">Secret Key:</p>
                  <div className="flex items-center justify-center gap-2">
                    <code className="text-sm font-mono">{twoFactorSetup.secret}</code>
                    <button
                      onClick={() => copyToClipboard(twoFactorSetup.secret)}
                      className="p-1 hover:bg-gray-200 rounded"
                    >
                      {copiedCode === twoFactorSetup.secret ? (
                        <Check className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4 text-text-secondary" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <Input
                id="verification-code"
                type="text"
                label="Verification Code"
                placeholder="Enter 6-digit code"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
              />

              {twoFactorError && (
                <p className="text-sm text-red-600">{twoFactorError}</p>
              )}
              {twoFactorSuccess && (
                <p className="text-sm text-green-600">{twoFactorSuccess}</p>
              )}

              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  onClick={close2FAModal}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={handleEnable2FA}
                  isLoading={is2FALoading}
                  className="flex-1"
                >
                  Enable 2FA
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="bg-green-50 border border-green-200 p-4 rounded-md mb-4">
                <p className="text-green-800 font-medium">2FA Enabled Successfully!</p>
                <p className="text-sm text-green-700 mt-1">
                  Save your backup codes in a secure location. Each code can only be used once.
                </p>
              </div>

              <div className="bg-gray-100 p-4 rounded-md">
                <p className="text-sm font-medium text-text-primary mb-2">Backup Codes:</p>
                <div className="grid grid-cols-2 gap-2">
                  {twoFactorSetup.backup_codes.map((code, index) => (
                    <div key={index} className="flex items-center justify-between bg-white p-2 rounded border">
                      <code className="text-sm font-mono">{code}</code>
                      <button
                        onClick={() => copyToClipboard(code)}
                        className="p-1 hover:bg-gray-100 rounded"
                      >
                        {copiedCode === code ? (
                          <Check className="w-3 h-3 text-green-600" />
                        ) : (
                          <Copy className="w-3 h-3 text-text-secondary" />
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <Button
                variant="primary"
                onClick={close2FAModal}
                className="w-full"
              >
                Done
              </Button>
            </>
          )}
        </div>
      </Modal>

      {/* 2FA Disable Modal */}
      <Modal
        isOpen={is2FADisableModalOpen}
        onClose={() => {
          setIs2FADisableModalOpen(false);
          setDisablePassword('');
          setDisableCode('');
          setTwoFactorError('');
          setTwoFactorSuccess('');
        }}
        title="Disable Two-Factor Authentication"
      >
        <div className="space-y-4">
          <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-md">
            <p className="text-yellow-800 text-sm">
              Warning: Disabling 2FA will make your account less secure.
            </p>
          </div>

          <Input
            id="disable-password"
            type="password"
            label="Password"
            value={disablePassword}
            onChange={(e) => setDisablePassword(e.target.value)}
          />

          <Input
            id="disable-code"
            type="text"
            label="2FA Code"
            placeholder="Enter 6-digit code"
            value={disableCode}
            onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            maxLength={6}
          />

          {twoFactorError && (
            <p className="text-sm text-red-600">{twoFactorError}</p>
          )}
          {twoFactorSuccess && (
            <p className="text-sm text-green-600">{twoFactorSuccess}</p>
          )}

          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={() => setIs2FADisableModalOpen(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleDisable2FA}
              isLoading={is2FALoading}
              className="flex-1"
            >
              Disable 2FA
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
};

export default Settings;
