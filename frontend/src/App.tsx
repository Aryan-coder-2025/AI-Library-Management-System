import React, { useEffect, useState } from 'react';
import { apiFetch } from './services/apiClient';
import type { UserProfile } from './types/library';
import { Navbar } from './components/Navbar';
import { SignIn } from './components/SignIn';
import { StudentCatalogue } from './components/StudentCatalogue';
import { SemanticSearch } from './components/SemanticSearch';
import { StudentLoans } from './components/StudentLoans';
import { StudentSpaces } from './components/StudentSpaces';
import { LibrarianCatalogue } from './components/LibrarianCatalogue';
import { LibrarianCirculation } from './components/LibrarianCirculation';
import { LibrarianEmbeddings } from './components/LibrarianEmbeddings';
import { LibrarianSpaces } from './components/LibrarianSpaces';
import { BookDetailModal } from './components/BookDetailModal';
import { AICopilotDrawer } from './components/AICopilotDrawer';
import { GuidedTourModal } from './components/GuidedTourModal';
import { PatronProfileModal } from './components/PatronProfileModal';
import { KnowledgeExplorer } from './components/knowledge/KnowledgeExplorer';
import { ModelComparisonStudio } from './components/knowledge/ModelComparisonStudio';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Active navigation tab
  const [activeTab, setActiveTab] = useState<string>('catalogue');

  // Book Detail Modal state
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);

  // AI Copilot & Guided Tour state
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [isTourOpen, setIsTourOpen] = useState(false);

  // Patron Profile state
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Check existing session on load
  useEffect(() => {
    apiFetch<UserProfile>('/api/auth/me')
      .then((user) => {
        setCurrentUser(user);
        setAuthLoading(false);
      })
      .catch(() => {
        setCurrentUser(null);
        setAuthLoading(false);
      });
  }, []);

  // Show guided onboarding tour on first login
  useEffect(() => {
    if (currentUser) {
      try {
        const hasSeenTour = localStorage.getItem('ai_library_tour_completed');
        if (!hasSeenTour) {
          setIsTourOpen(true);
        }
      } catch {
        // Ignore localStorage restrictions
      }
    }
  }, [currentUser]);

  const handleLogin = async (email: string, pass: string) => {
    setIsLoggingIn(true);
    setLoginError(null);

    try {
      const user = await apiFetch<UserProfile>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password: pass }),
      });
      setCurrentUser(user);
      setActiveTab('catalogue');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid credentials';
      setLoginError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // Ignore logout errors
    } finally {
      setCurrentUser(null);
      setActiveTab('catalogue');
      setSelectedBookId(null);
      setIsCopilotOpen(false);
      setIsTourOpen(false);
      setIsProfileOpen(false);
    }
  };

  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        Verifying session...
      </div>
    );
  }

  const isPatron = currentUser?.role === 'student' || currentUser?.role === 'teacher';

  return (
    <div className="app-shell">
      <Navbar
        currentUser={currentUser}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onLogout={handleLogout}
        onOpenTour={() => setIsTourOpen(true)}
        onOpenCopilot={() => setIsCopilotOpen(true)}
        onOpenProfile={() => setIsProfileOpen(true)}
      />

      <main className="main-content">
        {!currentUser ? (
          activeTab === 'login' ? (
            <div>
              <div style={{ maxWidth: '420px', margin: '0 auto 1rem', display: 'flex', justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab('catalogue')}
                >
                  ← Back to Public Catalogue
                </button>
              </div>
              <SignIn
                onLogin={handleLogin}
                loading={isLoggingIn}
                error={loginError}
              />
            </div>
          ) : (
            <div>
              <div className="alert alert-info" style={{ marginBottom: '1.25rem' }}>
                <div>
                  <strong>Public OPAC Mode:</strong> You are browsing the catalogue as a guest. Physical copy barcodes and borrower status are hidden. Sign in with your patron credentials to borrow books or access semantic search and account history.
                </div>
              </div>
              <StudentCatalogue onSelectBook={(id) => setSelectedBookId(id)} />
            </div>
          )
        ) : (
          <>
            {/* Patron & Shared Views */}
            {activeTab === 'catalogue' && (
              <StudentCatalogue onSelectBook={(id) => setSelectedBookId(id)} />
            )}

            {activeTab === 'semantic' && (
              <SemanticSearch
                onSelectBook={(id) => setSelectedBookId(id)}
                onGoToCatalogue={() => setActiveTab('catalogue')}
              />
            )}

            {activeTab === 'loans' && isPatron && (
              <StudentLoans currentUser={currentUser} />
            )}

            {activeTab === 'spaces' && isPatron && (
              <StudentSpaces currentUser={currentUser} />
            )}

            {activeTab === 'knowledge' && (
              <KnowledgeExplorer />
            )}

            {/* Librarian-Only Views */}
            {activeTab === 'manage_catalogue' && currentUser.role === 'librarian' && (
              <LibrarianCatalogue />
            )}

            {activeTab === 'circulation' && currentUser.role === 'librarian' && (
              <LibrarianCirculation />
            )}

            {activeTab === 'space_management' && currentUser.role === 'librarian' && (
              <LibrarianSpaces />
            )}

            {activeTab === 'embeddings' && currentUser.role === 'librarian' && (
              <LibrarianEmbeddings />
            )}

            {activeTab === 'ai_studio' && currentUser.role === 'librarian' && (
              <ModelComparisonStudio />
            )}
          </>
        )}
      </main>

      {/* Global Book Detail Modal (Available to both authenticated users and public guests) */}
      {selectedBookId !== null && (
        <BookDetailModal
          bookId={selectedBookId}
          onClose={() => setSelectedBookId(null)}
          onSelectBook={(id) => setSelectedBookId(id)}
        />
      )}

      {/* AI Library Copilot Drawer */}
      {currentUser && (
        <AICopilotDrawer
          currentUser={currentUser}
          isOpen={isCopilotOpen}
          onClose={() => setIsCopilotOpen(false)}
          onOpen={() => setIsCopilotOpen(true)}
          onSelectBook={(id) => {
            setSelectedBookId(id);
          }}
        />
      )}

      {/* First-Time Guided Assistant Tour Modal */}
      {currentUser && (
        <GuidedTourModal
          currentUser={currentUser}
          isOpen={isTourOpen}
          onClose={() => setIsTourOpen(false)}
          onNavigateTab={(tab) => setActiveTab(tab)}
        />
      )}

      {/* Patron Profile & Password Management Modal (PORT-06) */}
      {currentUser && (
        <PatronProfileModal
          currentUser={currentUser}
          isOpen={isProfileOpen}
          onClose={() => setIsProfileOpen(false)}
          onProfileUpdated={(updated) => setCurrentUser(updated)}
          onRequireRelogin={() => {
            setCurrentUser(null);
            setIsProfileOpen(false);
            setActiveTab('login');
          }}
        />
      )}
    </div>
  );
};

export default App;
