import React, { useState, useRef, useEffect } from 'react';
import type { UserProfile } from '../types/library';
import { NotificationBell } from './NotificationBell';

interface NavbarProps {
  currentUser: UserProfile | null;
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onLogout: () => void;
  onOpenTour?: () => void;
  onOpenCopilot?: () => void;
  onOpenProfile?: () => void;
  onOpenCommandPalette?: () => void;
  currentTheme?: 'dark' | 'light';
  onToggleTheme?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentUser,
  activeTab,
  onSelectTab,
  onLogout,
  onOpenTour,
  onOpenCopilot: _onOpenCopilot,
  onOpenProfile,
  onOpenCommandPalette,
  currentTheme = 'dark',
  onToggleTheme,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [staffMenuOpen, setStaffMenuOpen] = useState(false);
  const staffDropdownRef = useRef<HTMLDivElement>(null);

  const handleTabClick = (tab: string) => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
    setStaffMenuOpen(false);
  };

  // Close staff dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (staffDropdownRef.current && !staffDropdownRef.current.contains(e.target as Node)) {
        setStaffMenuOpen(false);
      }
    };
    if (staffMenuOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [staffMenuOpen]);

  const isPatron = currentUser?.role === 'student' || currentUser?.role === 'teacher';
  const isLibrarian = currentUser?.role === 'librarian';

  const librarianTabs = [
    { id: 'intelligence', label: 'Intelligence Centre', icon: '📈' },
    { id: 'manage_catalogue', label: 'Inventory', icon: '📦' },
    { id: 'circulation', label: 'Circulation Desk', icon: '🔄' },
    { id: 'space_management', label: 'Spaces Desk', icon: '🗺️' },
    { id: 'embeddings', label: 'AI Embeddings', icon: '⚡' },
    { id: 'ai_studio', label: 'AI Studio', icon: '⚖️' },
  ];

  const activeStaffTab = librarianTabs.find((t) => t.id === activeTab);

  return (
    <header className="navbar">
      <div className="navbar-container">
        {/* Futuristic Brand Identity: Athenaeum */}
        <a
          href="#home"
          className="navbar-brand"
          data-tour="nav-brand"
          onClick={(e) => {
            e.preventDefault();
            handleTabClick('dashboard');
          }}
        >
          <div className="navbar-brand-emblem">
            <span className="brand-glyph">🏛️</span>
            <span className="brand-glow-halo" />
          </div>
          <div className="navbar-brand-title">
            <span className="brand-name">ATHENAEUM</span>
            <span className="navbar-brand-badge">AI 2.0</span>
          </div>
        </a>

        {/* Global Command Palette Search launcher */}
        {onOpenCommandPalette && (
          <button
            type="button"
            className="navbar-search-launcher"
            onClick={onOpenCommandPalette}
            title="Open command palette (Ctrl+K or Cmd+K)"
          >
            <span className="search-icon">🔍</span>
            <span className="search-placeholder">Quick search...</span>
            <span className="keyboard-shortcut-pill">Ctrl K</span>
          </button>
        )}

        {/* Mobile Navigation Hamburger */}
        <button
          type="button"
          className="mobile-nav-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          ☰
        </button>

        {/* Navigation Tabs - Modern Futuristic Segmented Pill Bar */}
        <nav className={`nav-links ${mobileMenuOpen ? 'open' : ''}`}>
          <button
            type="button"
            data-tour="nav-dashboard"
            className={`nav-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => handleTabClick('dashboard')}
            title="Dashboard Overview"
          >
            <span className="nav-icon">📊</span>
            <span>Dashboard</span>
          </button>

          <button
            type="button"
            data-tour="nav-catalogue"
            className={`nav-button ${activeTab === 'catalogue' ? 'active' : ''}`}
            onClick={() => handleTabClick('catalogue')}
            title="Catalogue Monographs"
          >
            <span className="nav-icon">📚</span>
            <span>Catalogue</span>
          </button>

          <button
            type="button"
            data-tour="nav-semantic"
            className={`nav-button ${activeTab === 'semantic' ? 'active' : ''}`}
            onClick={() => handleTabClick('semantic')}
            title="AI Vector Semantic Search"
          >
            <span className="nav-icon">🧠</span>
            <span>AI Search</span>
          </button>

          <button
            type="button"
            data-tour="nav-knowledge"
            className={`nav-button ${activeTab === 'knowledge' ? 'active' : ''}`}
            onClick={() => handleTabClick('knowledge')}
            title="Knowledge Graph & Conceptual Navigator"
          >
            <span className="nav-icon">🔬</span>
            <span>Knowledge</span>
          </button>

          {/* Patron Views (Student & Teacher) */}
          {currentUser && isPatron && (
            <>
              <button
                type="button"
                data-tour="nav-loans"
                className={`nav-button ${activeTab === 'loans' ? 'active' : ''}`}
                onClick={() => handleTabClick('loans')}
                title="Active Monograph Loans"
              >
                <span className="nav-icon">📖</span>
                <span>Loans</span>
              </button>
              <button
                type="button"
                data-tour="nav-spaces"
                className={`nav-button ${activeTab === 'spaces' ? 'active' : ''}`}
                onClick={() => handleTabClick('spaces')}
                title="Interactive Floor Plans & Study Spaces"
              >
                <span className="nav-icon">🏛️</span>
                <span>Spaces</span>
              </button>
            </>
          )}

          {/* Teacher Portal (PORT-03 & INTEL-06) */}
          {currentUser && (currentUser.role === 'teacher' || currentUser.role === 'librarian') && (
            <button
              type="button"
              data-tour="nav-teacher-portal"
              className={`nav-button ${activeTab === 'teacher_portal' ? 'active' : ''}`}
              onClick={() => handleTabClick('teacher_portal')}
              title="Academic Syllabus & Course Reserve Planner"
            >
              <span className="nav-icon">🎓</span>
              <span>Teacher</span>
            </button>
          )}

          {/* Librarian Staff Management Menu */}
          {currentUser && isLibrarian && (
            <div className="nav-dropdown-wrap" ref={staffDropdownRef}>
              <button
                type="button"
                className={`nav-button nav-dropdown-btn ${activeStaffTab ? 'active' : ''}`}
                onClick={() => setStaffMenuOpen(!staffMenuOpen)}
                title="Librarian Staff Desks & Intelligence"
              >
                <span className="nav-icon">{activeStaffTab ? activeStaffTab.icon : '⚙️'}</span>
                <span>{activeStaffTab ? activeStaffTab.label : 'Staff Desks'}</span>
                <span className="dropdown-caret">▾</span>
              </button>
              {staffMenuOpen && (
                <div className="nav-dropdown-menu">
                  {librarianTabs.map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      className={`nav-dropdown-item ${activeTab === tab.id ? 'active' : ''}`}
                      onClick={() => handleTabClick(tab.id)}
                    >
                      <span className="nav-icon">{tab.icon}</span>
                      <span>{tab.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </nav>

        {/* Right Action Bar */}
        <div className="navbar-user-section">
          {/* Theme Switcher Toggle */}
          {onToggleTheme && (
            <button
              type="button"
              className="navbar-icon-btn"
              onClick={onToggleTheme}
              title={`Switch to ${currentTheme === 'dark' ? 'Academic Aurora (Light)' : 'Obsidian Cyber (Dark)'}`}
              aria-label="Toggle theme"
            >
              {currentTheme === 'dark' ? '☀️' : '🌙'}
            </button>
          )}

          {/* Notifications */}
          {currentUser && <NotificationBell currentUser={currentUser} />}

          {/* Tour Trigger */}
          {currentUser && onOpenTour && (
            <button
              type="button"
              className="navbar-icon-btn"
              onClick={onOpenTour}
              title="Tour & Platform Guide"
              aria-label="Platform Guide"
            >
              🧭
            </button>
          )}

          {/* User Account / Profile & 1-Click Sign Out */}
          {currentUser ? (
            <div className="user-profile-menu-wrap">
              <div
                className="user-badge"
                data-tour="nav-user"
                onClick={onOpenProfile}
                style={{ cursor: onOpenProfile ? 'pointer' : 'default' }}
                title="Account Settings & Profile"
              >
                <span className="user-name">{currentUser.full_name}</span>
                <span className={`user-role-tag ${currentUser.role}`}>
                  {currentUser.role}
                </span>
              </div>
              <button
                type="button"
                className="btn btn-signout btn-sm"
                onClick={onLogout}
                title="Sign out of Athenaeum"
              >
                <span>🚪 Sign Out</span>
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleTabClick('login')}
                title="Sign in with your university credentials or username"
              >
                Sign In
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleTabClick('register')}
                title="Create a new student scholar account"
              >
                Register
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
