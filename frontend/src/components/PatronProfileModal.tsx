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

  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [pwdLoading, setPwdLoading] = useState<boolean>(false);
  const [pwdMessage, setPwdMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdMessage(null);

    if (!currentPassword) {
      setPwdMessage({ type: 'error', text: 'Please enter your current password.' });
      return;
    }
    if (newPassword.length < 8) {
      setPwdMessage({ type: 'error', text: 'New password must be at least 8 characters long.' });
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
          backgroundColor: '#ffffff',
          borderRadius: '12px',
          maxWidth: '560px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#1e293b', margin: 0 }}>
              Account & Profile Settings
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0.25rem 0 0' }}>
              Manage patron identity details, borrowing credentials, and password security
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              color: '#94a3b8',
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
              backgroundColor: '#f8fafc',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Email Address
                </span>
                <div style={{ fontWeight: 600, color: '#1e293b', fontSize: '0.9rem' }}>
                  {currentUser.email}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
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
                          ? '#fef3c7'
                          : currentUser.role === 'librarian'
                          ? '#e0e7ff'
                          : '#e0f2fe',
                      color:
                        currentUser.role === 'teacher'
                          ? '#92400e'
                          : currentUser.role === 'librarian'
                          ? '#3730a3'
                          : '#0369a1',
                      textTransform: 'capitalize',
                    }}
                  >
                    {currentUser.role}
                  </span>
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Account Status
                </span>
                <div style={{ color: currentUser.is_active ? '#16a34a' : '#dc2626', fontWeight: 600, fontSize: '0.85rem' }}>
                  {currentUser.is_active ? '● Active' : '● Inactive'}
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Member Since
                </span>
                <div style={{ color: '#475569', fontSize: '0.85rem' }}>
                  {new Date(currentUser.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: '0.75rem',
                paddingTop: '0.75rem',
                borderTop: '1px solid #e2e8f0',
                fontSize: '0.8rem',
                color: '#475569',
              }}
            >
              <strong>Policy: </strong>
              {getPolicyBadge()}
            </div>
          </div>

          {/* Section 1: Update Full Name */}
          <form onSubmit={handleUpdateName}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#1e293b', marginBottom: '0.5rem' }}>
              Personal Information
            </h3>

            {nameMessage && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: nameMessage.type === 'success' ? '#f0fdf4' : '#fef2f2',
                  color: nameMessage.type === 'success' ? '#166534' : '#991b1b',
                  border: `1px solid ${nameMessage.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
                }}
              >
                {nameMessage.text}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label htmlFor="full-name-input" style={{ fontSize: '0.85rem', fontWeight: 500, color: '#334155' }}>
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
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
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

          {/* Section 2: Change Password */}
          <form onSubmit={handleChangePassword}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#1e293b', marginBottom: '0.5rem' }}>
              Change Password
            </h3>

            {pwdMessage && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: pwdMessage.type === 'success' ? '#f0fdf4' : '#fef2f2',
                  color: pwdMessage.type === 'success' ? '#166534' : '#991b1b',
                  border: `1px solid ${pwdMessage.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
                }}
              >
                {pwdMessage.text}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label
                  htmlFor="current-pwd-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: '#334155', marginBottom: '0.25rem' }}
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
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label
                  htmlFor="new-pwd-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: '#334155', marginBottom: '0.25rem' }}
                >
                  New Password
                </label>
                <input
                  id="new-pwd-input"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Min 8 chars (uppercase, lowercase, number, symbol)"
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label
                  htmlFor="confirm-pwd-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: '#334155', marginBottom: '0.25rem' }}
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
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div style={{ marginTop: '0.5rem' }}>
                <button
                  type="submit"
                  disabled={pwdLoading}
                  className="btn btn-secondary btn-sm"
                  style={{ width: '100%' }}
                >
                  {pwdLoading ? 'Updating Password...' : 'Change Password'}
                </button>
              </div>
            </div>
          </form>
        </div>

        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid #e2e8f0',
            backgroundColor: '#f8fafc',
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

