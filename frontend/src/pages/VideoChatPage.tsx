import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Video, Mic, MicOff, VideoOff, PhoneOff, ArrowLeft } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { Toast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';

/**
 * VideoChatPage Component
 * AI-powered video chat interface
 */
export const VideoChatPage = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [toast, setToast] = useState(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isCallActive, setIsCallActive] = useState(false);

  const handleStartCall = () => {
    setIsCallActive(true);
    setToast({ message: 'Starting video call...', type: 'success' });
  };

  const handleEndCall = () => {
    setIsCallActive(false);
    setToast({ message: 'Call ended', type: 'success' });
    setTimeout(() => navigate('/dashboard'), 1500);
  };

  return (
    <div className="min-h-screen w-full overflow-x-hidden bg-gray-900 flex flex-col">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 sm:px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-white hover:text-gray-300 transition-colors focus:outline-none focus:ring-2 focus:ring-white rounded px-2 py-1"
          >
            <ArrowLeft size={20} />
            <span className="hidden sm:inline">Back to Dashboard</span>
          </button>
          <h1 className="text-white font-semibold">AI Video Chat</h1>
          <div className="w-20"></div> {/* Spacer for centering */}
        </div>
      </div>

      {/* Video Area */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-6xl">
          <div className="aspect-video bg-gray-800 rounded-2xl shadow-2xl overflow-hidden relative">
            {!isCallActive ? (
              /* Before Call */
              <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
                <div className="w-20 h-20 sm:w-24 sm:h-24 bg-primary rounded-full flex items-center justify-center mb-6">
                  <Video size={40} className="text-white" />
                </div>
                <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                  Ready to Start?
                </h2>
                <p className="text-gray-400 mb-8 max-w-md">
                  Begin your AI-powered video conversation with an intelligent virtual assistant
                </p>
                <Button onClick={handleStartCall} className="px-8">
                  Start Video Call
                </Button>
              </div>
            ) : (
              /* During Call */
              <div className="absolute inset-0">
                {/* Main Video (AI) */}
                <div className="w-full h-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-24 h-24 sm:w-32 sm:h-32 bg-white bg-opacity-20 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Video size={48} className="text-white" />
                    </div>
                    <p className="text-white text-xl sm:text-2xl font-semibold">AI Assistant</p>
                    <p className="text-white text-opacity-80 text-sm mt-2">Connected</p>
                  </div>
                </div>

                {/* User Video (Picture-in-Picture) */}
                <div className="absolute bottom-4 right-4 w-32 h-24 sm:w-48 sm:h-36 bg-gray-700 rounded-lg shadow-lg overflow-hidden">
                  {isVideoOff ? (
                    <div className="w-full h-full flex items-center justify-center">
                      <VideoOff size={32} className="text-gray-400" />
                    </div>
                  ) : (
                    <div className="w-full h-full bg-gradient-to-br from-gray-600 to-gray-800 flex items-center justify-center">
                      <p className="text-white text-sm">{user?.name}</p>
                    </div>
                  )}
                </div>

                {/* Call Info */}
                <div className="absolute top-4 left-4 bg-black bg-opacity-50 px-4 py-2 rounded-full">
                  <p className="text-white text-sm">Call Active</p>
                </div>
              </div>
            )}
          </div>

          {/* Controls */}
          {isCallActive && (
            <div className="mt-6 flex justify-center gap-4">
              <button
                onClick={() => setIsMuted(!isMuted)}
                className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-white ${
                  isMuted ? 'bg-red-500 hover:bg-red-600' : 'bg-gray-700 hover:bg-gray-600'
                }`}
                aria-label={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted ? <MicOff size={24} className="text-white" /> : <Mic size={24} className="text-white" />}
              </button>

              <button
                onClick={() => setIsVideoOff(!isVideoOff)}
                className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-white ${
                  isVideoOff ? 'bg-red-500 hover:bg-red-600' : 'bg-gray-700 hover:bg-gray-600'
                }`}
                aria-label={isVideoOff ? 'Turn video on' : 'Turn video off'}
              >
                {isVideoOff ? <VideoOff size={24} className="text-white" /> : <Video size={24} className="text-white" />}
              </button>

              <button
                onClick={handleEndCall}
                className="w-14 h-14 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-white"
                aria-label="End call"
              >
                <PhoneOff size={24} className="text-white" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Footer Info */}
      <div className="bg-gray-800 border-t border-gray-700 px-4 py-3 text-center">
        <p className="text-gray-400 text-sm">
          This is a demo video chat interface. In production, integrate with WebRTC or a video SDK.
        </p>
      </div>
    </div>
  );
};