import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { Navbar } from '../components/Navbar/Navbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { Toast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import * as api from '../services/api';

/**
 * ChatTranscriptionPage Component
 * View full chat transcription
 */
export function ChatTranscriptionPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast, showToast, hideToast, sidebarOpen, closeSidebar } =
    useUIStore();

  const [chat, setChat] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch chat on mount (only if id exists)
  useEffect(() => {
    if (!id) {
      // New conversation - no ID provided
      setIsLoading(false);
      setChat({
        title: 'New Conversation',
        date: new Date().toISOString(),
        transcript: 'Start a new conversation with the AI Avatar...',
      });
      return;
    }

    const fetchChat = async () => {
      setIsLoading(true);
      try {
        const data = await api.getChat(id);
        setChat(data.chat);
      } catch (error) {
        showToast('Failed to load chat transcription', 'error');
      } finally {
        setIsLoading(false);
      }
    };
    fetchChat();
  }, [id, showToast]);

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
            {/* Back Button */}
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 text-primary hover:text-primary-dark mb-6 focus:outline-none focus:ring-2 focus:ring-primary rounded px-2 py-1"
            >
              <ArrowLeft size={20} />
              <span>Back to Dashboard</span>
            </button>

            {isLoading ? (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent mx-auto" />
                <p className="text-gray-600 mt-4">
                  Loading chat transcription...
                </p>
              </div>
            ) : chat ? (
              <div className="max-w-4xl mx-auto">
                <div className="bg-white rounded-2xl shadow-lg p-6 sm:p-8">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center flex-shrink-0">
                      <FileText className="text-primary" size={24} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h1 className="text-2xl font-bold text-primary mb-2">
                        {chat.title}
                      </h1>
                      <p className="text-sm text-gray-500">
                        Date:{' '}
                        {new Date(chat.date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </p>
                    </div>
                  </div>

                  <div className="prose max-w-none">
                    <div className="bg-gray-50 rounded-xl p-6 border border-gray-200">
                      <h2 className="text-lg font-semibold text-gray-900 mb-4">
                        Transcript
                      </h2>
                      <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                        {chat.transcript}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex gap-3">
                    <Button
                      onClick={() => navigate('/dashboard')}
                      variant="outline"
                    >
                      Back to Dashboard
                    </Button>
                    <Button onClick={() => window.print()}>
                      Print Transcript
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-gray-600">Chat transcription not found</p>
                <Button onClick={() => navigate('/dashboard')} className="mt-4">
                  Back to Dashboard
                </Button>
              </div>
            )}
          </div>
        </main>
      </div>

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
