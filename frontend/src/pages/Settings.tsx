import { useState } from 'react';
import { User, LogOut, Bell, Shield } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { useAuthStore } from '@/stores/authStore';

const Settings = () => {
  const { user } = useAuthStore();
  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [notifications, setNotifications] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    // Simulate save
    setTimeout(() => {
      setIsSaving(false);
    }, 1000);
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

            <Input
              id="email"
              type="email"
              label="Email Address"
              value={email}
              disabled
            />

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
                  checked={notifications}
                  onChange={(e) => setNotifications(e.target.checked)}
                  className="w-5 h-5 text-accent focus:ring-accent"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm font-medium text-text-primary">
                  Push Notifications
                </span>
                <input
                  type="checkbox"
                  checked={notifications}
                  onChange={(e) => setNotifications(e.target.checked)}
                  className="w-5 h-5 text-accent focus:ring-accent"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm font-medium text-text-primary">
                  Agent Execution Alerts
                </span>
                <input
                  type="checkbox"
                  checked={notifications}
                  onChange={(e) => setNotifications(e.target.checked)}
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
                  Last Password Change
                </p>
                <p className="text-xs text-text-secondary">
                  Never changed
                </p>
              </div>

              <Button variant="secondary" className="w-full">
                Change Password
              </Button>

              <div className="pt-4 border-t border-border">
                <p className="text-sm font-medium text-text-primary mb-2">
                  Two-Factor Authentication
                </p>
                <p className="text-xs text-text-secondary mb-3">
                  Not enabled
                </p>
                <Button variant="secondary" className="w-full">
                  Enable 2FA
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
};

export default Settings;
