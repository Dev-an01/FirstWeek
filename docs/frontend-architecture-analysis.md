# Frontend Architecture Analysis

**Date:** February 2026
**Project:** AI Officer Frontend
**Path:** `D:\ai officer\frontend`

---

## 1. Tech Stack

| Category | Technology | Version |
|----------|------------|---------|
| **Framework** | React | 18.3.1 |
| **Build Tool** | Vite | 5.4.0 |
| **State Management** | Zustand | 5.0.8 |
| **Routing** | React Router | 6.26.0 |
| **Styling** | Tailwind CSS | 3.4.10 |
| **HTTP Client** | Axios | 1.12.2 |
| **Real-time** | Socket.IO | 4.7.2 |
| **i18n** | i18next | 25.6.0 |
| **Icons** | Lucide React | 0.263.1 |
| **Markdown** | react-markdown | 10.1.0 |
| **Testing** | Jest + Playwright | 29.7.0 / 1.47.0 |

---

## 2. Design System

### 2.1 Color Palette

```
Primary Colors:
├── #2D2654 (primary DEFAULT)    - Brand color, buttons, active states
├── #3d3564 (primary-dark)       - Hover states, darker accents
└── #E8E6F0 (primary-light)      - Light backgrounds, icon containers

Extended (Tailwind defaults):
├── Grays: gray-50 to gray-900   - Text, backgrounds, borders
├── Blues: blue-500, blue-600    - Links, info states
├── Greens: green-500, green-600 - Success states
├── Reds: red-400 to red-600     - Error states
└── Yellows/Oranges              - Warning states
```

### 2.2 Typography

| Size | Tailwind Class | Usage |
|------|----------------|-------|
| Extra Large | text-2xl, text-3xl | Page headings |
| Large | text-lg | Card titles, section headers |
| Base | text-base | Body copy (default) |
| Small | text-sm | Labels, metadata |
| Extra Small | text-xs | Timestamps, minor text |

**Font Weights:** font-bold, font-semibold, font-medium

### 2.3 Spacing & Layout

- **Padding:** p-1 to p-6, px-*, py-*
- **Margins:** m-1 to m-8, mx-auto
- **Gaps:** gap-1 to gap-4
- **Border Radius:** rounded-sm, rounded-lg, rounded-xl, rounded-full
- **Shadows:** shadow-sm, shadow-md, shadow-lg, shadow-2xl

### 2.4 Breakpoints

| Breakpoint | Size | Usage |
|------------|------|-------|
| Mobile | < 640px | Default styles |
| sm | ≥ 640px | Small tablets |
| md | ≥ 768px | Tablets |
| lg | ≥ 1024px | Desktops |

---

## 3. Project Structure

```
frontend/
├── public/                     # Static assets
├── src/
│   ├── components/
│   │   ├── ui/                 # Reusable UI components
│   │   │   ├── Button.jsx
│   │   │   ├── FormInput.jsx
│   │   │   ├── PasswordInput.jsx
│   │   │   ├── Modal.jsx
│   │   │   ├── Toast.jsx
│   │   │   └── ImageUpload.jsx
│   │   │
│   │   ├── Chat/               # Chat feature components
│   │   │   ├── MessageBubble.jsx
│   │   │   ├── MessageInput.jsx
│   │   │   ├── MessageList.jsx
│   │   │   ├── ConversationList.jsx
│   │   │   ├── ConversationItem.jsx
│   │   │   ├── ConversationHeader.jsx
│   │   │   ├── ExecutiveSelector.jsx
│   │   │   ├── PathSelector.jsx
│   │   │   ├── TTSToggle.jsx
│   │   │   ├── EmptyState.jsx
│   │   │   └── ChatSidebarContent.jsx
│   │   │
│   │   ├── Auth/
│   │   │   └── ProtectedRoute.jsx
│   │   ├── Navbar/
│   │   │   └── Navbar.jsx
│   │   ├── Sidebar/
│   │   │   └── Sidebar.jsx
│   │   ├── LanguageToggle/
│   │   ├── EmailVerification/
│   │   ├── DashboardCard.jsx
│   │   └── PageLoader.jsx
│   │
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── SignupPage.jsx
│   │   ├── ForgotPasswordPage.jsx
│   │   ├── ResetPasswordPage.jsx
│   │   ├── DashboardPage.jsx
│   │   ├── ChatPage.jsx
│   │   ├── ProfilePage.jsx
│   │   ├── InviteMeetPage.jsx
│   │   ├── VideoChatPage.tsx
│   │   └── ChatTranscriptionPage.jsx
│   │
│   ├── store/                  # Zustand state management
│   │   ├── authStore.js
│   │   ├── chatStore.js
│   │   ├── uiStore.js
│   │   └── avatarStore.js
│   │
│   ├── services/
│   │   ├── api.js              # Axios client with interceptors
│   │   └── socket.js           # Socket.IO manager
│   │
│   ├── hooks/
│   │   ├── useDebounce.js
│   │   └── useVoiceInput.js
│   │
│   ├── utils/
│   │   ├── sanitizer.js        # XSS prevention
│   │   ├── validators.js       # Form validation
│   │   ├── cookieUtils.js
│   │   ├── logger.js
│   │   └── audioManager.js
│   │
│   ├── i18n/
│   │   ├── config.js
│   │   └── locales/
│   │       ├── en.json
│   │       └── ja.json
│   │
│   ├── styles/
│   │   └── index.css           # Tailwind imports + global styles
│   │
│   ├── App.jsx                 # Router configuration
│   └── main.jsx                # Entry point
│
├── Configuration:
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── jest.config.cjs
│   ├── babel.config.cjs
│   ├── playwright.config.js
│   ├── .eslintrc.cjs
│   └── .prettierrc.cjs
│
├── index.html
├── package.json
└── Dockerfile
```

