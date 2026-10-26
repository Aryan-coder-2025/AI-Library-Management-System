import { useEffect, useState } from 'react';
import { apiFetch } from './services/apiClient';

interface HealthData {
  status: string;
  project_name: string;
  environment: string;
  database: string;
}

interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export function App() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // Authentication State
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);
  const [emailInput, setEmailInput] = useState<string>('');
  const [passwordInput, setPasswordInput] = useState<string>('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  useEffect(() => {
    // 1. Fetch system health
    apiFetch<HealthData>('/api/health')
      .then((data) => {
        setHealth(data);
        setHealthLoading(false);
      })
      .catch((err) => {
        setHealthError(err.message || 'Failed to connect to backend service');
        setHealthLoading(false);
      });

    // 2. Check existing session
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

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsSubmitting(true);

    try {
      const user = await apiFetch<UserProfile>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: emailInput,
          password: passwordInput,
        }),
      });
      setCurrentUser(user);
      setPasswordInput('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed';
      setLoginError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // Ignore logout errors
    } finally {
      setCurrentUser(null);
      setEmailInput('');
      setPasswordInput('');
      setLoginError(null);
    }
  };

  return (
    <div className="app-container">
      <header className="header-banner">
        <h1>AI Library Management System</h1>
        <p>Stage 2: Authentication & Role-Based Access Control</p>
      </header>

      <div className="card-grid">
        {/* Card 1: Authentication / Session */}
        <div className="status-card">
          <h3>User Authentication & Session</h3>
          {authLoading ? (
            <span className="status-badge loading">Checking session...</span>
          ) : currentUser ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <span className={`role-badge ${currentUser.role}`}>{currentUser.role}</span>
                <button type="button" className="btn-secondary" onClick={handleLogout}>
                  Log Out
                </button>
              </div>
              <table className="meta-table">
                <tbody>
                  <tr>
                    <td>Name:</td>
                    <td>{currentUser.full_name}</td>
                  </tr>
                  <tr>
                    <td>Email:</td>
                    <td>{currentUser.email}</td>
                  </tr>
                  <tr>
                    <td>Status:</td>
                    <td>{currentUser.is_active ? 'Active' : 'Inactive'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <form className="auth-form" onSubmit={handleLogin}>
              <div className="form-group">
                <label htmlFor="email">Email Address</label>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  placeholder="student@university.edu"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  required
                />
              </div>
              {loginError && <div className="alert-error">{loginError}</div>}
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? 'Authenticating...' : 'Sign In'}
              </button>
            </form>
          )}
        </div>

        {/* Card 2: Backend & Database Health */}
        <div className="status-card">
          <h3>Backend & Database Health</h3>
          {healthLoading && <span className="status-badge loading">Connecting...</span>}
          {healthError && <span className="status-badge loading" style={{ color: '#ef4444' }}>Offline ({healthError})</span>}
          {health && (
            <>
              <span className="status-badge healthy">{health.status}</span>
              <table className="meta-table">
                <tbody>
                  <tr>
                    <td>Database Status:</td>
                    <td>{health.database}</td>
                  </tr>
                  <tr>
                    <td>Environment:</td>
                    <td>{health.environment}</td>
                  </tr>
                  <tr>
                    <td>Project:</td>
                    <td>{health.project_name}</td>
                  </tr>
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* Card 3: Security & RBAC Guards */}
        <div className="status-card">
          <h3>Security & RBAC Guards</h3>
          <table className="meta-table">
            <tbody>
              <tr>
                <td>Auth Mechanism:</td>
                <td>HttpOnly JWT Cookie (8h)</td>
              </tr>
              <tr>
                <td>CSRF Protection:</td>
                <td>Double Submit Cookie</td>
              </tr>
              <tr>
                <td>Roles Supported:</td>
                <td>Student, Librarian</td>
              </tr>
              <tr>
                <td>Password Hashing:</td>
                <td>Bcrypt (Rounds: 12)</td>
              </tr>
              <tr>
                <td>Bootstrap CLI:</td>
                <td>Interactive (No public endpoint)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default App;
