import React, { useState } from 'react';
import { apiFetch } from '../services/apiClient';

interface ResetPasswordProps {
  token: string;
  onSuccessToLogin: () => void;
  onRequestNewLink: () => void;
}

export const ResetPassword: React.FC<ResetPasswordProps> = ({
  token,
  onSuccessToLogin,
  onRequestNewLink,
}) => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cleanToken = token.trim();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!cleanToken) {
      setError('Password reset token is missing from the URL.');
      return;
    }

    if (password.length < 12) {
      setError('Password must be at least 12 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter your password.');
      return;
    }

    setLoading(true);

    try {
      await apiFetch<{ message: string }>('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({
          token: cleanToken,
          new_password: password,
          confirm_password: confirmPassword,
        }),
      });
      setSuccess(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset password.';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  };

  if (!cleanToken) {
    return (
      <div className="signin-page-wrapper">
        <div className="signin-card">
          <div className="signin-header">
            <h2>Invalid Reset Link</h2>
            <p>The password reset link is malformed or missing required security parameters.</p>
          </div>
          <div className="signin-body" style={{ textAlign: 'center', padding: '1rem 0' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>⚠️</div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
              Please request a new reset link from the password recovery page.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onRequestNewLink}
              style={{ width: '100%', padding: '0.65rem', marginBottom: '0.75rem' }}
            >
              Request New Reset Link
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onSuccessToLogin}
              style={{ width: '100%', padding: '0.65rem' }}
            >
              Back to Sign In
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="signin-page-wrapper">
      <div className="signin-card">
        <div className="signin-header">
          <h2>Establish New Password</h2>
          <p>Create a secure password of at least 12 characters for your account</p>
        </div>

        <div className="signin-body">
          {error && (
            <div className="alert alert-error" role="alert" style={{ marginBottom: '1rem' }}>
              <span>{error}</span>
            </div>
          )}

          {success ? (
            <div style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>✅</div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Password Updated Successfully
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                Your account credentials have been securely updated. You can now sign in using your new password.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={onSuccessToLogin}
                style={{ width: '100%', padding: '0.65rem' }}
              >
                Proceed to Sign In
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate>
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label htmlFor="new-password" className="form-label">
                    New Password
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
                  id="new-password"
                  type={showPassword ? 'text' : 'password'}
                  className="form-input"
                  placeholder="Minimum 12 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.35rem', fontSize: '0.78rem' }}>
                  <span style={{ color: password.length >= 12 ? '#10b981' : 'var(--text-muted)' }}>
                    {password.length >= 12 ? '✓' : '○'} At least 12 characters ({password.length}/12)
                  </span>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="confirm-new-password" className="form-label">
                  Confirm New Password
                </label>
                <input
                  id="confirm-new-password"
                  type={showPassword ? 'text' : 'password'}
                  className="form-input"
                  placeholder="Re-enter your new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
                {confirmPassword && (
                  <div style={{ marginTop: '0.35rem', fontSize: '0.78rem' }}>
                    {password === confirmPassword ? (
                      <span style={{ color: '#10b981' }}>✓ Passwords match</span>
                    ) : (
                      <span style={{ color: '#ef4444' }}>✗ Passwords do not match</span>
                    )}
                  </div>
                )}
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '0.75rem', padding: '0.65rem' }}
                disabled={loading || password.length < 12 || password !== confirmPassword}
              >
                {loading ? 'Updating Password...' : 'Reset Password'}
              </button>

              <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--card-border)', textAlign: 'center', fontSize: '0.85rem' }}>
                <button
                  type="button"
                  onClick={onSuccessToLogin}
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
                  Return to Sign In
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

