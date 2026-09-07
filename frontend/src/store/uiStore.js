/**
 * UI Store - Zustand
 * Manages global UI state (sidebar, modals, toasts, etc.)
 */
import { create } from 'zustand';

export const useUIStore = create((set) => ({
  // Sidebar state
  sidebarOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  openSidebar: () => set({ sidebarOpen: true }),
  closeSidebar: () => set({ sidebarOpen: false }),
  setSidebarOpen: (isOpen) => set({ sidebarOpen: isOpen }),

  // Toast notification state
  toast: null,
  showToast: (message, type = 'info') =>
    set({ toast: { message, type, id: Date.now() } }),
  showSuccessToast: (message) =>
    set({ toast: { message, type: 'success', id: Date.now() } }),
  showErrorToast: (message) =>
    set({ toast: { message, type: 'error', id: Date.now() } }),
  showWarningToast: (message) =>
    set({ toast: { message, type: 'warning', id: Date.now() } }),
  showInfoToast: (message) =>
    set({ toast: { message, type: 'info', id: Date.now() } }),
  hideToast: () => set({ toast: null }),

  // Modal states (can be extended)
  activeModal: null,
  openModal: (modalName) => set({ activeModal: modalName }),
  closeModal: () => set({ activeModal: null }),

  // Loading states
  globalLoading: false,
  setGlobalLoading: (isLoading) => set({ globalLoading: isLoading }),
}));
