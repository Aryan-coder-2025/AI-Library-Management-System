import React, { useState } from 'react';
import { apiFetch } from '../services/apiClient';

interface ForgotPasswordProps {
  onBackToLogin: () => void;
}

export const ForgotPassword: React.FC<ForgotPasswordProps> = ({ onBackToLogin }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setError('Please provide a valid institutional email address.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiFetch<{ message: string }>('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email: cleanEmail }),
      });
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An error occurred while submitting your request.';
      // Clean up leading error codes if returned by apiFetch
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="signin-page-wrapper">
      <div className="signin-card">
        <div className="signin-header">
          <h2>Password Recovery</h2>
          <p>Request a secure password reset link for your Athenaeum account</p>
        </div>

        <div className="signin-body">
          {error && (
            <div className="alert alert-error" role="alert" style={{ marginBottom: '1rem' }}>
              <span>{error}</span>
            </div>
          )}

          {submitted ? (
            <div style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📬</div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Instructions Dispatched
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                If an account with <strong>{email}</strong> exists, password reset instructions have been sent to your inbox.
                The link is valid for <strong>30 minutes</strong>.
              </p>
              <div style={{ padding: '0.75rem', background: 'var(--bg-glass)', borderRadius: '6px', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '1.5rem', border: '1px solid var(--card-border)' }}>
                Tip: Check your spam or quarantine folder if you do not receive the email shortly.
              </div>
              <button
                type="button"
                className="btn btn-primary"
                onClick={onBackToLogin}
                style={{ width: '100%', padding: '0.65rem' }}
              >
                Return to Sign In
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate>
              <div className="form-group">
                <label htmlFor="recovery-email" className="form-label">
                  Institutional Email Address
                </label>
                <input
                  id="recovery-email"
                  type="email"
                  className="form-input"
                  placeholder="patron@university.edu"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError(null);
                  }}
                  autoComplete="email"
                  required
                />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.35rem', display: 'block' }}>
                  Enter the email address associated with your library account.
                </span>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '0.75rem', padding: '0.65rem' }}
                disabled={loading || !email.trim()}
              >
                {loading ? 'Sending Instructions...' : 'Send Reset Link'}
              </button>

              <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--card-border)', textAlign: 'center', fontSize: '0.85rem' }}>
                <button
                  type="button"
                  onClick={onBackToLogin}
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
                  ← Back to Sign In
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

