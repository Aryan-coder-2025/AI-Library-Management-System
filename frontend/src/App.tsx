import React, { useEffect, useState } from 'react';
import { apiFetch } from './services/apiClient';
import type { UserProfile } from './types/library';
import { getInitialTheme, applyTheme, type ThemeMode } from './services/theme';
import { Navbar } from './components/Navbar';
import { SignIn } from './components/SignIn';
import { Register } from './components/Register';
import { ForgotPassword } from './components/ForgotPassword';
import { ResetPassword } from './components/ResetPassword';
import { DashboardView } from './components/DashboardView';
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
import { CommandPalette } from './components/CommandPalette';
import { KnowledgeExplorer } from './components/knowledge/KnowledgeExplorer';
import { ModelComparisonStudio } from './components/knowledge/ModelComparisonStudio';
import { TeacherPortal } from './components/TeacherPortal';
import { LibrarianIntelligenceCenter } from './components/intelligence/LibrarianIntelligenceCenter';
import { InactivityMonitor } from './components/InactivityMonitor';
import { SystemArchitectureAuditModal } from './components/SystemArchitectureAuditModal';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [isRegistering, setIsRegistering] = useState(false);
  const [resetToken, setResetToken] = useState<string | null>(null);

  // Active navigation tab (defaults to login for unauthenticated arrivals)
  const [activeTab, setActiveTab] = useState<string>('login');

  // Book Detail Modal state
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);

  // AI Copilot & Guided Tour state
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [isTourOpen, setIsTourOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);

  // Patron Profile state
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Global Command Palette state
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  // Theme Management (Midnight Intelligence / Academic Aurora)
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme: ThemeMode = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    applyTheme(nextTheme);
  };

  // Keyboard Shortcuts (Ctrl+K: Command Palette, Ctrl+J: AI Copilot)
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        setIsCopilotOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // Check existing session on load and detect password recovery token in URL
  useEffect(() => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const tokenParam = urlParams.get('reset_token') || urlParams.get('token');
      if (tokenParam) {
        setResetToken(tokenParam);
        setActiveTab('reset_password');
      }
    } catch {
      // Ignore URL parsing errors
    }

    apiFetch<UserProfile>('/api/auth/me')
      .then((user) => {
        setCurrentUser(user);
        setAuthLoading(false);
        setActiveTab('dashboard');
      })
      .catch(() => {
        setCurrentUser(null);
        setAuthLoading(false);
        setActiveTab('login');
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

  const handleLogin = async (email: string, pass: string, isPublicDevice?: boolean) => {
    setIsLoggingIn(true);
    setLoginError(null);

    try {
      const user = await apiFetch<UserProfile>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password: pass,
          is_public_device: Boolean(isPublicDevice),
        }),
      });
      setCurrentUser(user);
      setActiveTab('dashboard');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid credentials';
      setLoginError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleRegister = async (data: {
    fullName: string;
    email: string;
    username: string;
    pass: string;
    confirmPass: string;
    role?: 'student' | 'teacher' | 'librarian';
    verificationKey?: string;
  }) => {
    setIsRegistering(true);
    setRegisterError(null);

    const isInstitutional = data.role && data.role !== 'student';
    const endpoint = isInstitutional
      ? '/api/auth/register/institutional'
      : '/api/auth/register';

    const payload = isInstitutional
      ? {
          full_name: data.fullName,
          email: data.email,
          username: data.username,
          password: data.pass,
          confirm_password: data.confirmPass,
          role: data.role,
          verification_key: data.verificationKey || undefined,
        }
      : {
          full_name: data.fullName,
          email: data.email,
          username: data.username,
          password: data.pass,
          confirm_password: data.confirmPass,
        };

    try {
      const user = await apiFetch<UserProfile>(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setCurrentUser(user);
      setActiveTab('dashboard');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed';
      setRegisterError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsRegistering(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // Ignore logout errors
    } finally {
      setCurrentUser(null);
      setActiveTab('dashboard');
      setSelectedBookId(null);
      setIsCopilotOpen(false);
      setIsTourOpen(false);
      setIsProfileOpen(false);
      setIsCommandPaletteOpen(false);
    }
  };

  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '2rem' }}>🏛️</span>
          <span style={{ letterSpacing: '0.05em', fontWeight: 600 }}>INITIALIZING ATHENAEUM PLATFORM...</span>
        </div>
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
        onOpenAuditModal={() => setIsAuditModalOpen(true)}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        currentTheme={theme}
        onToggleTheme={toggleTheme}
        onSelectBook={(bookId) => setSelectedBookId(bookId)}
      />

      <main className="main-content">
        {!currentUser ? (
          activeTab === 'login' ? (
            <div>
              <div style={{ maxWidth: '420px', margin: '0 auto 1rem', display: 'flex', justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab('dashboard')}
                >
                  ← Back to Academic Portal
                </button>
              </div>
              <SignIn
                onLogin={handleLogin}
                loading={isLoggingIn}
                error={loginError}
                onSwitchToRegister={() => {
                  setLoginError(null);
                  setRegisterError(null);
                  setActiveTab('register');
                }}
                onSwitchToForgotPassword={() => {
                  setLoginError(null);
                  setRegisterError(null);
                  setActiveTab('forgot_password');
                }}
              />
            </div>
          ) : activeTab === 'forgot_password' ? (
            <div>
              <div style={{ maxWidth: '420px', margin: '0 auto 1rem', display: 'flex', justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab('dashboard')}
                >
                  ← Back to Academic Portal
                </button>
              </div>
              <ForgotPassword
                onBackToLogin={() => {
                  setLoginError(null);
                  setActiveTab('login');
                }}
              />
            </div>
          ) : activeTab === 'reset_password' ? (
            <div>
              <div style={{ maxWidth: '420px', margin: '0 auto 1rem', display: 'flex', justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab('dashboard')}
                >
                  ← Back to Academic Portal
                </button>
              </div>
              <ResetPassword
                token={resetToken || ''}
                onSuccessToLogin={() => {
                  setLoginError(null);
                  setResetToken(null);
                  // Clean URL query parameter
                  try {
                    window.history.replaceState({}, document.title, window.location.pathname);
                  } catch {
                    // Ignore history errors
                  }
                  setActiveTab('login');
                }}
                onRequestNewLink={() => {
                  setResetToken(null);
                  try {
                    window.history.replaceState({}, document.title, window.location.pathname);
                  } catch {
                    // Ignore history errors
                  }
                  setActiveTab('forgot_password');
                }}
              />
            </div>
          ) : activeTab === 'register' ? (
            <div>
              <div style={{ maxWidth: '480px', margin: '0 auto 1rem', display: 'flex', justifyContent: 'flex-start' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab('dashboard')}
                >
                  ← Back to Academic Portal
                </button>
              </div>
              <Register
                onRegister={handleRegister}
                loading={isRegistering}
                error={registerError}
                onSwitchToLogin={() => {
                  setLoginError(null);
                  setRegisterError(null);
                  setActiveTab('login');
                }}
              />
            </div>
          ) : activeTab === 'catalogue' ? (
            <div>
              <div className="alert alert-info" style={{ marginBottom: '1.25rem' }}>
                <div>
                  <strong>Public OPAC Mode:</strong> You are browsing the catalogue as a guest scholar. Sign in with your university credentials to borrow books or access semantic search and account history.
                </div>
              </div>
              <StudentCatalogue onSelectBook={(id) => setSelectedBookId(id)} />
            </div>
          ) : activeTab === 'semantic' ? (
            <SemanticSearch
              onSelectBook={(id) => setSelectedBookId(id)}
              onGoToCatalogue={() => setActiveTab('catalogue')}
            />
          ) : activeTab === 'knowledge' ? (
            <KnowledgeExplorer />
          ) : (
            <DashboardView
              currentUser={null}
              onSelectTab={setActiveTab}
              onOpenCopilot={() => setActiveTab('login')}
              onSelectBook={(id) => setSelectedBookId(id)}
            />
          )
        ) : (
          <>
            {/* Unified Academic Dashboard */}
            {activeTab === 'dashboard' && (
              <DashboardView
                currentUser={currentUser}
                onSelectTab={setActiveTab}
                onOpenCopilot={() => setIsCopilotOpen(true)}
                onSelectBook={(id) => setSelectedBookId(id)}
                onLogout={handleLogout}
              />
            )}

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

            {/* Teacher Portal (PORT-03 & INTEL-06) */}
            {activeTab === 'teacher_portal' && (currentUser.role === 'teacher' || currentUser.role === 'librarian') && (
              <TeacherPortal currentUser={currentUser} />
            )}

            {/* Librarian-Only Views */}
            {activeTab === 'intelligence' && currentUser.role === 'librarian' && (
              <LibrarianIntelligenceCenter />
            )}

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

      {/* Global Book Detail Modal */}
      {selectedBookId !== null && (
        <BookDetailModal
          bookId={selectedBookId}
          onClose={() => setSelectedBookId(null)}
          onSelectBook={(id) => setSelectedBookId(id)}
          onNavigateToLoans={() => {
            setSelectedBookId(null);
            setActiveTab('loans');
          }}
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
          onNavigateTab={(tab) => setActiveTab(tab)}
          onOpenAuditModal={() => setIsAuditModalOpen(true)}
        />
      )}

      {/* Global Command Palette (Ctrl+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectTab={setActiveTab}
        onOpenCopilot={() => setIsCopilotOpen(true)}
        onOpenProfile={() => setIsProfileOpen(true)}
        onOpenTour={() => setIsTourOpen(true)}
        onToggleTheme={toggleTheme}
        currentTheme={theme}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

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

      {/* Teacher Defense & System Architecture Audit Studio */}
      {isAuditModalOpen && (
        <SystemArchitectureAuditModal
          currentUser={currentUser}
          onClose={() => setIsAuditModalOpen(false)}
        />
      )}

      {/* Campus Workstation Inactivity & Session Auto-Logout Monitor */}
      <InactivityMonitor
        isActive={!!currentUser}
        onLogout={handleLogout}
        timeoutMinutes={30}
        warningMinutes={25}
      />
    </div>
  );
};

export default App;