---

## 4. Route Structure

### 4.1 Public Routes (Eager-loaded)
```
/login              → LoginPage
/signup             → SignupPage
/forgot-password    → ForgotPasswordPage
/reset-password     → ResetPasswordPage
```

### 4.2 Protected Routes (Lazy-loaded)
```
/dashboard          → DashboardPage
/chat/:conversationId? → ChatPage
/profile            → ProfilePage
/invite-meet        → InviteMeetPage
/videochat          → VideoChatPage
/transcription/:id? → ChatTranscriptionPage
```

### 4.3 Fallbacks
- `/` → Redirects to `/login`
- `/*` → Redirects to `/login`

---

## 5. State Management (Zustand)

### 5.1 Auth Store (`authStore.js`)

**State:**
```javascript
{
  user: null | Object,
  isLoading: boolean,
  isAuthenticated: boolean
}
```

**Actions:**
- `checkAuth()` - Validate session
- `login(identifier, password)` - Authenticate
- `signup(userData)` - Register
- `logout()` - Clear session + disconnect socket
- `logoutAllDevices()` - Force logout everywhere
- `refreshToken()` - Token refresh

**Features:**
- Cross-tab sync via BroadcastChannel API
- Auto auth check on initialization
- Account deactivation detection

### 5.2 Chat Store (`chatStore.js`)

**State Sections:**
```javascript
{
  // Conversations
  conversations: [],
  currentConversation: null,
  conversationsPagination: { total, limit: 20, offset, hasMore },

  // Messages
  messages: [],
  messagesPagination: { total, limit: 50, offset, hasMore },

  // Streaming
  streamingMessage: null,
  isStreaming: boolean,

  // RAG
  ragProfiles: [],
  selectedProfile: null,

  // TTS
  ttsEnabled: boolean,
  audioPlaying: boolean
}
```

**Key Patterns:**
- Optimistic UI updates for messages
- Cached RAG profiles with force-refresh
- Streaming message accumulation

### 5.3 UI Store (`uiStore.js`)

```javascript
{
  sidebarOpen: boolean,
  toast: { message, type, id } | null,
  activeModal: string | null,
  globalLoading: boolean
}
```

### 5.4 Avatar Store (`avatarStore.js`)

WebRTC session management for video avatar features.

---

## 6. Component Library

### 6.1 UI Components (Reusable)

| Component | Props | Features |
|-----------|-------|----------|
| **Button** | children, onClick, type, variant, disabled, className | primary/secondary/outline variants |
| **FormInput** | type, placeholder, value, onChange, icon, error, required | Icon support, validation |
| **PasswordInput** | placeholder, value, onChange, error, showStrength | Show/hide toggle, strength indicator |
| **Modal** | isOpen, onClose, title, children | Backdrop, escape key, accessible |
| **Toast** | message, type, onClose, duration | Auto-dismiss, slide-in animation |
| **ImageUpload** | currentImage, onImageChange, disabled, maxSizeInMB | Base64 conversion, preview |
| **DashboardCard** | title, children, icon, className | Hover elevation effect |

### 6.2 Layout Components

| Component | Purpose |
|-----------|---------|
| **Navbar** | Top navigation with logo, language toggle, profile |
| **Sidebar** | Responsive drawer with navigation items |
| **ProtectedRoute** | Auth guard wrapper |
| **PageLoader** | Loading spinner fallback |

### 6.3 Chat Components

| Component | Memoized | Zustand Integration |
|-----------|----------|---------------------|
| **MessageBubble** | Yes (React.memo) | No |
| **MessageInput** | No | Yes |
| **MessageList** | No | Yes |
| **ConversationList** | No | Yes |
| **ConversationItem** | Yes (React.memo) | No |
| **ExecutiveSelector** | No | Yes |
| **PathSelector** | Yes (React.memo) | No |
| **TTSToggle** | Yes (React.memo) | No |

---

## 7. Performance Optimizations

### 7.1 Code Splitting

