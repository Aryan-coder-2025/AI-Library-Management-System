import React, { useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { UserProfile } from '../types/library';

interface PatronProfileModalProps {
  currentUser: UserProfile;
  isOpen: boolean;
  onClose: () => void;
  onProfileUpdated: (user: UserProfile) => void;
  onRequireRelogin?: () => void;
}

export const PatronProfileModal: React.FC<PatronProfileModalProps> = ({
  currentUser,
  isOpen,
  onClose,
  onProfileUpdated,
  onRequireRelogin,
}) => {
  const [fullName, setFullName] = useState<string>(currentUser.full_name);
  const [nameLoading, setNameLoading] = useState<boolean>(false);
  const [nameMessage, setNameMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [username, setUsername] = useState<string>(currentUser.username || '');
  const [usernameLoading, setUsernameLoading] = useState<boolean>(false);
  const [usernameMessage, setUsernameMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [pwdLoading, setPwdLoading] = useState<boolean>(false);
  const [pwdMessage, setPwdMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // BYOK (Bring Your Own Key) State for Students & Teachers
  const [customKey, setCustomKey] = useState<string>(() => {
    return typeof window !== 'undefined' ? (localStorage.getItem('patron_custom_gemini_key') || '') : '';
  });
  const [keyTesting, setKeyTesting] = useState<boolean>(false);
  const [keyMessage, setKeyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isKeySaved, setIsKeySaved] = useState<boolean>(() => {
    return typeof window !== 'undefined' ? Boolean(localStorage.getItem('patron_custom_gemini_key')) : false;
  });

  const handleTestKey = async () => {
    if (!customKey.trim()) {
      setKeyMessage({ type: 'error', text: 'Please enter a Gemini API Key to test.' });
      return;
    }
    setKeyTesting(true);
    setKeyMessage(null);
    try {
      const res = await apiFetch<{ valid: boolean; provider: string; message: string }>('/api/copilot/verify-key', {
        method: 'POST',
        body: JSON.stringify({ api_key: customKey.trim(), provider: 'gemini' }),
      });
      if (res.valid) {
        setKeyMessage({ type: 'success', text: `Key verified successfully! (${res.message})` });
      } else {
        setKeyMessage({ type: 'error', text: res.message });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to test key';
      setKeyMessage({ type: 'error', text: msg.replace(/^\d+:\s*/, '') });
    } finally {
      setKeyTesting(false);
    }
  };

  const handleSaveKey = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customKey.trim()) {
      setKeyMessage({ type: 'error', text: 'API key cannot be empty.' });
      return;
    }
    localStorage.setItem('patron_custom_gemini_key', customKey.trim());
    setIsKeySaved(true);
    setKeyMessage({ type: 'success', text: 'Personal Gemini API key saved! Used for all Copilot and Multimodal searches.' });
  };

  const handleRemoveKey = () => {
    localStorage.removeItem('patron_custom_gemini_key');
    setCustomKey('');
    setIsKeySaved(false);
    setKeyMessage({ type: 'success', text: 'Personal API key cleared. Reverted to institutional default.' });
  };

  if (!isOpen) return null;

  const handleUpdateName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameMessage(null);
    if (!fullName.trim()) {
      setNameMessage({ type: 'error', text: 'Full name cannot be empty.' });
      return;
    }

    try {
      setNameLoading(true);
      const updatedUser = await apiFetch<UserProfile>('/api/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ full_name: fullName.trim() }),
      });
      setNameMessage({ type: 'success', text: 'Profile name successfully updated.' });
      onProfileUpdated(updatedUser);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update name';
      setNameMessage({ type: 'error', text: msg.replace(/^\d+:\s*/, '') });
    } finally {
      setNameLoading(false);
    }
  };

  const handleUpdateUsername = async (e: React.FormEvent) => {
    e.preventDefault();
    setUsernameMessage(null);
    const cleanUsername = username.trim().toLowerCase();

    if (cleanUsername.length < 3 || cleanUsername.length > 20) {
      setUsernameMessage({ type: 'error', text: 'Username must be between 3 and 20 characters long.' });
      return;
    }
    if (!/^[a-z0-9._-]+$/.test(cleanUsername)) {
      setUsernameMessage({
        type: 'error',
        text: 'Username may only contain letters, numbers, periods (.), underscores (_), and hyphens (-).',
      });
      return;
    }

    try {
      setUsernameLoading(true);
      const updatedUser = await apiFetch<UserProfile>('/api/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ username: cleanUsername }),
      });
      setUsernameMessage({ type: 'success', text: 'Username handle successfully updated.' });
      onProfileUpdated(updatedUser);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update username';
      setUsernameMessage({ type: 'error', text: msg.replace(/^\d+:\s*/, '') });
    } finally {
      setUsernameLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdMessage(null);

    if (!currentPassword) {
      setPwdMessage({ type: 'error', text: 'Please enter your current password.' });
      return;
    }
    if (newPassword.length < 12) {
      setPwdMessage({ type: 'error', text: 'New password must be at least 12 characters long.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwdMessage({ type: 'error', text: 'New passwords do not match.' });
      return;
    }

    try {
      setPwdLoading(true);
      await apiFetch<{ message: string }>('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setPwdMessage({
        type: 'success',
        text: 'Password successfully changed! Your session has ended. Redirecting to sign in...',
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        if (onRequireRelogin) {
          onRequireRelogin();
        } else {
          onClose();
        }
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to change password';
      setPwdMessage({ type: 'error', text: msg.replace(/^\d+:\s*/, '') });
    } finally {
      setPwdLoading(false);
    }
  };

  const getPolicyBadge = () => {
    if (currentUser.role === 'teacher') {
      return 'Faculty Borrowing Policy: 10 active loans, 30 days per loan';
    }
    if (currentUser.role === 'librarian') {
      return 'Staff Administrator: Full circulation & catalogue authority';
    }
    return 'Student Borrowing Policy: 3 active loans, 14 days per loan';
  };

  return (
    <div
      className="modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1050,
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-dialog"
        style={{
          backgroundColor: 'var(--card-bg)',
          borderRadius: '16px',
          maxWidth: '560px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: 'var(--card-shadow)',
          border: '1px solid var(--card-border)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--card-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Account & Profile Settings
            </h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0' }}>
              Manage patron identity details, username handle, and password security
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              lineHeight: 1,
            }}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Read-Only Account Identity Card */}
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-tertiary)',
              borderRadius: '12px',
              border: '1px solid var(--card-border)',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Email Address
                </span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                  {currentUser.email}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Current Username
                </span>
                <div style={{ fontWeight: 600, color: currentUser.username ? 'var(--brand-secondary)' : 'var(--text-muted)', fontSize: '0.9rem' }}>
                  {currentUser.username ? `@${currentUser.username}` : 'Not set'}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Patron Role
                </span>
                <div>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      backgroundColor:
                        currentUser.role === 'teacher'
                          ? 'rgba(245, 158, 11, 0.15)'
                          : currentUser.role === 'librarian'
                          ? 'rgba(128, 87, 245, 0.15)'
                          : 'rgba(34, 211, 238, 0.15)',
                      color:
                        currentUser.role === 'teacher'
                          ? '#f59e0b'
                          : currentUser.role === 'librarian'
                          ? 'var(--brand-secondary)'
                          : 'var(--accent-cyan)',
                      textTransform: 'capitalize',
                    }}
                  >
                    {currentUser.role}
                  </span>
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Account Status
                </span>
                <div style={{ color: currentUser.is_active ? 'var(--status-success)' : 'var(--status-danger)', fontWeight: 600, fontSize: '0.85rem' }}>
                  {currentUser.is_active ? '● Active' : '● Inactive'}
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: '0.75rem',
                paddingTop: '0.75rem',
                borderTop: '1px solid var(--card-border)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
              }}
            >
              <strong>Policy: </strong>
              {getPolicyBadge()}
            </div>
          </div>

          {/* Section 1: Update Full Name */}
          <form onSubmit={handleUpdateName}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              Personal Information
            </h3>

            {nameMessage && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: nameMessage.type === 'success' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: nameMessage.type === 'success' ? '#22c55e' : '#ef4444',
                  border: `1px solid ${nameMessage.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                }}
              >
                {nameMessage.text}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label htmlFor="full-name-input" style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                Full Name
              </label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  id="full-name-input"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  style={{
                    flex: 1,
                    padding: '0.5rem 0.75rem',
                    border: '1px solid var(--card-border)',
                    borderRadius: '8px',
                    fontSize: '0.9rem',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                  }}
                  required
                />
                <button
                  type="submit"
                  disabled={nameLoading || fullName.trim() === currentUser.full_name}
                  className="btn btn-primary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {nameLoading ? 'Saving...' : 'Update Name'}
                </button>
              </div>
            </div>
          </form>

          {/* Section 2: Update Username Handle */}
          <form onSubmit={handleUpdateUsername}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              Username Handle
            </h3>

            {usernameMessage && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: usernameMessage.type === 'success' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: usernameMessage.type === 'success' ? '#22c55e' : '#ef4444',
                  border: `1px solid ${usernameMessage.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                }}
              >
                {usernameMessage.text}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label htmlFor="username-input" style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                Username (3–20 alphanumeric chars, '.', '_', '-')
              </label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  id="username-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value.toLowerCase())}
                  placeholder="e.g. marie.curie"
                  style={{
                    flex: 1,
                    padding: '0.5rem 0.75rem',
                    border: '1px solid var(--card-border)',
                    borderRadius: '8px',
                    fontSize: '0.9rem',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                  }}
                  required
                />
                <button
                  type="submit"
                  disabled={
                    usernameLoading ||
                    !username.trim() ||
                    username.trim().toLowerCase() === (currentUser.username || '').toLowerCase()
                  }
                  className="btn btn-primary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {usernameLoading ? 'Saving...' : 'Save Username'}
                </button>
              </div>
            </div>
          </form>

          {/* Section 3: Change Password */}
          <form onSubmit={handleChangePassword}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              Change Password (min. 12 characters)
            </h3>

            {pwdMessage && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: pwdMessage.type === 'success' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: pwdMessage.type === 'success' ? '#22c55e' : '#ef4444',
                  border: `1px solid ${pwdMessage.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                }}
              >
                {pwdMessage.text}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label
                  htmlFor="current-pwd-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '4px' }}
                >
                  Current Password
                </label>
                <input
                  id="current-pwd-input"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid var(--card-border)',
                    borderRadius: '8px',
                    fontSize: '0.9rem',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label
                  htmlFor="new-pwd-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '4px' }}
                >
                  New Password (min 12 characters)
                </label>
                <input
                  id="new-pwd-input"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 12 characters..."
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid var(--card-border)',
                    borderRadius: '8px',
                    fontSize: '0.9rem',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label
                  htmlFor="confirm-pwd-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '4px' }}
                >
                  Confirm New Password
                </label>
                <input
                  id="confirm-pwd-input"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid var(--card-border)',
                    borderRadius: '8px',
                    fontSize: '0.9rem',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={pwdLoading || !currentPassword || newPassword.length < 12 || newPassword !== confirmPassword}
                className="btn btn-primary"
                style={{ marginTop: '0.5rem' }}
              >
                {pwdLoading ? 'Updating Password...' : 'Update Password'}
              </button>
            </div>
          </form>

          {/* Section 4: Bring Your Own Key (BYOK) - AI Preferences */}
          <form onSubmit={handleSaveKey}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                🔑 Custom AI Key (BYOK)
              </h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontWeight: 600,
                  backgroundColor: isKeySaved ? 'rgba(34, 197, 94, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                  color: isKeySaved ? '#22c55e' : 'var(--accent-cyan)',
                }}
              >
                {isKeySaved ? '● Personal Key Active' : '● Institutional Default'}
              </span>
            </div>

            <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.4 }}>
              Students and teachers can use their personal Google Gemini API key for AI Copilot conversations and Multimodal Research Discovery. Keys are stored locally in your browser and never saved in plaintext on central servers.
            </p>

            {keyMessage && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: keyMessage.type === 'success' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: keyMessage.type === 'success' ? '#22c55e' : '#ef4444',
                  border: `1px solid ${keyMessage.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                }}
              >
                {keyMessage.text}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <input
                id="custom-key-input"
                type="password"
                value={customKey}
                onChange={(e) => setCustomKey(e.target.value)}
                placeholder="AIzaSy... (Google Gemini API Key)"
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid var(--card-border)',
                  borderRadius: '8px',
                  fontSize: '0.9rem',
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-primary)',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                }}
              />
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="submit"
                  disabled={!customKey.trim()}
                  className="btn btn-primary btn-sm"
                >
                  Save Personal Key
                </button>
                <button
                  type="button"
                  onClick={handleTestKey}
                  disabled={keyTesting || !customKey.trim()}
                  className="btn btn-secondary btn-sm"
                >
                  {keyTesting ? 'Testing Key...' : '⚡ Test Key'}
                </button>
                {isKeySaved && (
                  <button
                    type="button"
                    onClick={handleRemoveKey}
                    className="btn btn-outline btn-sm"
                    style={{ color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.4)' }}
                  >
                    Clear & Use Default
                  </button>
                )}
              </div>
            </div>
          </form>
        </div>

        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid var(--card-border)',
            backgroundColor: 'var(--bg-tertiary)',
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};