import React, { useEffect, useState, useRef, useCallback } from 'react';

interface InactivityMonitorProps {
  isActive: boolean;
  onLogout: () => void;
  timeoutMinutes?: number;
  warningMinutes?: number;
}

export const InactivityMonitor: React.FC<InactivityMonitorProps> = ({
  isActive,
  onLogout,
  timeoutMinutes = 30,
  warningMinutes = 25,
}) => {
  const [showWarning, setShowWarning] = useState<boolean>(false);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(
    Math.max(10, (timeoutMinutes - warningMinutes) * 60)
  );

  const lastActiveRef = useRef<number>(Date.now());
  const logoutFiredRef = useRef<boolean>(false);

  // Throttled activity updater
  const handleUserActivity = useCallback(() => {
    // If the warning modal is already shown, do NOT auto-dismiss via subtle mouse movement
    // The user should explicitly click "Stay Logged In" to acknowledge.
    if (!showWarning) {
      const now = Date.now();
      if (now - lastActiveRef.current > 5000) {
        lastActiveRef.current = now;
      }
    }
  }, [showWarning]);

  // Attach window event listeners
  useEffect(() => {
    if (!isActive) return;

    const events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach((ev) => window.addEventListener(ev, handleUserActivity, { passive: true }));

    return () => {
      events.forEach((ev) => window.removeEventListener(ev, handleUserActivity));
    };
  }, [isActive, handleUserActivity]);

  // Periodic idle check
  useEffect(() => {
    if (!isActive) {
      setShowWarning(false);
      logoutFiredRef.current = false;
      return;
    }

    const interval = setInterval(() => {
      const now = Date.now();
      const idleMs = now - lastActiveRef.current;
      const warnThresholdMs = warningMinutes * 60 * 1000;
      const logoutThresholdMs = timeoutMinutes * 60 * 1000;

      if (idleMs >= logoutThresholdMs) {
        if (!logoutFiredRef.current) {
          logoutFiredRef.current = true;
          setShowWarning(false);
          onLogout();
        }
      } else if (idleMs >= warnThresholdMs) {
        const remainingSec = Math.max(0, Math.round((logoutThresholdMs - idleMs) / 1000));
        setSecondsRemaining(remainingSec);
        setShowWarning(true);
      } else {
        setShowWarning(false);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive, onLogout, timeoutMinutes, warningMinutes]);

  const handleStayLoggedIn = () => {
    lastActiveRef.current = Date.now();
    setShowWarning(false);
    logoutFiredRef.current = false;
  };

  if (!isActive || !showWarning) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(8, 13, 26, 0.75)',
        backdropFilter: 'blur(4px)',
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
    >
      <div
        style={{
          background: 'var(--bg-surface, #0E1626)',
          border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
          borderRadius: '14px',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(245, 158, 11, 0.2)',
          maxWidth: '440px',
          width: '100%',
          padding: '1.75rem',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⏱️</div>
        <h3 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-primary, #F8FAFC)', fontSize: '1.25rem' }}>
          Session Inactivity Warning
        </h3>
        <p style={{ margin: '0 0 1.25rem 0', color: 'var(--text-secondary, #94A3B8)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          You have been idle for {warningMinutes} minutes. For patron security on shared campus workstations, your session will automatically close in:
        </p>

        <div
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            color: '#FBBF24',
            fontFamily: 'monospace',
            marginBottom: '1.5rem',
            padding: '0.5rem',
            background: 'rgba(245, 158, 11, 0.1)',
            borderRadius: '8px',
            border: '1px solid rgba(245, 158, 11, 0.25)',
          }}
        >
          {Math.floor(secondsRemaining / 60)}:
          {(secondsRemaining % 60).toString().padStart(2, '0')}
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleStayLoggedIn}
            style={{ flex: 1, padding: '0.75rem' }}
          >
            Stay Logged In
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onLogout}
            style={{ flex: 1, padding: '0.75rem' }}
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
};