```javascript
// Lazy-loaded protected routes
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));

// Wrapped with Suspense
<Suspense fallback={<PageLoader />}>
  <Routes>{/* ... */}</Routes>
</Suspense>
```

### 7.2 Memoization Patterns

**React.memo:**
```javascript
export const MessageBubble = memo(MessageBubbleComponent);
export const ConversationItem = memo(ConversationItemComponent);
export const ChatPage = memo(ChatPageComponent);
```

**useMemo:**
```javascript
const filteredConversations = useMemo(() => {
  return conversations.filter(/* ... */);
}, [conversations, debouncedQuery]);
```

**useCallback:**
```javascript
const handleSubmit = useCallback(() => {
  // handler logic
}, [dependencies]);
```

### 7.3 Zustand Selectors

```javascript
// Optimized - only re-renders on specific state change
const messages = useChatStore((state) => state.messages);

// NOT like this (causes unnecessary re-renders)
const { messages, ...everything } = useChatStore();
```

### 7.4 Debouncing

```javascript
const debouncedSearchQuery = useDebounce(searchQuery, 300);
```

### 7.5 Optimistic Updates

```javascript
// Show message immediately
const optimisticMessage = { id: `temp-${Date.now()}`, isOptimistic: true };
// Replace with server response later
```

---

## 8. API Integration

### 8.1 Axios Configuration

**Two Instances:**
- Main: `/api/users` → Auth service (port 3001)
- Chat: `/api/chat` → Chat service (port 3002)

**Interceptors:**
- Request: Cookie forwarding
- Response: Token refresh on 401, error queue handling

### 8.2 Token Refresh Pattern

```javascript
// Queue failed requests during refresh
if (isRefreshing) {
  return new Promise((resolve, reject) => {
    failedQueue.push({ resolve, reject });
  }).then(() => axiosInstance(originalRequest));
}
```

---

## 9. Utilities

### 9.1 Sanitization (`sanitizer.js`)
- `sanitizeInput()` - XSS prevention
- `escapeHtml()` - HTML entity encoding
- `truncateString()` - Text truncation

### 9.2 Validation (`validators.js`)
- `validateEmail()` - Email format
- `validatePassword()` - Strength check
- `validateRequired()` - Non-empty check

### 9.3 Cookies (`cookieUtils.js`)
- `hasCookie()` - Check existence
- `hasAuthCookies()` - Check auth cookies
- `getAllCookies()` - Get all as object

### 9.4 Logger (`logger.js`)
- Environment-aware (dev only for debug)
- `logger.log/debug/info/warn/error`

---

## 10. Layout Pattern

### Standard Page Layout

```jsx
<div className="flex flex-col min-h-screen">
  <Navbar />

  <div className="flex flex-1">
    <Sidebar>
      {/* Optional sidebar content */}
    </Sidebar>

    <main className="flex-1 overflow-auto">
      {/* Page content */}
    </main>
  </div>

  {/* Mobile sidebar overlay */}
  {sidebarOpen && <div className="overlay" onClick={closeSidebar} />}
</div>
```

### Responsive Behavior

- **Mobile:** Sidebar hidden, toggle via menu button
- **Desktop (md+):** Sidebar always visible
- **Sidebar width:** w-72 (desktop), w-64 (tablet)

---

## 11. Testing Infrastructure

### Unit Tests (Jest)
- Coverage threshold: 40%
- Test files: `__tests__/**/*.test.js`
- Mocking: MSW for API

### E2E Tests (Playwright)
- Browsers: Chrome, Firefox, Safari
- Directory: `/e2e`
- Screenshots on failure

---

## 12. Build & Deployment

### Vite Configuration
- Path alias: `@` → `./src`
- API proxy for dev server
- Allowed hosts configured

### Docker
- Multi-stage build
- Alpine base image
- Non-root user
- Health checks

---

## 13. Key Patterns Summary

| Pattern | Where Used | Benefit |
|---------|------------|---------|
| Code splitting | App.jsx routes | Smaller initial bundle |
| React.memo | List items, complex components | Prevent re-renders |
| Zustand selectors | All components | Granular subscriptions |
| useCallback | Event handlers | Stable references |
| useMemo | Computed values | Avoid recalculation |
| Debouncing | Search inputs | Reduce API calls |
| Optimistic updates | Chat messages | Instant feedback |
| Cross-tab sync | Auth store | Consistent state |

---

## 14. For Onboarding Dashboard

### Reusable Components
- Button, Modal, Toast, FormInput
- DashboardCard
- ProtectedRoute
- Sidebar, Navbar
- PageLoader

### Reusable Patterns
- Zustand store with selectors
- API service with interceptors
- Pagination pattern
- File upload (ImageUpload)
- Loading/error states

### New Components Needed
- CompanyCard / CompanyList
- ExecutiveTree (hierarchical)
- DocumentList with status
- FileUploader (multi-file)
- CalibrationModal
- StatusBadge
