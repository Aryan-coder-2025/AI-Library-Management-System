import React, { useEffect, useState } from 'react';
import { apiFetch } from './services/apiClient';
import type { UserProfile } from './types/library';
import { Navbar } from './components/Navbar';
import { SignIn } from './components/SignIn';
import { StudentCatalogue } from './components/StudentCatalogue';
import { SemanticSearch } from './components/SemanticSearch';
import { StudentLoans } from './components/StudentLoans';
import { LibrarianCatalogue } from './components/LibrarianCatalogue';
import { LibrarianCirculation } from './components/LibrarianCirculation';
import { LibrarianEmbeddings } from './components/LibrarianEmbeddings';
import { BookDetailModal } from './components/BookDetailModal';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Active navigation tab
  const [activeTab, setActiveTab] = useState<string>('catalogue');

  // Book Detail Modal state
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);

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
    }
  };

  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        Verifying session...
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Navbar
        currentUser={currentUser}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onLogout={handleLogout}
      />

      <main className="main-content">
        {!currentUser ? (
          <SignIn
            onLogin={handleLogin}
            loading={isLoggingIn}
            error={loginError}
          />
        ) : (
          <>
            {/* Student & Shared Views */}
            {activeTab === 'catalogue' && (
              <StudentCatalogue onSelectBook={(id) => setSelectedBookId(id)} />
            )}

            {activeTab === 'semantic' && (
              <SemanticSearch
                onSelectBook={(id) => setSelectedBookId(id)}
                onGoToCatalogue={() => setActiveTab('catalogue')}
              />
            )}

            {activeTab === 'loans' && currentUser.role === 'student' && (
              <StudentLoans />
            )}

            {/* Librarian-Only Views */}
            {activeTab === 'manage_catalogue' && currentUser.role === 'librarian' && (
              <LibrarianCatalogue />
            )}

            {activeTab === 'circulation' && currentUser.role === 'librarian' && (
              <LibrarianCirculation />
            )}

            {activeTab === 'embeddings' && currentUser.role === 'librarian' && (
              <LibrarianEmbeddings />
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
        />
      )}
    </div>
  );
};

export default App;
