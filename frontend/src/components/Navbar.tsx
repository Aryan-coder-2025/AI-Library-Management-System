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
}

export const Navbar: React.FC<NavbarProps> = ({
  currentUser,
  activeTab,
  onSelectTab,
  onLogout,
  onOpenTour,
  onOpenCopilot,
  onOpenProfile,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleTabClick = (tab: string) => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
  };

  const isPatron = currentUser?.role === 'student' || currentUser?.role === 'teacher';

  return (
    <header className="navbar">
      <div className="navbar-container">
        <a
          href="#home"
          className="navbar-brand"
          data-tour="nav-brand"
          onClick={(e) => {
            e.preventDefault();
            handleTabClick('catalogue');
          }}
        >
          <div className="navbar-brand-icon">AI</div>
          <div className="navbar-brand-title">
            <span>AI Library</span>
            <span className="navbar-brand-subtitle">Management System</span>
          </div>
        </a>

        {/* Guest View Navigation */}
        {!currentUser && (
          <div className="navbar-user-section" style={{ marginLeft: 'auto', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <button
              type="button"
              className={`nav-button ${activeTab === 'catalogue' ? 'active' : ''}`}
              onClick={() => handleTabClick('catalogue')}
              style={{ border: 'none', background: 'none', cursor: 'pointer' }}
            >
              Public Catalogue
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => handleTabClick('login')}
              title="Sign in to your library account"
            >
              Sign In
            </button>
          </div>
        )}

        {currentUser && (
          <>
            <button
              type="button"
              className="mobile-nav-toggle"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle navigation menu"
            >
              ☰
            </button>

            <nav className={`nav-links ${mobileMenuOpen ? 'open' : ''}`}>
              {/* Shared Catalogue Tab */}
              <button
                type="button"
                data-tour="nav-catalogue"
                className={`nav-button ${activeTab === 'catalogue' ? 'active' : ''}`}
                onClick={() => handleTabClick('catalogue')}
              >
                Catalogue
              </button>

              {/* Patron Views (Student & Teacher) */}
              {isPatron && (
                <>
                  <button
                    type="button"
                    data-tour="nav-semantic"
                    className={`nav-button ${activeTab === 'semantic' ? 'active' : ''}`}
                    onClick={() => handleTabClick('semantic')}
                  >
                    Semantic Search
                  </button>
                  <button
                    type="button"
                    data-tour="nav-loans"
                    className={`nav-button ${activeTab === 'loans' ? 'active' : ''}`}
                    onClick={() => handleTabClick('loans')}
                  >
                    My Loans
                  </button>
                  <button
                    type="button"
                    data-tour="nav-spaces"
                    className={`nav-button ${activeTab === 'spaces' ? 'active' : ''}`}
                    onClick={() => handleTabClick('spaces')}
                  >
                    Study Spaces
                  </button>
                </>
              )}

              {/* Librarian Views */}
              {currentUser.role === 'librarian' && (
                <>
                  <button
                    type="button"
                    data-tour="nav-semantic"
                    className={`nav-button ${activeTab === 'semantic' ? 'active' : ''}`}
                    onClick={() => handleTabClick('semantic')}
                  >
                    AI Search
                  </button>
                  <button
                    type="button"
                    data-tour="nav-manage-catalogue"
                    className={`nav-button ${activeTab === 'manage_catalogue' ? 'active' : ''}`}
                    onClick={() => handleTabClick('manage_catalogue')}
                  >
                    Catalogue Management
                  </button>
                  <button
                    type="button"
                    data-tour="nav-circulation"
                    className={`nav-button ${activeTab === 'circulation' ? 'active' : ''}`}
                    onClick={() => handleTabClick('circulation')}
                  >
                    Circulation Desk
                  </button>
                  <button
                    type="button"
                    data-tour="nav-space-management"
                    className={`nav-button ${activeTab === 'space_management' ? 'active' : ''}`}
                    onClick={() => handleTabClick('space_management')}
                  >
                    Study Spaces Desk
                  </button>
                  <button
                    type="button"
                    data-tour="nav-embeddings"
                    className={`nav-button ${activeTab === 'embeddings' ? 'active' : ''}`}
                    onClick={() => handleTabClick('embeddings')}
                  >
                    AI Embeddings
                  </button>
                </>
              )}
            </nav>

            <div className="navbar-user-section">
              {/* Overdue Alerts & In-App Notification Bell (CIRC-04) */}
              <NotificationBell currentUser={currentUser} />

              {/* Tour & Help Trigger */}
              {onOpenTour && (
                <button
                  type="button"
                  data-tour="nav-tour"
                  className="btn btn-secondary btn-sm"
                  onClick={onOpenTour}
                  title="Open guided onboarding tour and website help"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '4px' }}>
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                  Tour & Help
                </button>
              )}

              {/* Copilot Quick Trigger */}
              {onOpenCopilot && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={onOpenCopilot}
                  title="Open conversational AI Library Copilot"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
                  </svg>
                  <span>Copilot</span>
                </button>
              )}

              {/* User Identity & Profile Modal Trigger (PORT-06) */}
              <div
                className="user-badge"
                data-tour="nav-user"
                onClick={onOpenProfile}
                style={{ cursor: onOpenProfile ? 'pointer' : 'default' }}
                title="Click to view and edit profile settings"
              >
                <span className="user-name">{currentUser.full_name}</span>
                <span className={`user-role-tag ${currentUser.role}`}>
                  {currentUser.role}
                </span>
              </div>

              {onOpenProfile && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={onOpenProfile}
                  title="Account settings & profile"
                >
                  Profile
                </button>
              )}

              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={onLogout}
                title="Sign out of your library account"
              >
                Sign Out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
};
