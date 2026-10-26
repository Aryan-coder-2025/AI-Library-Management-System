import { useEffect, useState } from 'react';
import { apiFetch } from './services/apiClient';

interface HealthData {
  status: string;
  project_name: string;
  environment: string;
  database: string;
}

export function App() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    apiFetch<HealthData>('/api/health')
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to connect to backend service');
        setLoading(false);
      });
  }, []);

  return (
    <div className="app-container">
      <header className="header-banner">
        <h1>AI Library Management System</h1>
        <p>Stage 1 Foundation & System Readiness</p>
      </header>

      <div className="card-grid">
        <div className="status-card">
          <h3>Backend & Database Health</h3>
          {loading && <span className="status-badge loading">Connecting...</span>}
          {error && <span className="status-badge loading" style={{ color: '#ef4444' }}>Offline ({error})</span>}
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

        <div className="status-card">
          <h3>Architectural Guards Active</h3>
          <table className="meta-table">
            <tbody>
              <tr>
                <td>SQLite WAL Mode:</td>
                <td>Verified outside transactions</td>
              </tr>
              <tr>
                <td>Write Lock Strategy:</td>
                <td>BEGIN IMMEDIATE on writes</td>
              </tr>
              <tr>
                <td>Referential Integrity:</td>
                <td>PRAGMA foreign_keys = ON</td>
              </tr>
              <tr>
                <td>CSRF Protection:</td>
                <td>Double Submit Cookie active</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default App;
