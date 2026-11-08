import React, { useState } from 'react';
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
  onOpenCopilot,
  onOpenProfile,
  onOpenCommandPalette,
  currentTheme = 'dark',
  onToggleTheme,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleTabClick = (tab: string) => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
  };

  const isPatron = currentUser?.role === 'student' || currentUser?.role === 'teacher';
  const isLibrarian = currentUser?.role === 'librarian';

  return (
    <header className="navbar">
      <div className="navbar-container">
        {/* Brand identity: Athenaeum */}
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
            <span className="navbar-brand-subtitle">Academic Intelligence</span>
          </div>
        </a>

        {/* Global Command Palette search bar launcher */}
        {onOpenCommandPalette && (
          <button
            type="button"
            className="navbar-search-launcher"
            onClick={onOpenCommandPalette}
            title="Open command palette (Ctrl+K or Cmd+K)"
          >
            <span className="search-icon">🔍</span>
            <span className="search-placeholder">Quick search or command...</span>
            <span className="keyboard-shortcut-pill">Ctrl K</span>
          </button>
        )}

        {/* Mobile Nav Toggle */}
        <button
          type="button"
          className="mobile-nav-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          ☰
        </button>

        {/* Navigation Tabs */}
        <nav className={`nav-links ${mobileMenuOpen ? 'open' : ''}`}>
          {/* Workspace Group */}
          <button
            type="button"
            data-tour="nav-dashboard"
            className={`nav-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => handleTabClick('dashboard')}
          >
            <span className="nav-icon">📊</span>
            <span>Dashboard</span>
          </button>

          <button
            type="button"
            data-tour="nav-catalogue"
            className={`nav-button ${activeTab === 'catalogue' ? 'active' : ''}`}
            onClick={() => handleTabClick('catalogue')}
          >
            <span className="nav-icon">📚</span>
            <span>Catalogue</span>
          </button>

          <button
            type="button"
            data-tour="nav-semantic"
            className={`nav-button ${activeTab === 'semantic' ? 'active' : ''}`}
            onClick={() => handleTabClick('semantic')}
          >
            <span className="nav-icon">🧠</span>
            <span>Semantic Search</span>
          </button>

          <button
            type="button"
            data-tour="nav-knowledge"
            className={`nav-button ${activeTab === 'knowledge' ? 'active' : ''}`}
            onClick={() => handleTabClick('knowledge')}
          >
            <span className="nav-icon">🔬</span>
            <span>Knowledge Graph</span>
          </button>

          {/* Patron Views (Student & Teacher) */}
          {currentUser && isPatron && (
            <>
              <button
                type="button"
                data-tour="nav-loans"
                className={`nav-button ${activeTab === 'loans' ? 'active' : ''}`}
                onClick={() => handleTabClick('loans')}
              >
                <span className="nav-icon">📖</span>
                <span>My Loans</span>
              </button>
              <button
                type="button"
                data-tour="nav-spaces"
                className={`nav-button ${activeTab === 'spaces' ? 'active' : ''}`}
                onClick={() => handleTabClick('spaces')}
              >
                <span className="nav-icon">🏛️</span>
                <span>Study Spaces</span>
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
            >
              <span className="nav-icon">🎓</span>
              <span>Teacher Portal</span>
            </button>
          )}

          {/* Librarian Views */}
          {currentUser && isLibrarian && (
            <>
              <button
                type="button"
                data-tour="nav-intelligence"
                className={`nav-button ${activeTab === 'intelligence' ? 'active' : ''}`}
                onClick={() => handleTabClick('intelligence')}
              >
                <span className="nav-icon">📈</span>
                <span>Intelligence Centre</span>
              </button>
              <button
                type="button"
                data-tour="nav-manage-catalogue"
                className={`nav-button ${activeTab === 'manage_catalogue' ? 'active' : ''}`}
                onClick={() => handleTabClick('manage_catalogue')}
              >
                <span className="nav-icon">📦</span>
                <span>Inventory</span>
              </button>
              <button
                type="button"
                data-tour="nav-circulation"
                className={`nav-button ${activeTab === 'circulation' ? 'active' : ''}`}
                onClick={() => handleTabClick('circulation')}
              >
                <span className="nav-icon">🔄</span>
                <span>Circulation</span>
              </button>
              <button
                type="button"
                data-tour="nav-space-management"
                className={`nav-button ${activeTab === 'space_management' ? 'active' : ''}`}
                onClick={() => handleTabClick('space_management')}
              >
                <span className="nav-icon">🗺️</span>
                <span>Spaces Desk</span>
              </button>
              <button
                type="button"
                data-tour="nav-embeddings"
                className={`nav-button ${activeTab === 'embeddings' ? 'active' : ''}`}
                onClick={() => handleTabClick('embeddings')}
              >
                <span className="nav-icon">⚡</span>
                <span>Embeddings</span>
              </button>
              <button
                type="button"
                data-tour="nav-ai-studio"
                className={`nav-button ${activeTab === 'ai_studio' ? 'active' : ''}`}
                onClick={() => handleTabClick('ai_studio')}
              >
                <span className="nav-icon">⚖️</span>
                <span>AI Studio</span>
              </button>
            </>
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
              title={`Switch to ${currentTheme === 'dark' ? 'Academic Aurora (Light)' : 'Midnight Intelligence (Dark)'}`}
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

          {/* AI Copilot Signature Launcher */}
          {currentUser && onOpenCopilot && (
            <button
              type="button"
              className="btn btn-primary btn-sm copilot-nav-trigger"
              onClick={onOpenCopilot}
              title="Open conversational AI Copilot (Ctrl+J)"
            >
              <span className="spark-icon">✨</span>
              <span>Copilot</span>
            </button>
          )}

          {/* User Account / Profile */}
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
                className="btn btn-secondary btn-sm"
                onClick={onLogout}
                title="Sign out of Athenaeum"
              >
                Sign Out
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
