# FirstWeek Frontend

Modern React frontend application for FirstWeek built with Vite, featuring authentication, internationalization, and optimized performance with lazy loading.

---

## 🚀 Quick Start

Get the application up and running on your local machine in minutes.

### 1. Prerequisites

Ensure you have the following installed:

- **Node.js** v18.x or higher - [Download](https://nodejs.org/)
- **npm** v9.x or higher - comes with Node.js
- **Git** - [Download](https://git-scm.com/)
- **Backend API** running on port 3001

Verify installations:
```bash
node --version
npm --version
git --version
```

### 2. Navigate to Frontend Directory
```bash
cd /path/to/FirstWeek/frontend
```

### 3. Install Dependencies
```bash
npm install
```

This installs all required packages including React, React Router, i18next, Tailwind CSS, Vite, and more.

### 4. Configure Environment

Create a `.env` file in the frontend root:

```bash
touch .env
```

Add the backend API URL:
```env
VITE_API_BASE_URL=http://localhost:3001/api/users
VITE_DEV_ENV=true
```

**Note**: Never commit the `.env` file! Use `.env.example` as a template.

### 5. Start Development Server
```bash
npm run dev
```

Expected output:
```
VITE v5.4.21  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### 6. Open in Browser

Navigate to `http://localhost:5173`

✅ You should see the login page!

---

## 🛠️ Tech Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **Framework** | React | 18.3.1 |
| **Build Tool** | Vite | 5.4.21 |
| **Routing** | React Router DOM | 6.26.0 |
| **State Management** | Zustand | 5.0.8 |
| **Styling** | Tailwind CSS | 3.4.10 |
| **HTTP Client** | Axios | 1.12.2 |
| **i18n** | i18next + react-i18next | 25.6.0 |
| **Icons** | Lucide React | 0.263.1 |

---

## 📂 Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── Auth/           # Authentication components
│   │   ├── EmailVerification/
│   │   ├── ui/             # Base UI components (Button, Input, Toast)
│   │   ├── Navbar/
│   │   ├── Sidebar/
│   │   └── PageLoader.jsx  # Lazy loading fallback
│   ├── pages/              # Page components (lazy loaded)
│   │   ├── LoginPage.jsx
│   │   ├── SignupPage.jsx
│   │   ├── DashboardPage.jsx
│   │   ├── ProfilePage.jsx
│   │   └── ...
│   ├── services/           # API integration layer
│   │   └── api.js          # Centralized API endpoints
│   ├── store/              # Zustand stores
│   │   └── authStore.js    # Authentication state
│   ├── i18n/               # Internationalization
│   │   ├── config.js
│   │   ├── locales/
│   │   │   ├── en.json     # English translations
│   │   │   └── ja.json     # Japanese translations
│   ├── utils/              # Utility functions
│   │   ├── validators.js   # Form validation
│   │   └── sanitizer.js    # Input sanitization
│   ├── App.jsx             # Root component with routing
│   └── main.jsx            # Entry point
├── public/                 # Static assets
├── .env                    # Environment variables
├── package.json
├── vite.config.js          # Vite configuration
├── tailwind.config.js      # Tailwind CSS configuration
└── eslint.config.js        # ESLint configuration
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the frontend root:

```env
VITE_API_BASE_URL=http://localhost:3001/api/users
VITE_DEV_ENV=true
```

### Vite Config

- **Dev Server Port**: 5173
- **API Proxy**: `/api` → `http://localhost:3001`
- **Path Alias**: `@` → `./src`

---

## 🎯 Key Features

### Authentication & Security
- ✅ Cookie-based authentication with session management
- ✅ Protected routes with redirect to login
- ✅ Email verification with OTP
- ✅ Password reset functionality
- ✅ Input sanitization to prevent XSS
- ✅ Strong password validation
- ✅ Cross-tab synchronization (BroadcastChannel)

### User Experience
- ✅ Responsive design (mobile-first)
- ✅ Multi-language support (English, Japanese)
- ✅ Toast notifications for user feedback
- ✅ Form validation with real-time error messages
- ✅ Accessibility (ARIA labels, semantic HTML)
- ✅ Loading states and skeleton screens

### Performance Optimizations
- ✅ **Lazy loading** for route-based code splitting
- ✅ Optimized bundle sizes (~46KB saved on initial load)
- ✅ On-demand loading of protected pages
- ✅ Lightweight state management (Zustand)
- ✅ Fast build times with Vite

---

## 📦 Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server on port 5173 |
| `npm run build` | Build for production (output to `dist/`) |
| `npm run preview` | Preview production build locally |
| `npm run test` | Run Jest tests |
| `npm run test:coverage` | Run tests with coverage report |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run test:e2e:ui` | Run E2E tests with UI |
| `npm run lint` | Lint code with ESLint |
| `npm run format` | Format code with Prettier |

---

## 🔐 Authentication Flow

1. **Login**: User enters email/username + password
2. **API Call**: POST to `/api/users/login` with credentials
3. **Cookie Set**: Backend sets httpOnly cookie
4. **Store Update**: Zustand store updates auth state
5. **Redirect**: User redirected to dashboard
6. **Protected Routes**: ProtectedRoute checks auth before rendering

### Cross-Tab Synchronization

```javascript
// Login in Tab 1 → All other tabs auto-login
// Logout in Tab 1 → All other tabs auto-logout
// Uses BroadcastChannel API
```

---

## 🌐 Internationalization (i18n)

### Supported Languages
- 🇺🇸 English (en)
- 🇯🇵 Japanese (ja)

### Usage in Components

```javascript
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();
  return <h1>{t('welcome')}</h1>;
}
```

### Adding New Languages

1. Create `src/i18n/locales/[lang].json`
2. Add to `src/i18n/config.js` resources
3. Update LanguageToggle component

---

## 🚦 Routing

### Public Routes (Not Lazy Loaded)
- `/login` - Login page
- `/signup` - User registration
- `/forgot-password` - Password reset request
- `/reset-password` - Password reset with token

### Protected Routes (Lazy Loaded)
- `/dashboard` - Main dashboard
- `/profile` - User profile management
- `/invite-meet` - Schedule meetings
- `/chat/:id?` - Chat transcription
- `/videochat` - Video chat interface

### Lazy Loading Implementation

```javascript
// Pages are split into separate chunks
const DashboardPage = lazy(() => import('./pages/DashboardPage'));

// Wrapped in Suspense with loading fallback
<Suspense fallback={<PageLoader />}>
  <DashboardPage />
</Suspense>
```

**Benefits**:
- Initial bundle: 285 KB (shared + auth)
- Lazy chunks: 4-17 KB each
- Faster initial page load
- Better user experience

---

## 🎨 UI Components

### Base Components (`components/ui/`)

**Button**
```javascript
<Button variant="primary" onClick={handleClick}>
  Click Me
</Button>
// Variants: primary, secondary, outline
```

**FormInput**
```javascript
<FormInput
  label="Email"
  type="email"
  error={errors.email}
  icon={Mail}
/>
```

**PasswordInput**
```javascript
<PasswordInput
  label="Password"
  value={password}
  onChange={handleChange}
  showStrength={true}
/>
```

**Toast**
```javascript
<Toast
  message="Success!"
  type="success"
  onClose={handleClose}
/>
// Types: success, error, info
```

**ImageUpload**
```javascript
<ImageUpload
  currentImage={user.profilePicture}
  onImageSelect={handleImageSelect}
  maxSize={5} // MB
/>
```

---

## 🧪 Testing

### Unit Tests (Jest)

```bash
npm run test
npm run test:coverage
```

### E2E Tests (Playwright)

```bash
npm run test:e2e
npm run test:e2e:ui
```

### Test Coverage Goals
- Critical paths: 70%+
- Auth flows: 90%+
- UI components: 60%+

---

## 🐛 Troubleshooting

### npm install fails

```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install

# If still failing, try with legacy peer deps
npm install --legacy-peer-deps
```

### Port 5173 already in use

```bash
# Linux/Mac
lsof -ti:5173 | xargs kill -9

# Windows
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Or use different port
npm run dev -- --port 3000
```

### Backend connection errors

1. Ensure backend is running on port 3001
2. Check `.env` has correct `VITE_API_BASE_URL`
3. Verify CORS enabled on backend for `http://localhost:5173`

### Lazy loading errors

Check browser console - if chunks fail to load:
1. Clear browser cache
2. Rebuild: `npm run build`
3. Check network tab for 404 errors

---

## 📊 Build Output Example

```
dist/index.html                           0.88 kB
dist/assets/index-DGVCdj1K.css          25.59 kB
dist/assets/ProfilePage-DVsFW1lm.js     17.44 kB  (lazy)
dist/assets/InviteMeetPage-ChkpansM.js   6.82 kB  (lazy)
dist/assets/DashboardPage-DhhksdMU.js    6.55 kB  (lazy)
dist/assets/VideoChatPage-YmrzK1ef.js    5.82 kB  (lazy)
dist/assets/index-Bgqq3JUe.js          285.44 kB  (main bundle)
```

---

## 🔗 API Integration

All API calls centralized in `src/services/api.js`:

```javascript
import { login, getMe, updateProfile } from './services/api';

// Login
const response = await login('user@example.com', 'password123');

// Get current user
const user = await getMe();

// Update profile
await updateProfile({ firstName: 'John' });
```

See `BACKEND_INTEGRATION.md` for detailed API documentation.

---

## 📚 Additional Documentation

- **Backend Integration**: `BACKEND_INTEGRATION.md`
- **Features & Status**: `STATUS.md`
- **Email Verification**: `EMAIL_VERIFICATION_FEATURE.md`
- **Profile Feature**: `PROFILE_FEATURE.md`
- **CORS Setup**: `CORS_FIX.md`
- **Browser Testing**: `BROWSER_TESTING.md`

---

## 🚀 Deployment

### Production Build

```bash
npm run build
```

Output in `dist/` directory ready for static hosting (Netlify, Vercel, etc.)

### Environment Variables for Production

```env
VITE_API_BASE_URL=https://api.yourapp.com/api/users
VITE_DEV_ENV=false
```

### Hosting Recommendations
- **Netlify**: Automatic deployments from Git
- **Vercel**: Zero-config deployment
- **AWS S3 + CloudFront**: Scalable static hosting

---

## 🤝 Contributing

1. Follow existing code style (Prettier + ESLint)
2. Write tests for new features
3. Update documentation
4. Use conventional commits

---

## 📝 License

[Your License Here]

---

**Status**: ✅ Production-ready with optimized performance

For questions or issues, please contact the development team.
