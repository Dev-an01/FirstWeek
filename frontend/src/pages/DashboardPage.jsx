import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Clock, Video, Calendar } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../store/authStore';
import { useUIStore } from '../store/uiStore';
import { useChatStore } from '../store/chatStore';
import { Navbar } from '../components/Navbar/Navbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { Toast } from '../components/ui/Toast';
import { DashboardCard } from '../components/DashboardCard';
import { Button } from '../components/ui/Button';
import * as api from '../services/api';

/**
 * DashboardPage Component
 * Fully responsive dashboard that fits all screen sizes without overflow
 */
export function DashboardPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const { toast, hideToast, sidebarOpen, closeSidebar } = useUIStore();
  const { conversations, fetchConversations } = useChatStore();

  // Data state
  const [meetings, setMeetings] = useState([]);
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(false);
  const [executives, setExecutives] = useState([]);

  // Fetch recent conversations on mount
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Fetch executives for name mapping
  useEffect(() => {
    const fetchExecutives = async () => {
      try {
        const response = await api.getRagProfiles();
        const profiles = response.data?.profiles || [];
        setExecutives(profiles);
      } catch (error) {
        console.error('Failed to load executives:', error);
      }
    };
    fetchExecutives();
  }, []);

  // Fetch scheduled meetings
  useEffect(() => {
    const fetchMeetings = async () => {
      setIsLoadingMeetings(true);
      try {
        const response = await api.getMeetings('pending');
        // axios returns full response object, data is in response.data
        const data = response.data || response;
        setMeetings(data.meetings || []);
      } catch (error) {
        console.error('Failed to load meetings:', error);
      } finally {
        setIsLoadingMeetings(false);
      }
    };
    fetchMeetings();
  }, []);

  return (
    <div className="flex flex-col min-h-screen w-full overflow-x-hidden bg-gradient-to-br from-gray-50 to-gray-100">
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
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
            {/* Welcome Header */}
            <div className="mb-6 lg:mb-8">
              <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-primary">
                {t('dashboard.welcome', {
                  name: user?.firstName || user?.name,
                })}
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                {t('dashboard.subtitle')}
              </p>
            </div>

            {/* Dashboard Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6">
              {/* 1. New Conversation */}
              <div className="bg-white rounded-xl p-5 lg:p-6 shadow-sm hover:shadow-md transition-shadow w-full max-w-full">
                <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center mb-4">
                  <MessageSquare
                    className="text-primary"
                    size={22}
                    aria-hidden="true"
                  />
                </div>
                <h3 className="text-lg font-semibold text-primary mb-2">
                  {t('dashboard.newConversation.title')}
                </h3>
                <div className="space-y-3">
                  <p className="text-sm text-gray-600">
                    {t('dashboard.newConversation.description')}
                  </p>
                  <Button onClick={() => navigate('/chat')} className="w-full">
                    {t('dashboard.newConversation.button')}
                  </Button>
                </div>
              </div>

              {/* 2. Start New Video Chat */}
              <div className="bg-white rounded-xl p-5 lg:p-6 shadow-sm hover:shadow-md transition-shadow w-full max-w-full">
                <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center mb-4">
                  <Video
                    className="text-primary"
                    size={22}
                    aria-hidden="true"
                  />
                </div>
                <h3 className="text-lg font-semibold text-primary mb-2">
                  {t('dashboard.videoChat.title')}
                </h3>
                <div className="space-y-3">
                  <p className="text-sm text-gray-600">
                    {t('dashboard.videoChat.description')}
                  </p>
                  <Button
                    onClick={() => {
                      // Redirect to avatar video interface
                      const avatarUrl = import.meta.env.VITE_AVATAR_VIDEO_URL || 'https://example.invalid';
                      window.location.href = avatarUrl;
                    }}
                    className="w-full"
                  >
                    {t('dashboard.videoChat.button')}
                  </Button>
                </div>
              </div>

              {/* 3. Schedule a Meeting */}
              <div className="bg-white rounded-xl p-5 lg:p-6 shadow-sm hover:shadow-md transition-shadow w-full max-w-full">
                <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center mb-4">
                  <Calendar
                    className="text-primary"
                    size={22}
                    aria-hidden="true"
                  />
                </div>
                <h3 className="text-lg font-semibold text-primary mb-2">
                  {t('dashboard.scheduleMeeting.title')}
                </h3>
                <div className="space-y-3">
                  <p className="text-sm text-gray-600">
                    {t('dashboard.scheduleMeeting.description')}
                  </p>
                  <Button
                    onClick={() => navigate('/invite-meet')}
                    className="w-full"
                  >
                    {t('dashboard.scheduleMeeting.button')}
                  </Button>
                </div>
              </div>

              {/* 4. Recent Activity */}
              <div className="bg-white rounded-xl p-5 lg:p-6 shadow-sm hover:shadow-md transition-shadow w-full max-w-full">
                <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center mb-4">
                  <Clock
                    className="text-primary"
                    size={22}
                    aria-hidden="true"
                  />
                </div>
                <h3 className="text-lg font-semibold text-primary mb-2">
                  {t('dashboard.recentActivity.title')}
                </h3>
                <div className="space-y-2 text-sm text-gray-600">
                  {conversations.length > 0 ? (
                    conversations.slice(0, 4).map((conversation) => (
                      <button
                        key={conversation.id}
                        onClick={() => navigate(`/chat/${conversation.id}`)}
                        className="w-full flex items-center justify-between hover:bg-gray-50 p-2 rounded cursor-pointer transition-colors text-left"
                      >
                        <div className="flex-1 truncate">
                          <span className="truncate block">
                            {conversation.title}
                          </span>
                          <span className="text-xs text-gray-400">
                            {new Date(
                              conversation.lastMessageAt ||
                              conversation.updatedAt
                            ).toLocaleDateString()}
                          </span>
                        </div>
                        <span aria-hidden="true" className="flex-shrink-0 ml-2">
                          ›
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="text-gray-500 text-sm p-2">
                      {t(
                        'dashboard.recentActivity.noActivity',
                        'No recent chats'
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* 5. Upcoming Meetings */}
              <DashboardCard
                title={t('dashboard.upcomingMeetings.title')}
                icon={Calendar}
                className="md:col-span-2 lg:col-span-2"
              >
                {isLoadingMeetings ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-pulse flex items-center gap-2">
                      <div className="w-2 h-2 bg-primary rounded-full" />
                      <div className="w-2 h-2 bg-primary rounded-full" />
                      <div className="w-2 h-2 bg-primary rounded-full" />
                    </div>
                  </div>
                ) : meetings.length > 0 ? (
                  <div className="space-y-3">
                    {meetings.map((meeting) => {
                      // Find executive name from profile_id
                      const executive = executives.find(
                        (exec) => exec.id === meeting.profile_id
                      );
                      const executiveName = executive
                        ? executive.name
                        : meeting.executive || 'Executive';

                      return (
                        <div
                          key={meeting.meeting_id}
                          className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-4 hover:shadow-md transition-all duration-200 border border-gray-200"
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-2">
                                <span className="text-sm font-semibold text-gray-900">
                                  {meeting.platform} with {executiveName}
                                </span>
                                <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">
                                  {meeting.status}
                                </span>
                              </div>
                              <div className="flex items-center gap-1 text-xs text-gray-600">
                                <Calendar size={12} />
                                {new Date(
                                  meeting.scheduled_time.endsWith('Z')
                                    ? meeting.scheduled_time
                                    : `${meeting.scheduled_time}Z`
                                ).toLocaleString()}
                              </div>
                            </div>
                            <div className="flex gap-2 flex-shrink-0">
                              <a
                                href={meeting.meeting_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-4 py-2 text-xs font-medium bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors shadow-sm hover:shadow"
                              >
                                {t('dashboard.upcomingMeetings.join')}
                              </a>
                              <button
                                onClick={async () => {
                                  try {
                                    await api.cancelMeeting(meeting.meeting_id);
                                    // Refresh meetings after cancel
                                    const response =
                                      await api.getMeetings('pending');
                                    const data = response.data || response;
                                    setMeetings(data.meetings || []);
                                  } catch (error) {
                                    console.error(
                                      'Failed to cancel meeting:',
                                      error
                                    );
                                  }
                                }}
                                className="px-4 py-2 text-xs font-medium bg-white text-red-600 rounded-lg hover:bg-red-50 transition-colors shadow-sm border border-red-200"
                              >
                                {t('dashboard.upcomingMeetings.cancel')}
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                      <Calendar className="text-gray-400" size={32} />
                    </div>
                    <p className="text-sm text-gray-600 font-medium">
                      {t('dashboard.upcomingMeetings.noMeetings')}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {t('dashboard.upcomingMeetings.scheduleHelpText')}
                    </p>
                  </div>
                )}
              </DashboardCard>
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
