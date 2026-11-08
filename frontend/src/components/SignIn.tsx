import React, { useState } from 'react';

interface SignInProps {
  onLogin: (email: string, pass: string) => Promise<void>;
  loading: boolean;
  error: string | null;
  onSwitchToRegister?: () => void;
  onSwitchToForgotPassword?: () => void;
}

export const SignIn: React.FC<SignInProps> = ({
  onLogin,
  loading,
  error,
  onSwitchToRegister,
  onSwitchToForgotPassword,
}) => {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) return;
    await onLogin(identifier.trim(), password);
  };

  return (
    <div className="signin-page-wrapper">
      <div className="signin-card">
        <div className="signin-header">
          <h2>AI Library Management System</h2>
          <p>Sign in using your institutional email or username to access your account</p>
        </div>

        <div className="signin-body">
          {error && (
            <div className="alert alert-error" role="alert">
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="signin-identifier" className="form-label">
                Email Address or Username
              </label>
              <input
                id="signin-identifier"
                type="text"
                className="form-input"
                placeholder="name@example.com or username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label htmlFor="signin-password" className="form-label">
                  Password
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  {onSwitchToForgotPassword && (
                    <button
                      type="button"
                      onClick={onSwitchToForgotPassword}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--brand-secondary)',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        padding: 0,
                      }}
                    >
                      Forgot?
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted)',
                      fontSize: '0.78rem',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>
              <input
                id="signin-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>

            <div style={{ marginTop: '0.85rem', marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #77829E)', marginBottom: '0.35rem', textAlign: 'center' }}>
                ⚡ Quick Demo Pre-fill:
              </div>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                <button
                  type="button"
                  onClick={() => {
                    setIdentifier('student1');
                    setPassword('StudentPass123!');
                  }}
                  style={{
                    flex: 1,
                    padding: '0.35rem 0.2rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-medium, #29334F)',
                    background: 'var(--bg-subtle, #1D2742)',
                    color: 'var(--text-primary, #F5F6FF)',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                  }}
                >
                  🎓 Student
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIdentifier('teacher1');
                    setPassword('TeacherPass123!');
                  }}
                  style={{
                    flex: 1,
                    padding: '0.35rem 0.2rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-medium, #29334F)',
                    background: 'var(--bg-subtle, #1D2742)',
                    color: 'var(--text-primary, #F5F6FF)',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                  }}
                >
                  🧑‍🏫 Teacher
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIdentifier('librarian1');
                    setPassword('AdminPass123!');
                  }}
                  style={{
                    flex: 1,
                    padding: '0.35rem 0.2rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-medium, #29334F)',
                    background: 'var(--bg-subtle, #1D2742)',
                    color: 'var(--text-primary, #F5F6FF)',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                  }}
                >
                  🏛️ Librarian
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '0.5rem', padding: '0.65rem' }}
              disabled={loading || !identifier.trim() || !password}
            >
              {loading ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>

          {onSwitchToRegister && (
            <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--card-border)', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <span>Need an account? </span>
              <button
                type="button"
                onClick={onSwitchToRegister}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--brand-secondary)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: 0,
                  textDecoration: 'underline',
                }}
              >
                Create Account
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
