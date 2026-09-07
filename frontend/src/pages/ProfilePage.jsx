import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  Mail,
  Lock,
  Save,
  X,
  ShieldCheck,
  AlertTriangle,
  Building,
  Ticket,
  Briefcase,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../store/authStore';
import * as api from '../services/api';
import { Navbar } from '../components/Navbar/Navbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { FormInput } from '../components/ui/FormInput';
import { PasswordInput } from '../components/ui/PasswordInput';
import { Button } from '../components/ui/Button';
import { Toast } from '../components/ui/Toast';
import { EmailVerificationModal } from '../components/EmailVerification/EmailVerificationModal';
import { validateEmail } from '../utils/validators';

/**
 * ProfilePage Component
 * Allows users to view and edit their profile information
 */
export function ProfilePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Auth store (optimized with selectors to prevent unnecessary re-renders)
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const logoutAllDevices = useAuthStore((state) => state.logoutAllDevices);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [toast, setToast] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showVerificationModal, setShowVerificationModal] = useState(false);
  const [isSendingOtp, setIsSendingOtp] = useState(false);
  const [inviteCode, setInviteCode] = useState('');
  const [isRedeemingCode, setIsRedeemingCode] = useState(false);

  // Profile form state
  const [profileData, setProfileData] = useState({
    username: '',
    firstName: '',
    lastName: '',
    email: '',
    profilePic: '',
    title: '',
  });

  // Password form state
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [errors, setErrors] = useState({});
  const [showDeactivateModal, setShowDeactivateModal] = useState(false);
  const [isDeactivating, setIsDeactivating] = useState(false);

  // Load user data
  useEffect(() => {
    if (user) {
      setProfileData({
        username: user.username || '',
        firstName: user.firstName || '',
        lastName: user.lastName || '',
        email: user.email || '',
        profilePic: user.profilePic || '',
        title: user.title || '',
      });
    }
  }, [user]);

  const handleLogout = useCallback(async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      setToast({ message: 'Logout failed', type: 'error' });
    }
  }, [logout, navigate]);

  const handleLogoutAll = useCallback(async () => {
    try {
      await logoutAllDevices();
      navigate('/login');
    } catch (error) {
      setToast({ message: 'Failed to logout from all devices', type: 'error' });
    }
  }, [logoutAllDevices, navigate]);

  // Handle send verification OTP
  const handleSendVerificationOtp = useCallback(async () => {
    setIsSendingOtp(true);
    try {
      await api.sendEmailOTP(user.email);
      setShowVerificationModal(true);
      setToast({
        message: 'Verification code sent to your email!',
        type: 'success',
      });
    } catch (error) {
      setToast({
        message: error.message || 'Failed to send verification code',
        type: 'error',
      });
    } finally {
      setIsSendingOtp(false);
    }
  }, [user]);

  // Handle verification success
  const handleVerificationSuccess = useCallback(async () => {
    try {
      // Reload user data to get updated verification status
      // eslint-disable-next-line no-unused-vars
      const response = await api.getMe();
      window.location.reload();
    } catch (error) {
      console.error('Failed to reload user data:', error);
    }
  }, []);

  // Handle profile update
  const handleProfileSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      setErrors({});

      // Validation
      const newErrors = {};
      if (!profileData.firstName.trim()) {
        newErrors.firstName = 'First name is required';
      }
      if (!profileData.lastName.trim()) {
        newErrors.lastName = 'Last name is required';
      }
      if (!validateEmail(profileData.email)) {
        newErrors.email = 'Invalid email address';
      }

      if (Object.keys(newErrors).length > 0) {
        setErrors(newErrors);
        return;
      }

      setIsSubmitting(true);
      try {
        await api.updateProfile({
          firstName: profileData.firstName,
          lastName: profileData.lastName,
          email: profileData.email,
          profilePic: profileData.profilePic || undefined,
          title: profileData.title || undefined,
        });

        setToast({ message: 'Profile updated successfully!', type: 'success' });
        setIsEditing(false);

        // Reload user data
        await api.getMe();
        // Update will happen through AuthProvider
        window.location.reload(); // Reload to get fresh user data
      } catch (error) {
        setToast({
          message: error.message || 'Failed to update profile',
          type: 'error',
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [profileData]
  );

  // Handle password change
  const handlePasswordSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      setErrors({});

      // Validation
      const newErrors = {};
      if (!passwordData.currentPassword) {
        newErrors.currentPassword = 'Current password is required';
      }
      if (!passwordData.newPassword) {
        newErrors.newPassword = 'New password is required';
      } else if (passwordData.newPassword.length < 8) {
        newErrors.newPassword = 'Password must be at least 8 characters';
      }
      if (passwordData.newPassword !== passwordData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }

      if (Object.keys(newErrors).length > 0) {
        setErrors(newErrors);
        return;
      }

      setIsSubmitting(true);
      try {
        await api.changePassword(
          passwordData.currentPassword,
          passwordData.newPassword,
          passwordData.confirmPassword
        );

        setToast({
          message: 'Password changed successfully!',
          type: 'success',
        });
        setIsChangingPassword(false);
        setPasswordData({
          currentPassword: '',
          newPassword: '',
          confirmPassword: '',
        });
      } catch (error) {
        setToast({
          message: error.message || 'Failed to change password',
          type: 'error',
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [passwordData]
  );

  // Handle account deactivation
  const handleDeactivateAccount = useCallback(async () => {
    setIsDeactivating(true);
    try {
      await api.deactivateAccount();
      setToast({
        message: 'Account deactivated successfully. Logging out...',
        type: 'success',
      });

      // Wait a moment to show the message, then logout
      setTimeout(async () => {
        await logout();
        navigate('/login');
      }, 2000);
    } catch (error) {
      setToast({
        message: error.message || 'Failed to deactivate account',
        type: 'error',
      });
      setIsDeactivating(false);
    } finally {
      setShowDeactivateModal(false);
    }
  }, [logout, navigate]);

  if (!user) {
    return null; // Loading or redirect will happen via ProtectedRoute
  }

  return (
    <div className="flex flex-col min-h-screen w-full overflow-x-hidden bg-gray-50">
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Email Verification Modal */}
      <EmailVerificationModal
        isOpen={showVerificationModal}
        onClose={() => setShowVerificationModal(false)}
        email={user.email}
        onVerificationSuccess={handleVerificationSuccess}
      />

      {/* Navbar - Full Width at Top */}
      <Navbar
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        user={user}
      />

      {/* Content Area with Sidebar */}
      <div className="flex flex-1 w-full overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          isOpen={sidebarOpen}
          onLogout={handleLogout}
          onLogoutAll={handleLogoutAll}
          onClose={() => setSidebarOpen(false)}
        />

        {/* Main Content */}
        <main
          className="flex-1 w-full overflow-x-hidden overflow-y-auto"
          role="main"
        >
          <div className="w-full max-w-full px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
            <div className="max-w-4xl mx-auto">
              {/* Header */}
              <div className="mb-6">
                <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
                  {t('profile.title')}
                </h1>
                <p className="text-gray-600 mt-1">{t('profile.subtitle')}</p>
              </div>

              {/* Profile Card */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
                {/* Profile Header */}
                <div className="bg-gradient-to-r from-primary to-primary-dark p-6 sm:p-8">
                  <div className="flex flex-col sm:flex-row items-center gap-4">
                    <div className="w-24 h-24 rounded-full bg-white flex items-center justify-center text-primary text-3xl font-bold shadow-lg overflow-hidden">
                      {profileData.profilePic ? (
                        <img
                          src={profileData.profilePic}
                          alt="Profile"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <span>
                          {user.firstName?.charAt(0)}
                          {user.lastName?.charAt(0)}
                        </span>
                      )}
                    </div>
                    <div className="text-center sm:text-left text-white">
                      <h2 className="text-2xl font-bold">
                        {user.firstName} {user.lastName}
                      </h2>
                      {user.title && (
                        <p className="text-white/90 text-sm">{user.title}</p>
                      )}
                      <p className="text-white/90">@{user.username}</p>
                      <p className="text-white/80 text-sm mt-1">{user.email}</p>
                    </div>
                  </div>
                </div>

                {/* Profile Form */}
                <div className="p-6 sm:p-8">
                  {!isEditing && !isChangingPassword ? (
                    // View Mode
                    <div className="space-y-6">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            {t('profile.username')}
                          </label>
                          <p className="text-gray-900 font-medium">
                            @{user.username}
                          </p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            {t('profile.email')}
                          </label>
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-gray-900">{user.email}</p>
                            {user.emailVerified ? (
                              <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full">
                                <ShieldCheck size={14} />
                                {t('profile.emailVerified')}
                              </span>
                            ) : (
                              <>
                                <span className="inline-flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-700 text-xs font-medium rounded-full">
                                  ⚠ {t('profile.emailNotVerified')}
                                </span>
                                <button
                                  onClick={handleSendVerificationOtp}
                                  disabled={isSendingOtp}
                                  className="text-xs text-primary hover:text-primary-dark underline font-medium disabled:opacity-50"
                                >
                                  {isSendingOtp
                                    ? t('profile.sending')
                                    : t('profile.verifyNow')}
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            {t('profile.firstName')}
                          </label>
                          <p className="text-gray-900">{user.firstName}</p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            {t('profile.lastName')}
                          </label>
                          <p className="text-gray-900">{user.lastName}</p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Title / Designation
                          </label>
                          <p className="text-gray-900">{user.title || <span className="text-gray-400 italic">Not set</span>}</p>
                        </div>
                      </div>

                      <div className="border-t pt-6 flex flex-wrap gap-3">
                        <Button
                          onClick={() => setIsEditing(true)}
                          className="flex items-center gap-2"
                        >
                          <User size={18} />
                          {t('profile.editProfile')}
                        </Button>
                        <button
                          onClick={() => setIsChangingPassword(true)}
                          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2 text-gray-700"
                        >
                          <Lock size={18} />
                          {t('profile.changePassword')}
                        </button>
                      </div>
                    </div>
                  ) : isEditing ? (
                    // Edit Profile Mode
                    <form onSubmit={handleProfileSubmit} className="space-y-6">
                      {/* Profile Picture URL */}
                      <div className="border-b pb-6">
                        <h3 className="text-sm font-medium text-gray-700 mb-4">
                          {t('profile.profilePicUrl')}
                        </h3>
                        <FormInput
                          type="url"
                          placeholder={t('profile.profilePicPlaceholder')}
                          value={profileData.profilePic}
                          onChange={(value) =>
                            setProfileData({
                              ...profileData,
                              profilePic: value,
                            })
                          }
                          error={errors.profilePic}
                          disabled={isSubmitting}
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          {t('profile.profilePicHelper')}
                        </p>
                        {profileData.profilePic && (
                          <div className="mt-3 flex justify-center">
                            <img
                              src={profileData.profilePic}
                              alt="Profile preview"
                              className="w-24 h-24 rounded-full object-cover border-2 border-gray-200"
                              onError={(e) => {
                                e.target.style.display = 'none';
                              }}
                            />
                          </div>
                        )}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <FormInput
                          type="text"
                          placeholder={t('profile.firstName')}
                          value={profileData.firstName}
                          onChange={(value) =>
                            setProfileData({ ...profileData, firstName: value })
                          }
                          icon={<User size={20} />}
                          error={errors.firstName}
                          required
                        />
                        <FormInput
                          type="text"
                          placeholder={t('profile.lastName')}
                          value={profileData.lastName}
                          onChange={(value) =>
                            setProfileData({ ...profileData, lastName: value })
                          }
                          icon={<User size={20} />}
                          error={errors.lastName}
                          required
                        />
                      </div>

                      <FormInput
                        type="text"
                        placeholder="Title / Designation (e.g., CEO, VP Engineering)"
                        value={profileData.title}
                        onChange={(value) =>
                          setProfileData({ ...profileData, title: value })
                        }
                        icon={<Briefcase size={20} />}
                        maxLength={100}
                      />

                      <FormInput
                        type="email"
                        placeholder={t('profile.email')}
                        value={profileData.email}
                        onChange={(value) =>
                          setProfileData({ ...profileData, email: value })
                        }
                        icon={<Mail size={20} />}
                        error={errors.email}
                        required
                      />

                      <div className="flex gap-3 pt-4">
                        <Button type="submit" disabled={isSubmitting}>
                          <Save size={18} className="mr-2" />
                          {isSubmitting
                            ? t('profile.saving')
                            : t('profile.saveChanges')}
                        </Button>
                        <button
                          type="button"
                          onClick={() => {
                            setIsEditing(false);
                            setErrors({});
                            // Reset to original data
                            setProfileData({
                              username: user.username,
                              firstName: user.firstName,
                              lastName: user.lastName,
                              email: user.email,
                              profilePic: user.profilePic || '',
                              title: user.title || '',
                            });
                          }}
                          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
                        >
                          <X size={18} />
                          {t('profile.cancel')}
                        </button>
                      </div>
                    </form>
                  ) : (
                    // Change Password Mode
                    <form onSubmit={handlePasswordSubmit} className="space-y-4">
                      <PasswordInput
                        placeholder={t('profile.currentPassword')}
                        value={passwordData.currentPassword}
                        onChange={(value) =>
                          setPasswordData({
                            ...passwordData,
                            currentPassword: value,
                          })
                        }
                        error={errors.currentPassword}
                        required
                      />

                      <PasswordInput
                        placeholder={t('profile.newPassword')}
                        value={passwordData.newPassword}
                        onChange={(value) =>
                          setPasswordData({
                            ...passwordData,
                            newPassword: value,
                          })
                        }
                        error={errors.newPassword}
                        showStrength
                        required
                      />

                      <PasswordInput
                        placeholder={t('profile.confirmPassword')}
                        value={passwordData.confirmPassword}
                        onChange={(value) =>
                          setPasswordData({
                            ...passwordData,
                            confirmPassword: value,
                          })
                        }
                        error={errors.confirmPassword}
                        required
                      />

                      <div className="flex gap-3 pt-4">
                        <Button type="submit" disabled={isSubmitting}>
                          <Lock size={18} className="mr-2" />
                          {isSubmitting
                            ? t('profile.changing')
                            : t('profile.changePassword')}
                        </Button>
                        <button
                          type="button"
                          onClick={() => {
                            setIsChangingPassword(false);
                            setErrors({});
                            setPasswordData({
                              currentPassword: '',
                              newPassword: '',
                              confirmPassword: '',
                            });
                          }}
                          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
                        >
                          <X size={18} />
                          {t('profile.cancel')}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>

              {/* Account Info */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  {t('profile.accountInfo')}
                </h3>
                <div className="space-y-3 text-sm">
                  {/* Company Info */}
                  {user.company ? (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600 flex items-center gap-2">
                        <Building size={16} />
                        Company
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{user.company.name}</span>
                        {user.isCompanyVerified ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs font-medium rounded-full">
                            <ShieldCheck size={12} />
                            Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-orange-100 text-orange-700 text-xs font-medium rounded-full">
                            Pending
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-600 flex items-center gap-2">
                          <Building size={16} />
                          Company
                        </span>
                        <span className="text-gray-400 italic">Not assigned</span>
                      </div>
                      {/* Join Company with Invite Code */}
                      <div className="mt-2 p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <h4 className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
                          <Ticket size={16} />
                          Have an invite code?
                        </h4>
                        <p className="text-xs text-blue-600 mb-3">
                          Enter your company invite code to join and become a verified employee.
                        </p>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={inviteCode}
                            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                            placeholder="Enter invite code"
                            className="flex-1 px-3 py-2 border border-blue-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 uppercase"
                            disabled={isRedeemingCode}
                            maxLength={8}
                          />
                          <button
                            onClick={async () => {
                              if (!inviteCode.trim()) {
                                setToast({ message: 'Please enter an invite code', type: 'error' });
                                return;
                              }
                              setIsRedeemingCode(true);
                              try {
                                await api.redeemInviteCode(inviteCode.trim());
                                setToast({ message: 'Successfully joined company!', type: 'success' });
                                setInviteCode('');
                                // Reload user data
                                window.location.reload();
                              } catch (error) {
                                setToast({ message: error.message || 'Failed to redeem invite code', type: 'error' });
                              } finally {
                                setIsRedeemingCode(false);
                              }
                            }}
                            disabled={isRedeemingCode || !inviteCode.trim()}
                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                          >
                            {isRedeemingCode ? 'Joining...' : 'Join'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      {t('profile.accountStatus')}
                    </span>
                    <span className="font-medium text-green-600">
                      {t('profile.active')}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      {t('profile.memberSince')}
                    </span>
                    <span className="font-medium">
                      {new Date(user.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      {t('profile.lastUpdated')}
                    </span>
                    <span className="font-medium">
                      {new Date(user.updatedAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {/* Danger Zone */}
                <div className="mt-6 pt-6 border-t border-red-200">
                  <h4 className="text-sm font-semibold text-red-600 mb-3 flex items-center gap-2">
                    <AlertTriangle size={18} />
                    Danger Zone
                  </h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Deactivating your account will prevent you from logging in.
                    This action can be reversed by contacting support.
                  </p>
                  <button
                    onClick={() => setShowDeactivateModal(true)}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium flex items-center gap-2"
                  >
                    <AlertTriangle size={16} />
                    Deactivate Account
                  </button>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Deactivate Account Confirmation Modal */}
      {showDeactivateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="text-red-600" size={24} />
              </div>
              <h3 className="text-xl font-bold text-gray-900">
                Deactivate Account?
              </h3>
            </div>

            <div className="mb-6">
              <p className="text-gray-700 mb-3">
                Are you sure you want to deactivate your account? This will:
              </p>
              <ul className="list-disc list-inside text-sm text-gray-600 space-y-1 ml-2">
                <li>Prevent you from logging in</li>
                <li>Hide your profile from other users</li>
                <li>Disable all account features</li>
              </ul>
              <p className="text-sm text-gray-500 mt-3 italic">
                Note: You can contact support to reactivate your account later.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleDeactivateAccount}
                disabled={isDeactivating}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isDeactivating ? 'Deactivating...' : 'Yes, Deactivate'}
              </button>
              <button
                onClick={() => setShowDeactivateModal(false)}
                disabled={isDeactivating}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
