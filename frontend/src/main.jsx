import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/index.css';

const App = React.lazy(() => import.meta.env.VITE_FIRSTWEEK_PUBLIC_ONLY === 'true'
  ? import('./firstweek/PublicApp') : import('./App'));

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <React.Suspense fallback={<p role="status">Loading FirstWeek…</p>}><App /></React.Suspense>
  </React.StrictMode>
);
