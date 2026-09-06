/**
 * CivicSight - Authentication & Role-Based Navigation Manager (Week 3)
 *
 * Provides client-side JWT session management, API request helpers,
 * role verification, and dynamic post-login navigation updates.
 */

const CivicSightAuth = (() => {
  const TOKEN_KEY = 'civicsight_token';
  const USER_KEY = 'civicsight_user';

  // Determine API Base URL
  function getApiBase() {
    if (window.location.protocol === 'file:') {
      return 'http://127.0.0.1:8000';
    }
    // If backend is running on port 8000
    if (window.location.port !== '8000') {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    return '';
  }

  const API_BASE = getApiBase();

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getUser() {
    try {
      const data = localStorage.getItem(USER_KEY);
      return data ? JSON.parse(data) : null;
    } catch (e) {
      return null;
    }
  }

  function setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function isAuthenticated() {
    return !!getToken();
  }

  function hasRole(roles) {
    const user = getUser();
    if (!user || !user.role) return false;
    if (typeof roles === 'string') {
      return user.role.toLowerCase() === roles.toLowerCase();
    }
    if (Array.isArray(roles)) {
      return roles.some(r => r.toLowerCase() === user.role.toLowerCase());
    }
    return false;
  }

  async function register(payload) {
    const url1 = `${API_BASE}/api/v1/auth/register`;
    const url2 = `${API_BASE}/auth/register`;

    let response;
    try {
      response = await fetch(url1, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (response.status === 404) {
        response = await fetch(url2, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
    } catch (err) {
      throw new Error(`Connection failed. Please ensure the backend server is running at ${API_BASE}.`);
    }

    const data = await response.json();
    if (!response.ok) {
      const errorMsg = data.detail 
        ? (Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(', ') : data.detail)
        : 'Registration failed. Please try again.';
      throw new Error(errorMsg);
    }
    return data;
  }

  async function login(email, password) {
    const url1 = `${API_BASE}/api/v1/auth/login`;
    const url2 = `${API_BASE}/auth/login`;

    let response;
    try {
      response = await fetch(url1, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (response.status === 404) {
        response = await fetch(url2, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
      }
    } catch (err) {
      throw new Error(`Connection failed. Please ensure the backend server is running at ${API_BASE}.`);
    }

    const data = await response.json();
    if (!response.ok) {
      const errorMsg = data.detail 
        ? (Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(', ') : data.detail)
        : 'Invalid email or password.';
      throw new Error(errorMsg);
    }

    setSession(data.access_token, data.user);
    return data;
  }

  function logout() {
    clearSession();
    updateNavigation();
    showToast('You have been signed out.', 'info');
    // Refresh page or redirect to index if on protected view
    setTimeout(() => {
      const isSubPage = window.location.pathname.includes('/pages/');
      window.location.href = isSubPage ? '../index.html' : 'index.html';
    }, 500);
  }

  function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    let iconSvg = '';

    if (type === 'success') {
      iconSvg = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-success);">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
      `;
    } else if (type === 'error') {
      iconSvg = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-danger);">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      `;
    } else {
      iconSvg = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-primary-light);">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
      `;
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- Dynamic Post-Login Navigation Structure ---
  function updateNavigation() {
    const isSubPage = window.location.pathname.includes('/pages/');
    const basePath = isSubPage ? '' : 'pages/';
    const homePath = isSubPage ? '../index.html' : 'index.html';

    const navActions = document.querySelector('.nav-actions');
    const navLinks = document.getElementById('navLinks');

    const user = getUser();
    const loggedIn = isAuthenticated() && user;

    if (navActions) {
      if (loggedIn) {
        const roleClass = (user.role || 'Citizen').toLowerCase().replace(/\s+/g, '-');
        navActions.innerHTML = `
          <div class="user-nav-profile">
            <div class="user-avatar-badge" title="${user.name}">
              ${user.name.charAt(0).toUpperCase()}
            </div>
            <div class="user-meta-wrap">
              <span class="user-nav-name">${user.name}</span>
              <span class="user-role-badge role-${roleClass}">${user.role}</span>
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" id="signOutBtn">Sign Out</button>
        `;

        const signOutBtn = document.getElementById('signOutBtn');
        if (signOutBtn) {
          signOutBtn.addEventListener('click', logout);
        }
      } else {
        navActions.innerHTML = `
          <a href="${basePath}login.html" class="btn btn-secondary btn-sm">Log In</a>
          <a href="${basePath}register.html" class="btn btn-primary btn-sm">Register</a>
        `;
      }
    }

    // Role-based Nav Links Preparation
    if (navLinks) {
      // Check existing links and dynamically insert role-specific portal triggers
      const roleSectionContainer = document.getElementById('roleNavItems');
      if (!roleSectionContainer && loggedIn) {
        const roleLi = document.createElement('li');
        roleLi.id = 'roleNavItems';
        
        let roleBadgeContent = '';
        if (user.role === 'Admin') {
          roleBadgeContent = `<a href="#admin" class="nav-link role-active-link" data-placeholder="Admin Management Panel">[Admin Ops]</a>`;
        } else if (user.role === 'Municipal Officer') {
          roleBadgeContent = `<a href="#officer" class="nav-link role-active-link" data-placeholder="Municipal Verification & Dispatch">[Officer Triage]</a>`;
        } else if (user.role === 'Maintenance Staff') {
          roleBadgeContent = `<a href="#staff" class="nav-link role-active-link" data-placeholder="Assigned Road Repairs">[Field Work Orders]</a>`;
        } else {
          roleBadgeContent = `<a href="${basePath}report.html" class="nav-link role-active-link">[Citizen Portal]</a>`;
        }
        roleLi.innerHTML = roleBadgeContent;
        navLinks.appendChild(roleLi);
      } else if (roleSectionContainer && !loggedIn) {
        roleSectionContainer.remove();
      }
    }
  }

  // Auto-run when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    updateNavigation();
  });

  return {
    API_BASE,
    getToken,
    getUser,
    isAuthenticated,
    hasRole,
    register,
    login,
    logout,
    showToast,
    updateNavigation,
  };
})();
