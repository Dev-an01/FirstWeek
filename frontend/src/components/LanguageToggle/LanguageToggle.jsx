import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';

/**
 * LanguageToggle Component
 * Toggles between English and Japanese languages
 */
export function LanguageToggle() {
  const { i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'ja' : 'en';
    i18n.changeLanguage(newLang);
    localStorage.setItem('language', newLang);
  };

  return (
    <button
      onClick={toggleLanguage}
      className="relative flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white/90 backdrop-blur-sm border border-gray-200 hover:text-primary hover:bg-primary/10 hover:border-primary/30 rounded-lg transition-all shadow-sm hover:shadow-md"
      title="Toggle Language"
    >
      <Languages size={18} />
      <span className="hidden sm:inline">
        {i18n.language === 'en' ? 'EN' : '日本語'}
      </span>
    </button>
  );
}
