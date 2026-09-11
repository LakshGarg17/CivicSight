/**
 * CivicSight - Theme Management System
 * 
 * Implements strict two-theme system: Plain White (light) and Plain Black (dark).
 * Instant switching with zero page reload and localStorage persistence.
 */

(function () {
  const THEME_STORAGE_KEY = 'civicsight_theme';

  function getSavedTheme() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') {
      return saved;
    }
    // Default to light theme
    return 'light';
  }

  function applyTheme(theme) {
    const validTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', validTheme);
    document.documentElement.style.colorScheme = validTheme;
    localStorage.setItem(THEME_STORAGE_KEY, validTheme);
    updateToggleButtons(validTheme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  }

  function getIconSvg(theme) {
    if (theme === 'dark') {
      // In dark mode: show Sun icon to switch to light mode
      return `
        <svg class="theme-icon sun-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      `;
    } else {
      // In light mode: show Moon icon to switch to dark mode
      return `
        <svg class="theme-icon moon-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      `;
    }
  }

  function updateToggleButtons(theme) {
    const buttons = document.querySelectorAll('.theme-toggle-btn');
    buttons.forEach((btn) => {
      const isDark = theme === 'dark';
      const label = isDark ? 'Switch to light theme' : 'Switch to dark theme';
      btn.setAttribute('aria-label', label);
      btn.setAttribute('title', label);
      btn.innerHTML = getIconSvg(theme);
    });
  }

  // Set initial theme immediately to prevent FOUC (Flash of Unstyled Content)
  const initialTheme = getSavedTheme();
  document.documentElement.setAttribute('data-theme', initialTheme);
  document.documentElement.style.colorScheme = initialTheme;

  // Initialize UI event listeners once DOM is parsed
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeUI);
  } else {
    initThemeUI();
  }

  function initThemeUI() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || initialTheme;
    updateToggleButtons(currentTheme);

    document.querySelectorAll('.theme-toggle-btn').forEach((btn) => {
      // Remove any existing click handler to prevent duplicate triggers
      btn.removeEventListener('click', toggleTheme);
      btn.addEventListener('click', toggleTheme);
    });
  }

  // Public API
  window.CivicSightTheme = {
    getTheme: () => document.documentElement.getAttribute('data-theme') || 'light',
    setTheme: applyTheme,
    toggleTheme: toggleTheme,
    updateButtons: updateToggleButtons,
  };
})();
