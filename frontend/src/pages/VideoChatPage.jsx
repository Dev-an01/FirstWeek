import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Video,
  Mic,
  MicOff,
  VideoOff,
  PhoneOff,
  Loader2,
  User,
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { useAvatarStore } from '../store/avatarStore';
import { useUIStore } from '../store/uiStore';
import { Navbar } from '../components/Navbar/Navbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { Toast } from '../components/ui/Toast';
import Modal from '../components/ui/Modal';

/**
 * VideoChatPage Component
 * AI-powered video chat interface with real-time avatar streaming
 */
export function VideoChatPage() {
  const location = useLocation();
  const { user } = useAuthStore();
  const { sidebarOpen, closeSidebar } = useUIStore();
  const {
    init,
    connect,
    disconnect,
    isConnected,
    isLoading,
    videoStream,
    error: avatarError,
    avatars,
  } = useAvatarStore();

  const [toast, setToast] = useState(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const videoRef = useRef(null);
  const hasAutoConnected = useRef(false);

  // Initialize store on mount
  useEffect(() => {
    init();
    return () => {
      disconnect();
    };
  }, [init, disconnect]);

  // Handle errors
  useEffect(() => {
    if (avatarError) {
      setToast({ message: avatarError, type: 'error' });
    }
  }, [avatarError]);

  // Attach video stream
  useEffect(() => {
    if (videoRef.current && videoStream) {
      videoRef.current.srcObject = videoStream;
    }
  }, [videoStream]);

  // Auto-connect if avatar passed from dashboard
  const handleConnect = async (avatarName) => {
    setIsModalOpen(false);
    setToast({ message: `Connecting to ${avatarName}...`, type: 'info' });
    await connect(avatarName);
  };
  useEffect(() => {
    const selectedAvatar = location.state?.selectedAvatar;

    if (
      selectedAvatar &&
      avatars.length > 0 &&
      !isConnected &&
      !isLoading &&
      !hasAutoConnected.current
    ) {
      handleConnect(selectedAvatar);
      hasAutoConnected.current = true;
      // Clear state so refresh doesn't re-trigger if we wanted to stop
      window.history.replaceState({}, document.title);
    } else if (
      !selectedAvatar &&
      avatars.length > 0 &&
      !isConnected &&
      !isLoading &&
      !hasAutoConnected.current
    ) {
      // If no avatar passed, show modal
      setIsModalOpen(true);
    }
  }, [avatars, isConnected, isLoading, location.state]);

  const handleEndCall = () => {
    disconnect();
    setToast({ message: 'Call ended', type: 'success' });
    // Re-open modal to allow selecting another avatar
    setTimeout(() => setIsModalOpen(true), 1000);
  };

  return (
    <div className="flex flex-col min-h-screen w-full overflow-x-hidden bg-gradient-to-br from-gray-50 to-gray-100">
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Navbar */}
      <Navbar />

      <div className="flex flex-1 w-full overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content */}
        <main className="flex-1 w-full overflow-x-hidden overflow-y-auto p-4 sm:p-6 lg:p-8 flex flex-col items-center justify-center">
          <div className="w-full max-w-5xl">
            {/* Header */}
            <div className="mb-6 text-center">
              <h1 className="text-2xl font-bold text-primary">AI Video Chat</h1>
              <p className="text-gray-600">
                Real-time conversation with your digital assistant
              </p>
            </div>

            {/* Video Container */}
            <div className="aspect-video bg-white rounded-2xl shadow-lg overflow-hidden relative border border-gray-200">
              {!isConnected && !isLoading ? (
                /* Before Call / Loading Avatars */
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-gray-50">
                  <div className="w-20 h-20 bg-primary-light rounded-full flex items-center justify-center mb-6">
                    <Video size={40} className="text-primary" />
                  </div>
                  <h2 className="text-xl font-semibold text-gray-800 mb-2">
                    {avatars.length === 0
                      ? 'Loading Avatars...'
                      : 'Select an Avatar'}
                  </h2>
                  <p className="text-gray-500 mb-6 max-w-md">
                    {avatars.length === 0
                      ? 'Please wait while we fetch available avatars...'
                      : 'Choose an AI assistant to start your session.'}
                  </p>
                  {avatars.length === 0 ? (
                    <Loader2 size={32} className="animate-spin text-primary" />
                  ) : (
                    <button
                      onClick={() => setIsModalOpen(true)}
                      className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors"
                    >
                      Open Avatar Selection
                    </button>
                  )}
                </div>
              ) : (
                /* During Call or Connecting */
                <div className="absolute inset-0 bg-black">
                  {/* Main Video (AI) */}
                  <div className="w-full h-full flex items-center justify-center relative">
                    {isLoading ? (
                      <div className="flex flex-col items-center text-white">
                        <Loader2
                          size={48}
                          className="animate-spin mb-4 text-primary"
                        />
                        <p>Connecting to Avatar...</p>
                      </div>
                    ) : (
                      // eslint-disable-next-line jsx-a11y/media-has-caption
                      <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        className="w-full h-full object-cover"
                      />
                    )}

                    {/* Overlay Info */}
                    {isConnected && (
                      <div className="absolute top-4 left-4 bg-black bg-opacity-50 px-4 py-2 rounded-full z-10 backdrop-blur-sm">
                        <p className="text-white text-sm flex items-center gap-2">
                          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                          Live Session
                        </p>
                      </div>
                    )}
                  </div>

                  {/* User Video (Picture-in-Picture) */}
                  <div className="absolute bottom-4 right-4 w-32 h-24 sm:w-48 sm:h-36 bg-gray-800 rounded-lg shadow-lg overflow-hidden border border-gray-700 z-20">
                    {isVideoOff ? (
                      <div className="w-full h-full flex items-center justify-center bg-gray-900">
                        <VideoOff size={32} className="text-gray-500" />
                      </div>
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center">
                        <p className="text-white text-sm font-medium">
                          {user?.firstName || 'You'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Controls */}
            {(isConnected || isLoading) && (
              <div className="mt-8 flex justify-center gap-6">
                <button
                  onClick={() => setIsMuted(!isMuted)}
                  className={`w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-primary ${
                    isMuted
                      ? 'bg-red-500 hover:bg-red-600 text-white'
                      : 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-200'
                  }`}
                  aria-label={isMuted ? 'Unmute' : 'Mute'}
                  disabled={isLoading}
                >
                  {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
                </button>

                <button
                  onClick={() => setIsVideoOff(!isVideoOff)}
                  className={`w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-primary ${
                    isVideoOff
                      ? 'bg-red-500 hover:bg-red-600 text-white'
                      : 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-200'
                  }`}
                  aria-label={isVideoOff ? 'Turn video on' : 'Turn video off'}
                  disabled={isLoading}
                >
                  {isVideoOff ? <VideoOff size={24} /> : <Video size={24} />}
                </button>

                <button
                  onClick={handleEndCall}
                  className="w-14 h-14 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-red-500"
                  aria-label="End call"
                  disabled={isLoading}
                >
                  <PhoneOff size={24} />
                </button>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Avatar Selection Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Select an AI Assistant"
      >
        <div className="grid grid-cols-1 gap-4">
          {avatars.map((avatar) => (
            <button
              key={avatar}
              onClick={() => handleConnect(avatar)}
              className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors group"
            >
              <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center mr-4 group-hover:bg-primary group-hover:text-white transition-colors">
                <User
                  size={24}
                  className="text-primary group-hover:text-white"
                />
              </div>
              <div className="text-left">
                <h4 className="font-semibold text-gray-900 capitalize">
                  {avatar}
                </h4>
                <p className="text-sm text-gray-500">AI Assistant</p>
              </div>
            </button>
          ))}
          {avatars.length === 0 && (
            <p className="text-center text-gray-500 py-4">
              No avatars available
            </p>
          )}
        </div>
      </Modal>

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
