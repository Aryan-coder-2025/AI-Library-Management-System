import React, { useState } from 'react';
import type { UserProfile } from '../types/library';

interface NavbarProps {
  currentUser: UserProfile | null;
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentUser,
  activeTab,
  onSelectTab,
  onLogout,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleTabClick = (tab: string) => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
  };

  return (
    <header className="navbar">
      <div className="navbar-container">
        <a
          href="#home"
          className="navbar-brand"
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
              {/* Shared Tab */}
              <button
                type="button"
                className={`nav-button ${activeTab === 'catalogue' ? 'active' : ''}`}
                onClick={() => handleTabClick('catalogue')}
              >
                Catalogue
              </button>

              {/* Student Views */}
              {currentUser.role === 'student' && (
                <>
                  <button
                    type="button"
                    className={`nav-button ${activeTab === 'semantic' ? 'active' : ''}`}
                    onClick={() => handleTabClick('semantic')}
                  >
                    Semantic Search
                  </button>
                  <button
                    type="button"
                    className={`nav-button ${activeTab === 'loans' ? 'active' : ''}`}
                    onClick={() => handleTabClick('loans')}
                  >
                    My Loans
                  </button>
                </>
              )}

              {/* Librarian Views */}
              {currentUser.role === 'librarian' && (
                <>
                  <button
                    type="button"
                    className={`nav-button ${activeTab === 'semantic' ? 'active' : ''}`}
                    onClick={() => handleTabClick('semantic')}
                  >
                    AI Search
                  </button>
                  <button
                    type="button"
                    className={`nav-button ${activeTab === 'manage_catalogue' ? 'active' : ''}`}
                    onClick={() => handleTabClick('manage_catalogue')}
                  >
                    Catalogue Management
                  </button>
                  <button
                    type="button"
                    className={`nav-button ${activeTab === 'circulation' ? 'active' : ''}`}
                    onClick={() => handleTabClick('circulation')}
                  >
                    Circulation Desk
                  </button>
                  <button
                    type="button"
                    className={`nav-button ${activeTab === 'embeddings' ? 'active' : ''}`}
                    onClick={() => handleTabClick('embeddings')}
                  >
                    AI Embeddings
                  </button>
                </>
              )}
            </nav>

            <div className="navbar-user-section">
              <div className="user-badge">
                <span className="user-name">{currentUser.full_name}</span>
                <span className={`user-role-tag ${currentUser.role}`}>
                  {currentUser.role}
                </span>
              </div>
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
