import React, { useEffect, useLayoutEffect, useState } from 'react';
import type { UserProfile } from '../types/library';

interface GuidedTourModalProps {
  currentUser: UserProfile;
  isOpen: boolean;
  onClose: () => void;
  onNavigateTab?: (tab: string) => void;
}

interface TourStep {
  title: string;
  badge: string;
  content: string;
  targetSelector?: string;
  tabKey?: string;
  tip?: string;
}

export const GuidedTourModal: React.FC<GuidedTourModalProps> = ({
  currentUser,
  isOpen,
  onClose,
  onNavigateTab,
}) => {
  const isStudent = currentUser.role === 'student';

  const studentSteps: TourStep[] = [
    {
      title: 'Welcome to the AI Library',
      badge: 'System Overview',
      content:
        'This application pairs verified physical catalogue holdings with neural vector search. ' +
        'Follow this quick tour to learn how to find books, inspect availability, and track your loans.',
      tabKey: 'catalogue',
    },
    {
      title: 'Holdings Catalogue',
      badge: 'Navigation Tab',
      targetSelector: '[data-tour="nav-catalogue"]',
      content:
        'Browse all catalogued titles, view active availability counts, and inspect shelf locations. ' +
        'Every record reflects real-time physical inventory.',
      tabKey: 'catalogue',
    },
    {
      title: 'Live Search & Filters',
      badge: 'Keyword Search',
      targetSelector: '[data-tour="catalogue-search-bar"]',
      content:
        'Filter the collection by title, author, or ISBN-13. ' +
        'You can also filter by subject category to explore specific academic disciplines.',
      tabKey: 'catalogue',
      tip: 'Click "View Details & Copies" on any card to see barcode shelf locations.',
    },
    {
      title: 'AI Semantic Search',
      badge: 'Dense Vectors',
      targetSelector: '[data-tour="nav-semantic"]',
      content:
        'Powered by 384-dimensional dense vectors (sentence-transformers/all-MiniLM-L6-v2), ' +
        'this search matches conceptual themes (e.g. "fault-tolerant streaming meshes") directly against book descriptions.',
      tabKey: 'semantic',
      tip: 'Results display cosine similarity percentage badges.',
    },
    {
      title: 'My Borrowed Loans',
      badge: 'Circulation',
      targetSelector: '[data-tour="nav-loans"]',
      content:
        'Review your active borrowings and due dates. Circulation policies:\n' +
        '• Standard loan duration is 14 calendar days.\n' +
        '• Maximum 3 physical books borrowed concurrently.\n' +
        '• Overdue items block further checkouts until returned.',
      tabKey: 'loans',
    },
    {
      title: 'Grounded AI Copilot',
      badge: 'Conversational Assistant',
      targetSelector: '[data-tour="copilot-launcher"]',
      content:
        'Query the assistant anytime about your personal due dates, catalogue availability, or library rules. ' +
        'Responses are strictly grounded in our live database and never hallucinate loan facts.',
      tip: 'Click the Copilot button at the bottom-right corner whenever you need assistance.',
    },
  ];

  const librarianSteps: TourStep[] = [
    {
      title: 'Staff Librarian Portal',
      badge: 'Administration',
      content:
        'Welcome to the staff portal. As a librarian, you manage monograph metadata, oversee physical circulation, ' +
        'and monitor the SentenceTransformer vector embedding pipeline.',
      tabKey: 'catalogue',
    },
    {
      title: 'Catalogue Management',
      badge: 'Bibliographic Records',
      targetSelector: '[data-tour="nav-manage-catalogue"]',
      content:
        'Manage catalogued monographs, update descriptions, register barcode copies, and soft-archive retired titles.',
      tabKey: 'manage_catalogue',
    },
    {
      title: 'Create Monographs & Copies',
      badge: 'Inventory Control',
      targetSelector: '[data-tour="librarian-add-book"]',
      content:
        'Register new books with Modulo-10 ISBN-13 checksum validation. ' +
        'Once created, register physical copy barcodes (e.g., CS-DIST-001) with available or maintenance statuses.',
      tabKey: 'manage_catalogue',
      tip: 'Physical copies track operational statuses: available, maintenance, lost, or retired.',
    },
    {
      title: 'Circulation Desk',
      badge: 'Lending Operations',
      targetSelector: '[data-tour="nav-circulation"]',
      content:
        'Issue copies to active students and process returns. ' +
        'Enforces a 14-day due date, 3-loan limit, and overdue blocks with atomic SQLite transaction locks to prevent TOCTOU race conditions.',
      tabKey: 'circulation',
    },
    {
      title: 'Quick Loan Issuance',
      badge: 'Circulation Desk',
      targetSelector: '[data-tour="circulation-issue-panel"]',
      content:
        'Assign an available physical copy barcode to an active student account in one step. ' +
        'Overdue loans and loan limits are validated immediately.',
      tabKey: 'circulation',
    },
    {
      title: 'AI Vector Embeddings',
      badge: 'Vector Pipeline',
      targetSelector: '[data-tour="nav-embeddings"]',
      content:
        'Inspect model runtime availability, verify 384-dimensional vector coverage, and trigger batch embedding regeneration as monograph metadata changes.',
      tabKey: 'embeddings',
    },
    {
      title: 'AI Library Copilot for Staff',
      badge: 'Staff Assistant',
      targetSelector: '[data-tour="copilot-launcher"]',
      content:
        'Staff can query the Copilot for instant circulation statistics, active loan totals, and system rules directly from the bottom-right launcher.',
    },
  ];

  const steps = isStudent ? studentSteps : librarianSteps;
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  const currentStep = steps[currentStepIndex];

  // Update target rect whenever step changes or window resizes
  useLayoutEffect(() => {
    if (!isOpen) {
      setTargetRect(null);
      return;
    }

    const updateTarget = () => {
      if (currentStep.targetSelector) {
        const el = document.querySelector(currentStep.targetSelector);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const rect = el.getBoundingClientRect();
          setTargetRect(rect);
          return;
        }
      }
      setTargetRect(null);
    };

    updateTarget();
    const timer = setTimeout(updateTarget, 150);
    window.addEventListener('resize', updateTarget);
    window.addEventListener('scroll', updateTarget, true);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateTarget);
      window.removeEventListener('scroll', updateTarget, true);
    };
  }, [isOpen, currentStepIndex, currentStep.targetSelector]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        handleDismiss();
      } else if (e.key === 'ArrowRight') {
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        handlePrev();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentStepIndex]);

  if (!isOpen) return null;

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      const nextIdx = currentStepIndex + 1;
      setCurrentStepIndex(nextIdx);
      if (steps[nextIdx].tabKey && onNavigateTab) {
        onNavigateTab(steps[nextIdx].tabKey!);
      }
    } else {
      handleDismiss();
    }
  };

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      const prevIdx = currentStepIndex - 1;
      setCurrentStepIndex(prevIdx);
      if (steps[prevIdx].tabKey && onNavigateTab) {
        onNavigateTab(steps[prevIdx].tabKey!);
      }
    }
  };

  const handleDismiss = () => {
    try {
      localStorage.setItem('ai_library_tour_completed', 'true');
    } catch {
      // Ignore storage errors
    }
    onClose();
  };

  // Calculate tooltip placement adjacent to target or center on screen
  const getCardStyle = (): React.CSSProperties => {
    if (!targetRect) {
      // Centered fallback modal
      return {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 10002,
      };
    }

    const margin = 16;
    const cardWidth = 440;
    const cardHeight = 320;
    const vWidth = window.innerWidth;
    const vHeight = window.innerHeight;

    let left = targetRect.left + targetRect.width / 2 - cardWidth / 2;
    if (left < margin) left = margin;
    if (left + cardWidth > vWidth - margin) left = vWidth - cardWidth - margin;

    let top = targetRect.bottom + 12;
    // If not enough room below, place above target
    if (top + cardHeight > vHeight - margin && targetRect.top - cardHeight - 12 > margin) {
      top = targetRect.top - cardHeight - 12;
    }

    // Keep within viewport bounds
    if (top < margin) top = margin;
    if (top + cardHeight > vHeight - margin) top = vHeight - cardHeight - margin;

    return {
      position: 'fixed',
      top: `${top}px`,
      left: `${left}px`,
      zIndex: 10002,
    };
  };

  return (
    <div className="tour-overlay-root" role="dialog" aria-modal="true" aria-label="Guided Library Tour">
      {/* Dimmed backdrop */}
      <div className="tour-backdrop" onClick={handleDismiss} />

      {/* Spotlight cutout around the target element */}
      {targetRect && (
        <div
          className="tour-spotlight"
          style={{
            top: `${targetRect.top - 4}px`,
            left: `${targetRect.left - 4}px`,
            width: `${targetRect.width + 8}px`,
            height: `${targetRect.height + 8}px`,
          }}
        />
      )}

      {/* Crisp, high-contrast, fully opaque tooltip card */}
      <div className="tour-tooltip-card" style={getCardStyle()} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="tour-card-header">
          <div className="tour-header-meta">
            <span className="tour-role-badge">{isStudent ? 'STUDENT GUIDE' : 'STAFF GUIDE'}</span>
            <span className="tour-badge-pill">{currentStep.badge}</span>
          </div>
          <button
            type="button"
            className="tour-close-btn"
            onClick={handleDismiss}
            aria-label="Close tour"
            title="Close tour (Esc)"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="tour-card-body">
          <h3 className="tour-card-title">{currentStep.title}</h3>
          <p className="tour-card-text" style={{ whiteSpace: 'pre-line' }}>
            {currentStep.content}
          </p>

          {currentStep.tip && (
            <div className="tour-card-tip">
              <strong>Tip:</strong> {currentStep.tip}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="tour-card-footer">
          <div className="tour-footer-progress">
            <span className="tour-step-indicator">
              {currentStepIndex + 1} of {steps.length}
            </span>
            <div className="tour-mini-dots">
              {steps.map((_, idx) => (
                <div
                  key={idx}
                  className={`tour-mini-dot ${idx === currentStepIndex ? 'dot-active' : ''}`}
                />
              ))}
            </div>
          </div>

          <div className="tour-footer-buttons">
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleDismiss}>
              Skip
            </button>
            {currentStepIndex > 0 && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={handlePrev}>
                Back
              </button>
            )}
            <button type="button" className="btn btn-primary btn-sm" onClick={handleNext}>
              {currentStepIndex === steps.length - 1 ? 'Finish Tour' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
