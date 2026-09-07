import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useUIStore } from '../store/uiStore';
import { Navbar } from '../components/Navbar/Navbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { Button } from '../components/ui/Button';
import { Toast } from '../components/ui/Toast';
import * as api from '../services/api';
import { sanitizeInput } from '../utils/sanitizer';

/**
 * InviteMeetPage Component
 * Page for inviting AI executives to meetings
 */
export function InviteMeetPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { toast, showToast, hideToast, sidebarOpen, closeSidebar } =
    useUIStore();

  // Form state
  const [executive, setExecutive] = useState('');
  const [platform, setPlatform] = useState('');
  const [language, setLanguage] = useState('en'); // Default to English
  const [meetLink, setMeetLink] = useState('');
  const [meetDate, setMeetDate] = useState('');
  const [meetTime, setMeetTime] = useState('');
  const [isInstant, setIsInstant] = useState(false); // Toggle for instant meeting

  // Data state
  const [executives, setExecutives] = useState([]);
  const [scheduledMeetings, setScheduledMeetings] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  // Fetch executives (RAG profiles) on mount
  useEffect(() => {
    const fetchExecutives = async () => {
      setIsLoading(true);
      try {
        const response = await api.getRagProfiles();
        // API returns: { success, data: { profiles, count } }
        const profiles = response.data?.profiles || [];
        setExecutives(profiles);
      } catch (error) {
        console.error('Failed to load executives:', error);
        showToast('Failed to load executives', 'error');
      } finally {
        setIsLoading(false);
      }
    };
    fetchExecutives();
  }, [showToast]);

  // Fetch scheduled meetings
  const fetchScheduledMeetings = async () => {
    try {
      const response = await api.getMeetings('pending');
      // axios returns full response object, data is in response.data
      const data = response.data || response;
      setScheduledMeetings(data.meetings || []);
    } catch (error) {
      console.error('Failed to load meetings:', error);
    }
  };

  // Fetch on mount
  useEffect(() => {
    fetchScheduledMeetings();
  }, []);

  /**
   * Validate URL format
   */
  const validateURL = (url) => {
    const urlRegex =
      /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/;
    return urlRegex.test(url);
  };

  /**
   * Validate date is not in the past
   */
  const validateDateTime = (date, time) => {
    const selectedDateTime = new Date(`${date}T${time}`);
    const now = new Date();
    return selectedDateTime > now;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});

    // Validation
    const newErrors = {};
    if (!executive) newErrors.executive = 'Please select an AI executive';
    if (!platform) newErrors.platform = 'Please select a platform';
    if (!meetLink) {
      newErrors.meetLink = 'Meeting link is required';
    } else if (!validateURL(meetLink)) {
      newErrors.meetLink = 'Please enter a valid URL';
    }

    // Only validate date/time for scheduled meetings
    if (!isInstant) {
      if (!meetDate) newErrors.meetDate = 'Meeting date is required';
      if (!meetTime) newErrors.meetTime = 'Meeting time is required';

      if (meetDate && meetTime && !validateDateTime(meetDate, meetTime)) {
        newErrors.meetDate = 'Meeting date/time cannot be in the past';
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Submit
    setIsSubmitting(true);
    try {
      if (isInstant) {
        // Create instant meeting
        const meetingData = {
          executive: sanitizeInput(executive),
          platform: sanitizeInput(platform),
          language: sanitizeInput(language),
          link: sanitizeInput(meetLink),
        };

        await api.createInstantMeeting(meetingData);

        showToast(
          'Bot is joining the meeting now! 🚀',
          'success'
        );
      } else {
        // Create scheduled meeting
        const localDateTime = new Date(`${meetDate}T${meetTime}`);
        const utcDate = localDateTime.toISOString().split('T')[0];
        const utcTime = localDateTime.toISOString().split('T')[1].substring(0, 5);

        const meetingData = {
          executive: sanitizeInput(executive),
          platform: sanitizeInput(platform),
          language: sanitizeInput(language),
          link: sanitizeInput(meetLink),
          date: utcDate,
          time: utcTime,
        };

        await api.createMeeting(meetingData);

        showToast(
          'Meeting scheduled! Bot will join 3 minutes before start time.',
          'success'
        );
      }

      // Refresh meetings list
      fetchScheduledMeetings();

      // Reset form
      setTimeout(() => {
        setExecutive('');
        setPlatform('');
        setLanguage('en');
        setMeetLink('');
        setMeetDate('');
        setMeetTime('');
        setIsInstant(false);
        navigate('/dashboard');
      }, 1500);
    } catch (error) {
      showToast(error.message || t('inviteMeet.inviteFailed'), 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Check if form is valid
  const isFormValid = isInstant
    ? executive && platform && meetLink && validateURL(meetLink)
    : executive &&
    platform &&
    meetLink &&
    meetDate &&
    meetTime &&
    validateURL(meetLink) &&
    validateDateTime(meetDate, meetTime);

  return (
    <div className="flex flex-col min-h-screen w-full overflow-x-hidden bg-gradient-to-br from-gray-50 to-gray-100">
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => hideToast()}
        />
      )}

      {/* Navbar - Full Width at Top */}
      <Navbar />

      {/* Content Area with Sidebar */}
      <div className="flex flex-1 w-full overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content */}
        <main
          className="flex-1 w-full overflow-x-hidden overflow-y-auto"
          role="main"
        >
          <div className="w-full max-w-full px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
            {/* Page Header */}
            <div className="mb-6 lg:mb-8 text-center">
              <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-primary">
                {t('inviteMeet.title')}
              </h1>
              <p className="text-sm text-gray-600 mt-2">
                {t('inviteMeet.subtitle')}
              </p>
            </div>

            {/* Two-column layout: Form + Meetings */}
            <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column - Form Card */}
              <div className="bg-white rounded-2xl shadow-lg p-6 sm:p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center">
                    <Calendar className="text-primary" size={24} />
                  </div>
                  <h2 className="text-lg font-semibold text-primary">
                    {t('inviteMeet.meetingDetails')}
                  </h2>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                  {/* AI Executive Dropdown */}
                  <div>
                    <label
                      htmlFor="executive"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      {t('inviteMeet.aiExecutive')} *
                    </label>
                    <select
                      id="executive"
                      value={executive}
                      onChange={(e) => setExecutive(e.target.value)}
                      className={`w-full px-4 py-2.5 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${errors.executive
                        ? 'border-red-400'
                        : 'border-gray-200 focus:border-primary'
                        }`}
                      disabled={isLoading}
                    >
                      <option value="">
                        {t('inviteMeet.selectExecutive')}
                      </option>
                      {executives.map((exec) => (
                        <option key={exec.id} value={exec.id}>
                          {exec.name} - {exec.title}
                        </option>
                      ))}
                    </select>
                    {errors.executive && (
                      <p className="text-red-500 text-sm mt-1">
                        {errors.executive}
                      </p>
                    )}
                  </div>

                  {/* Platform Dropdown */}
                  <div>
                    <label
                      htmlFor="platform"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      {t('inviteMeet.platform')} *
                    </label>
                    <select
                      id="platform"
                      value={platform}
                      onChange={(e) => setPlatform(e.target.value)}
                      className={`w-full px-4 py-2.5 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${errors.platform
                        ? 'border-red-400'
                        : 'border-gray-200 focus:border-primary'
                        }`}
                    >
                      <option value="">{t('inviteMeet.selectPlatform')}</option>
                      <option value="Google Meet">Google Meet</option>
                      <option value="Zoom">Zoom</option>
                      <option value="Microsoft Teams">Microsoft Teams</option>
                    </select>
                    {errors.platform && (
                      <p className="text-red-500 text-sm mt-1">
                        {errors.platform}
                      </p>
                    )}
                  </div>

                  {/* Language Dropdown */}
                  <div>
                    <label
                      htmlFor="language"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Language *
                    </label>
                    <select
                      id="language"
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full px-4 py-2.5 bg-white border-2 border-gray-200 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 focus:border-primary"
                    >
                      <option value="en">English</option>
                      <option value="ja">Japanese</option>
                    </select>
                  </div>

                  {/* Meeting Link */}
                  <div>
                    <label
                      htmlFor="meetLink"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      {t('inviteMeet.meetingLink')} *
                    </label>
                    <input
                      type="url"
                      id="meetLink"
                      value={meetLink}
                      onChange={(e) => setMeetLink(e.target.value)}
                      placeholder={t('inviteMeet.meetingLinkPlaceholder')}
                      className={`w-full px-4 py-2.5 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${errors.meetLink
                        ? 'border-red-400'
                        : 'border-gray-200 focus:border-primary'
                        }`}
                    />
                    {errors.meetLink && (
                      <p className="text-red-500 text-sm mt-1">
                        {errors.meetLink}
                      </p>
                    )}
                  </div>

                  {/* Instant Meeting Toggle */}
                  <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-4">
                    <label className="flex items-center justify-between cursor-pointer">
                      <div className="flex items-center gap-3">
                        <div className="flex-shrink-0">
                          <span className="text-2xl">🚀</span>
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-gray-900">
                            Instant Meeting
                          </div>
                          <div className="text-xs text-gray-600">
                            Bot joins immediately (no scheduling)
                          </div>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={isInstant}
                        onChange={(e) => setIsInstant(e.target.checked)}
                        className="w-5 h-5 text-primary bg-white border-gray-300 rounded focus:ring-primary focus:ring-2"
                      />
                    </label>
                  </div>

                  {/* Meeting Date - Only show for scheduled meetings */}
                  {!isInstant && (
                    <div>
                      <label
                        htmlFor="meetDate"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        {t('inviteMeet.meetingDate')} *
                      </label>
                      <input
                        type="date"
                        id="meetDate"
                        value={meetDate}
                        onChange={(e) => setMeetDate(e.target.value)}
                        min={new Date().toISOString().split('T')[0]}
                        className={`w-full px-4 py-2.5 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${errors.meetDate
                          ? 'border-red-400'
                          : 'border-gray-200 focus:border-primary'
                          }`}
                      />
                      {errors.meetDate && (
                        <p className="text-red-500 text-sm mt-1">
                          {errors.meetDate}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Meeting Time - Only show for scheduled meetings */}
                  {!isInstant && (
                    <div>
                      <label
                        htmlFor="meetTime"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        {t('inviteMeet.meetingTime')} *
                      </label>
                      <input
                        type="time"
                        id="meetTime"
                        value={meetTime}
                        onChange={(e) => setMeetTime(e.target.value)}
                        className={`w-full px-4 py-2.5 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${errors.meetTime
                          ? 'border-red-400'
                          : 'border-gray-200 focus:border-primary'
                          }`}
                      />
                      {errors.meetTime && (
                        <p className="text-red-500 text-sm mt-1">
                          {errors.meetTime}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Submit Button */}
                  <Button type="submit" disabled={!isFormValid || isSubmitting}>
                    {isSubmitting
                      ? t('inviteMeet.sendingInvite')
                      : t('inviteMeet.sendInvite')}
                  </Button>

                  <p className="text-xs text-gray-500 text-center mt-4">
                    {t('inviteMeet.allFieldsRequired')}
                  </p>
                </form>
              </div>

              {/* Right Column - Scheduled Meetings List */}
              <div className="bg-white rounded-2xl shadow-lg p-6 sm:p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center">
                    <Calendar className="text-primary" size={24} />
                  </div>
                  <h2 className="text-lg font-semibold text-primary">
                    {t('inviteMeet.upcomingMeetingsTitle', {
                      count: scheduledMeetings.length,
                    })}
                  </h2>
                </div>

                {scheduledMeetings.length > 0 ? (
                  <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                    {scheduledMeetings.map((meeting) => {
                      // Find executive name from profile_id
                      // eslint-disable-next-line
                      const executive = executives.find(
                        (exec) => exec.id === meeting.profile_id
                      );
                      const executiveName = executive
                        ? executive.name
                        : meeting.executive || 'Executive';

                      return (
                        <div
                          key={meeting.meeting_id}
                          className="bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-semibold text-gray-900 mb-1">
                                {meeting.platform} with {executiveName}
                              </div>
                              <div className="text-xs text-gray-600 flex items-center gap-1">
                                <Calendar size={12} />
                                {new Date(
                                  meeting.scheduled_time.endsWith('Z')
                                    ? meeting.scheduled_time
                                    : `${meeting.scheduled_time}Z`
                                ).toLocaleString()}
                              </div>
                              <div className="mt-2">
                                <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded">
                                  {meeting.status}
                                </span>
                              </div>
                            </div>
                            <div className="flex flex-col gap-2">
                              <a
                                href={meeting.meeting_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 text-xs font-medium bg-primary text-white rounded-md hover:bg-primary-dark transition-colors text-center"
                              >
                                {t('inviteMeet.join')}
                              </a>
                              <button
                                onClick={async () => {
                                  try {
                                    await api.cancelMeeting(meeting.meeting_id);
                                    showToast('Meeting cancelled', 'success');
                                    fetchScheduledMeetings();
                                  } catch (error) {
                                    showToast(
                                      'Failed to cancel meeting',
                                      'error'
                                    );
                                  }
                                }}
                                className="px-3 py-1.5 text-xs font-medium bg-red-50 text-red-600 rounded-md hover:bg-red-100 transition-colors"
                              >
                                {t('inviteMeet.cancelMeeting')}
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                      <Calendar className="text-gray-400" size={32} />
                    </div>
                    <p className="text-sm text-gray-500 mb-1">
                      {t('inviteMeet.noUpcomingMeetings')}
                    </p>
                    <p className="text-xs text-gray-400">
                      {t('inviteMeet.scheduleHelpText')}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
