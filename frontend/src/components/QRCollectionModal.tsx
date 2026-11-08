import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import type { BookCollectionPass } from '../types/library';

interface QRCollectionModalProps {
  holdId: number;
  bookTitle: string;
  onClose: () => void;
}

export const QRCollectionModal: React.FC<QRCollectionModalProps> = ({
  holdId,
  bookTitle,
  onClose,
}) => {
  const [pass, setPass] = useState<BookCollectionPass | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPass = async () => {
      try {
        setLoading(true);
        setError(null);
        const csrfToken = document.cookie
          .split('; ')
          .find((row) => row.startsWith('csrf_token='))
          ?.split('=')[1] || '';

        const res = await fetch(`/api/circulation/qr-collection/pass/${holdId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to generate collection pass.');
        }

        const data: BookCollectionPass = await res.json();
        setPass(data);

        // Generate QR image
        const url = await QRCode.toDataURL(data.qr_payload, {
          width: 256,
          margin: 2,
          color: {
            dark: '#0f172a',
            light: '#ffffff',
          },
        });
        setQrDataUrl(url);
      } catch (err: any) {
        setError(err.message || 'Error creating collection QR token.');
      } finally {
        setLoading(false);
      }
    };

    fetchPass();
  }, [holdId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center space-x-2">
            <span className="text-xl">📱</span>
            <h2 className="text-lg font-bold text-slate-100">Book Collection Pass</h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-xl font-bold p-1 rounded-lg hover:bg-slate-800 transition"
          >
            ✕
          </button>
        </div>

        <div className="p-6 text-center">
          {loading && (
            <div className="py-12 flex flex-col items-center justify-center space-y-3">
              <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-sm text-slate-400">Generating secure collection token...</p>
            </div>
          )}

          {error && (
            <div className="py-8 px-4 bg-red-950/40 border border-red-800/60 rounded-xl my-4 text-left">
              <p className="text-sm font-semibold text-red-300">Unable to generate pass:</p>
              <p className="text-xs text-red-400 mt-1">{error}</p>
              <button
                onClick={onClose}
                className="mt-4 w-full py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-lg transition"
              >
                Close
              </button>
            </div>
          )}

          {pass && qrDataUrl && (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">Present at Circulation Desk</p>
                <h3 className="text-base font-bold text-slate-100 mt-1 line-clamp-1">{bookTitle}</h3>
                <p className="text-xs text-slate-400">Copy Code: <span className="font-mono text-cyan-300">{pass.copy_code}</span></p>
              </div>

              <div className="p-4 bg-white rounded-2xl inline-block shadow-lg mx-auto">
                <img src={qrDataUrl} alt="Collection QR Code" className="w-56 h-56 mx-auto" />
              </div>

              <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-left space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Patron:</span>
                  <span className="font-semibold text-slate-200">{pass.patron_name}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Token ID:</span>
                  <span className="font-mono text-xs text-slate-300">{pass.token.slice(0, 16)}...</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Valid Until:</span>
                  <span className="text-emerald-400 font-medium">
                    {new Date(pass.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} (2 hrs)
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-400 text-center leading-relaxed">
                Circulation staff will scan or verify this pass to issue your physical monograph.
              </p>

              <button
                onClick={onClose}
                className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl transition"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
