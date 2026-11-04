import React, { useEffect, useState, useRef, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type {
  Notification,
  NotificationPaginationResponse,
  NotificationUnreadCountResponse,
  UserProfile,
} from '../types/library';

interface NotificationBellProps {
  currentUser: UserProfile;
}

export const NotificationBell: React.FC<NotificationBellProps> = ({ currentUser }) => {
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await apiFetch<NotificationUnreadCountResponse>('/api/notifications/unread-count');
      setUnreadCount(res.unread_count);
    } catch {
      // Ignore network errors on background poll
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setActionMessage(null);
    try {
      const res = await apiFetch<NotificationPaginationResponse>('/api/notifications?page=1&page_size=20');
      setNotifications(res.items);
      setUnreadCount(res.unread_count);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load notifications';
      setActionMessage(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 60000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen, fetchNotifications]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleMarkRead = async (id: number) => {
    try {
      await apiFetch<Notification>(`/api/notifications/${id}/read`, { method: 'PATCH' });
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error updating notification';
      setActionMessage(msg.replace(/^\d+:\s*/, ''));
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await apiFetch('/api/notifications/mark-all-read', { method: 'POST' });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
      setActionMessage('All notifications marked as read.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error';
      setActionMessage(msg.replace(/^\d+:\s*/, ''));
    }
  };

  const handleTriggerSweep = async () => {
    try {
      setLoading(true);
      const res = await apiFetch<{ new_notifications: number }>('/api/notifications/sweep', {
        method: 'POST',
      });
      setActionMessage(`Sweep completed: ${res.new_notifications} new notification(s) generated.`);
      await fetchNotifications();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error running sweep';
      setActionMessage(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="notification-bell-container" ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => setIsOpen(!isOpen)}
        title="View Notifications & Overdue Alerts"
        style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
        aria-label="Notifications"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '-6px',
              right: '-6px',
              backgroundColor: '#dc2626',
              color: '#ffffff',
              fontSize: '0.7rem',
              fontWeight: 700,
              borderRadius: '9999px',
              padding: '1px 6px',
              lineHeight: 1.4,
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className="notification-dropdown"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '380px',
            maxWidth: '90vw',
            backgroundColor: '#ffffff',
            borderRadius: '8px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.15), 0 2px 6px rgba(0,0,0,0.08)',
            border: '1px solid #e2e8f0',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '0.75rem 1rem',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: '#f8fafc',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#1e293b' }}>
              Notifications {unreadCount > 0 && <span style={{ color: '#dc2626' }}>({unreadCount} unread)</span>}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  style={{
                    border: 'none',
                    background: 'none',
                    color: '#2563eb',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  Mark all read
                </button>
              )}
              {currentUser.role === 'librarian' && (
                <button
                  type="button"
                  onClick={handleTriggerSweep}
                  style={{
                    border: 'none',
                    background: 'none',
                    color: '#0d9488',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                  title="Scan catalogue for overdue loans and issue patron notifications"
                >
                  ⚡ Run sweep
                </button>
              )}
            </div>
          </div>

          {actionMessage && (
            <div
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#eff6ff',
                color: '#1e40af',
                fontSize: '0.8rem',
                borderBottom: '1px solid #bfdbfe',
              }}
            >
              {actionMessage}
            </div>
          )}

          <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
            {loading ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                Loading alerts...
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: '#94a3b8' }}>
                <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>🔔</div>
                <div style={{ fontWeight: 500, fontSize: '0.9rem', color: '#475569' }}>All caught up!</div>
                <div style={{ fontSize: '0.8rem' }}>You have no pending library alerts.</div>
              </div>
            ) : (
              notifications.map((n) => {
                const isOverdue = n.notification_type === 'overdue';
                return (
                  <div
                    key={n.id}
                    style={{
                      padding: '0.75rem 1rem',
                      borderBottom: '1px solid #f1f5f9',
                      backgroundColor: n.is_read ? '#ffffff' : '#f0fdf4',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.35rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            backgroundColor: isOverdue ? '#fee2e2' : '#e0f2fe',
                            color: isOverdue ? '#991b1b' : '#0369a1',
                          }}
                        >
                          {isOverdue ? '⚠️ Overdue' : 'Notice'}
                        </span>
                        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1e293b' }}>
                          {n.title}
                        </span>
                      </div>
                      {!n.is_read && (
                        <button
                          type="button"
                          onClick={() => handleMarkRead(n.id)}
                          style={{
                            border: 'none',
                            background: 'none',
                            color: '#2563eb',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                            padding: '0 2px',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          Mark read
                        </button>
                      )}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.4 }}>
                      {n.message}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                      {new Date(n.created_at).toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};

