import React, { useState } from 'react';

interface RegisterProps {
  onRegister: (data: {
    fullName: string;
    email: string;
    username: string;
    pass: string;
    confirmPass: string;
    role?: 'student' | 'teacher' | 'librarian';
    verificationKey?: string;
  }) => Promise<void>;
  loading: boolean;
  error: string | null;
  onSwitchToLogin: () => void;
}

export const Register: React.FC<RegisterProps> = ({
  onRegister,
  loading,
  error,
  onSwitchToLogin,
}) => {
  const [role, setRole] = useState<'student' | 'teacher' | 'librarian'>('student');
  const [verificationKey, setVerificationKey] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setClientError(null);

    const cleanName = fullName.trim();
    const cleanEmail = email.trim();
    const cleanUsername = username.trim().toLowerCase();

    if (!cleanName || cleanName.length < 2) {
      setClientError('Full name must be at least 2 characters long.');
      return;
    }
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setClientError('Please enter a valid email address.');
      return;
    }
    if (cleanUsername.length < 3 || cleanUsername.length > 20) {
      setClientError('Username must be between 3 and 20 characters long.');
      return;
    }
    if (!/^[a-z0-9._-]+$/.test(cleanUsername)) {
      setClientError('Username may only contain letters, numbers, periods (.), underscores (_), and hyphens (-).');
      return;
    }
    if (password.length < 12) {
      setClientError('Password must be at least 12 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setClientError('Passwords do not match.');
      return;
    }

    await onRegister({
      fullName: cleanName,
      email: cleanEmail,
      username: cleanUsername,
      pass: password,
      confirmPass: confirmPassword,
      role,
      verificationKey: verificationKey.trim(),
    });
  };

  const displayedError = clientError || error;

  return (
    <div className="signin-page-wrapper">
      <div className="signin-card" style={{ maxWidth: '480px' }}>
        <div className="signin-header">
          <h2>
            {role === 'student' && 'Create Student Account'}
            {role === 'teacher' && 'Create Faculty Account'}
            {role === 'librarian' && 'Create Staff Librarian Account'}
          </h2>
          <p>
            {role === 'student' && 'Register as an Athenaeum scholar to borrow books, reserve study spaces, and use AI features'}
            {role === 'teacher' && 'Register as an Athenaeum faculty member to curate syllabus reserves and manage reading lists'}
            {role === 'librarian' && 'Register as a library administrator to manage circulation, forecasting, and models'}
          </p>
        </div>

        <div className="signin-body">
          {displayedError && (
            <div className="alert alert-error" role="alert" style={{ marginBottom: '1rem' }}>
              <span>{displayedError}</span>
            </div>
          )}

          {/* Role Selection Pills */}
          <div
            style={{
              display: 'flex',
              gap: '0.35rem',
              marginBottom: '1.25rem',
              background: 'var(--bg-subtle, #1D2742)',
              padding: '0.3rem',
              borderRadius: '12px',
              border: '1px solid var(--border-subtle, #1E293B)',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setRole('student');
                setClientError(null);
              }}
              style={{
                flex: 1,
                padding: '0.45rem',
                borderRadius: '8px',
                border: 'none',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: role === 'student' ? 'var(--color-primary, #8057F5)' : 'transparent',
                color: role === 'student' ? '#ffffff' : 'var(--text-secondary, #A9B2CC)',
                transition: 'all 0.15s ease',
              }}
            >
              🎓 Student
            </button>
            <button
              type="button"
              onClick={() => {
                setRole('teacher');
                setClientError(null);
              }}
              style={{
                flex: 1,
                padding: '0.45rem',
                borderRadius: '8px',
                border: 'none',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: role === 'teacher' ? 'var(--color-primary, #8057F5)' : 'transparent',
                color: role === 'teacher' ? '#ffffff' : 'var(--text-secondary, #A9B2CC)',
                transition: 'all 0.15s ease',
              }}
            >
              🧑‍🏫 Teacher
            </button>
            <button
              type="button"
              onClick={() => {
                setRole('librarian');
                setClientError(null);
              }}
              style={{
                flex: 1,
                padding: '0.45rem',
                borderRadius: '8px',
                border: 'none',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: role === 'librarian' ? 'var(--color-primary, #8057F5)' : 'transparent',
                color: role === 'librarian' ? '#ffffff' : 'var(--text-secondary, #A9B2CC)',
                transition: 'all 0.15s ease',
              }}
            >
              🏛️ Librarian
            </button>
          </div>

          <form onSubmit={handleSubmit} noValidate>
            {role !== 'student' && (
              <div
                className="form-group"
                style={{
                  background: 'var(--bg-surface-elevated, #171D35)',
                  padding: '0.75rem',
                  borderRadius: '10px',
                  border: '1px solid var(--border-medium, #29334F)',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <label htmlFor="reg-key" className="form-label" style={{ margin: 0, fontWeight: 600 }}>
                    Institutional Verification Key
                  </label>
                  <span style={{ fontSize: '0.72rem', color: 'var(--color-secondary-violet, #A78BFA)' }}>
                    {role === 'teacher' ? 'Faculty Passkey' : 'Staff Admin Passkey'}
                  </span>
                </div>
                <input
                  id="reg-key"
                  type="text"
                  className="form-input"
                  placeholder={role === 'teacher' ? 'e.g. FACULTY-2026 or invite code...' : 'e.g. LIBRARIAN-2026...'}
                  value={verificationKey}
                  onChange={(e) => setVerificationKey(e.target.value)}
                />
                <div style={{ marginTop: '0.4rem', fontSize: '0.72rem', color: 'var(--text-muted, #77829E)' }}>
                  💡 Demo Passkey: <strong>{role === 'teacher' ? 'FACULTY-2026' : 'LIBRARIAN-2026'}</strong> (or leave blank if your email was authorized by librarian).
                </div>
              </div>
            )}
            <div className="form-group">
              <label htmlFor="reg-fullname" className="form-label">
                Full Name
              </label>
              <input
                id="reg-fullname"
                type="text"
                className="form-input"
                placeholder="e.g. Marie Curie"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="reg-email" className="form-label">
                Institutional / Personal Email
              </label>
              <input
                id="reg-email"
                type="email"
                className="form-input"
                placeholder="scholar@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="reg-username" className="form-label">
                Username
              </label>
              <input
                id="reg-username"
                type="text"
                className="form-input"
                placeholder="3–20 chars (e.g. marie.curie)"
                value={username}
                onChange={(e) => setUsername(e.target.value.toLowerCase())}
                autoComplete="username"
                required
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', display: 'block' }}>
                Letters, numbers, periods, underscores, or hyphens.
              </span>
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label htmlFor="reg-password" className="form-label">
                  Password (min. 12 characters)
                </label>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--brand-secondary)',
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <input
                id="reg-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                placeholder="At least 12 characters..."
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="reg-confirm-password" className="form-label">
                Confirm Password
              </label>
              <input
                id="reg-confirm-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                placeholder="Re-enter password..."
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>

            <div style={{ margin: '0.75rem 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              {role === 'student' && (
                <span>🔒 Public registration automatically provisions an authenticated <strong>Student Scholar</strong> profile.</span>
              )}
              {role === 'teacher' && (
                <span>🧑‍🏫 Faculty registration grants access to the <strong>Teacher Portal</strong> to curate course reading lists.</span>
              )}
              {role === 'librarian' && (
                <span>🏛️ Staff registration grants administrative access to <strong>Circulation Desk</strong> and <strong>Forecasting</strong>.</span>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '0.5rem', padding: '0.65rem' }}
              disabled={loading || !fullName.trim() || !email.trim() || !username.trim() || password.length < 12}
            >
              {loading ? 'Creating Account...' : 'Complete Registration'}
            </button>
          </form>

          <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--card-border)', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <span>Already have an account? </span>
            <button
              type="button"
              onClick={onSwitchToLogin}
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
              Sign In
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
