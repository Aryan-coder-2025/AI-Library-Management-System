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
            width: '400px',
            maxWidth: '92vw',
            backgroundColor: 'var(--bg-surface-elevated, #171D35)',
            borderRadius: '10px',
            boxShadow: '0 12px 32px rgba(0,0,0,0.35), 0 2px 8px rgba(0,0,0,0.15)',
            border: '1px solid var(--border-medium, #29334F)',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '0.75rem 1rem',
              borderBottom: '1px solid var(--border-subtle, #1E293B)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--bg-subtle, #1D2742)',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary, #F5F6FF)' }}>
              Notifications {unreadCount > 0 && <span style={{ color: '#FB7185' }}>({unreadCount} unread)</span>}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  style={{
                    border: 'none',
                    background: 'none',
                    color: 'var(--color-secondary-violet, #38BDF8)',
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
                    color: 'var(--color-accent, #22D3EE)',
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
                backgroundColor: 'rgba(34, 211, 238, 0.12)',
                color: 'var(--color-accent, #22D3EE)',
                fontSize: '0.8rem',
                borderBottom: '1px solid var(--border-subtle, #1E293B)',
              }}
            >
              {actionMessage}
            </div>
          )}

          <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
            {loading ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted, #77829E)', fontSize: '0.85rem' }}>
                Loading alerts...
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--text-muted, #77829E)' }}>
                <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>🔔</div>
                <div style={{ fontWeight: 500, fontSize: '0.9rem', color: 'var(--text-primary, #F5F6FF)' }}>All caught up!</div>
                <div style={{ fontSize: '0.8rem' }}>You have no pending library alerts.</div>
              </div>
            ) : (
              notifications.map((n) => {
                const isOverdue = n.notification_type === 'overdue' || n.notification_type === 'overdue_alert';
                const isCourseReading = n.notification_type === 'course_reading_list';
                const isDueSoon = n.notification_type === 'due_soon_reminder';

                let badgeLabel = 'Notice';
                let badgeBg = 'rgba(34, 211, 238, 0.15)';
                let badgeColor = '#22D3EE';
                let badgeBorder = '1px solid rgba(34, 211, 238, 0.3)';

                if (isOverdue) {
                  badgeLabel = '⚠️ Overdue';
                  badgeBg = 'rgba(251, 113, 133, 0.18)';
                  badgeColor = '#FB7185';
                  badgeBorder = '1px solid rgba(251, 113, 133, 0.35)';
                } else if (isCourseReading) {
                  badgeLabel = '📚 Required Reading';
                  badgeBg = 'rgba(37, 99, 235, 0.16)';
                  badgeColor = '#93C5FD';
                  badgeBorder = '1px solid rgba(59, 130, 246, 0.35)';
                } else if (isDueSoon) {
                  badgeLabel = '⏰ Due Soon';
                  badgeBg = 'rgba(251, 191, 36, 0.18)';
                  badgeColor = '#FBBF24';
                  badgeBorder = '1px solid rgba(251, 191, 36, 0.35)';
                }

                return (
                  <div
                    key={n.id}
                    style={{
                      padding: '0.75rem 1rem',
                      borderBottom: '1px solid var(--border-subtle, #1E293B)',
                      backgroundColor: n.is_read
                        ? 'transparent'
                        : 'var(--bg-subtle, rgba(29, 39, 66, 0.6))',
                      borderLeft: n.is_read ? '3px solid transparent' : '3px solid var(--color-primary, #2563EB)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.35rem',
                      transition: 'background-color 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '1px 7px',
                            borderRadius: '4px',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            backgroundColor: badgeBg,
                            color: badgeColor,
                            border: badgeBorder,
                            lineHeight: 1.4,
                          }}
                        >
                          {badgeLabel}
                        </span>
                        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary, #F5F6FF)' }}>
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
                            color: 'var(--color-secondary-violet, #38BDF8)',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                            padding: '0 2px',
                            whiteSpace: 'nowrap',
                            fontWeight: 500,
                          }}
                        >
                          Mark read
                        </button>
                      )}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #A9B2CC)', lineHeight: 1.45 }}>
                      {n.message}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #77829E)' }}>
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

