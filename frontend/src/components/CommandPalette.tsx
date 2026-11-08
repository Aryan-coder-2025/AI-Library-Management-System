import React, { useEffect, useState, useRef } from 'react';
import type { UserProfile } from '../types/library';

interface CommandItem {
  id: string;
  category: 'Workspace' | 'Discover' | 'My Library' | 'Management' | 'Preferences' | 'Academic Tools';
  title: string;
  subtitle?: string;
  icon: string;
  shortcut?: string;
  action: () => void;
  keywords?: string[];
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: string) => void;
  onOpenCopilot: () => void;
  onOpenProfile: () => void;
  onOpenTour: () => void;
  onToggleTheme: () => void;
  currentTheme: 'dark' | 'light';
  currentUser: UserProfile | null;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectTab,
  onOpenCopilot,
  onOpenProfile,
  onOpenTour,
  onToggleTheme,
  currentTheme,
  currentUser,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const isPatron = currentUser?.role === 'student' || currentUser?.role === 'teacher';
  const isLibrarian = currentUser?.role === 'librarian';

  const allItems: CommandItem[] = [
    // Workspace
    {
      id: 'nav-dashboard',
      category: 'Workspace',
      title: 'Academic Workspace Dashboard',
      subtitle: 'Personalized overview, active loans, and quick telemetry',
      icon: '📊',
      action: () => {
        onSelectTab('dashboard');
        onClose();
      },
      keywords: ['dashboard', 'home', 'overview', 'main', 'kpi'],
    },
    {
      id: 'action-copilot',
      category: 'Workspace',
      title: 'Open AI Copilot',
      subtitle: 'Ask questions, lookup policies, find books and spaces',
      icon: '✨',
      shortcut: 'Ctrl+J',
      action: () => {
        onOpenCopilot();
        onClose();
      },
      keywords: ['ai', 'copilot', 'assistant', 'chat', 'ask', 'agent', 'librarian'],
    },
    {
      id: 'nav-semantic',
      category: 'Workspace',
      title: 'Semantic Vector Search',
      subtitle: 'Search library collection by conceptual meaning & themes',
      icon: '🧠',
      action: () => {
        onSelectTab('semantic');
        onClose();
      },
      keywords: ['semantic', 'vector', 'ai', 'conceptual', 'embeddings', 'similarity'],
    },

    // Discover
    {
      id: 'nav-catalogue',
      category: 'Discover',
      title: 'Library Catalogue & Monographs',
      subtitle: 'Browse all textbooks, monographs, and research volumes',
      icon: '📚',
      action: () => {
        onSelectTab('catalogue');
        onClose();
      },
      keywords: ['catalogue', 'books', 'search', 'monographs', 'library', 'opac'],
    },
    {
      id: 'nav-knowledge',
      category: 'Discover',
      title: 'Academic Knowledge Explorer',
      subtitle: 'Disciplines, topics, concepts, and collection links',
      icon: '🔬',
      action: () => {
        onSelectTab('knowledge');
        onClose();
      },
      keywords: ['knowledge', 'taxonomy', 'disciplines', 'concepts', 'topics', 'tree'],
    },

    // My Library (Patrons)
    ...(isPatron
      ? [
          {
            id: 'nav-loans',
            category: 'My Library' as const,
            title: 'My Active Loans & Circulation',
            subtitle: 'View due dates, return statuses, and renew borrowed books',
            icon: '📖',
            action: () => {
              onSelectTab('loans');
              onClose();
            },
            keywords: ['loans', 'borrowed', 'due', 'renew', 'books', 'history'],
          },
          {
            id: 'nav-spaces',
            category: 'My Library' as const,
            title: 'Study Spaces & Floor Wayfinding',
            subtitle: 'Interactive architectural floor plans and seat reservations',
            icon: '🏛️',
            action: () => {
              onSelectTab('spaces');
              onClose();
            },
            keywords: ['spaces', 'study', 'seats', 'rooms', 'floor', 'plan', 'reserve', 'qr'],
          },
        ]
      : []),

    // Librarian Subsystems
    ...(isLibrarian
      ? [
          {
            id: 'nav-circulation-desk',
            category: 'Management' as const,
            title: 'Circulation Desk Operations',
            subtitle: 'Issue, return, and scan physical monograph copies',
            icon: '🔄',
            action: () => {
              onSelectTab('circulation');
              onClose();
            },
            keywords: ['circulation', 'issue', 'return', 'barcode', 'desk', 'patron'],
          },
          {
            id: 'nav-manage-catalogue',
            category: 'Management' as const,
            title: 'Catalogue Inventory Management',
            subtitle: 'Create monographs, manage barcodes, and edit metadata',
            icon: '📦',
            action: () => {
              onSelectTab('manage_catalogue');
              onClose();
            },
            keywords: ['manage', 'inventory', 'isbn', 'add', 'edit', 'copies'],
          },
          {
            id: 'nav-spaces-desk',
            category: 'Management' as const,
            title: 'Study Spaces Management',
            subtitle: 'Floor plans, seat layouts, and live occupancy telemetry',
            icon: '🗺️',
            action: () => {
              onSelectTab('space_management');
              onClose();
            },
            keywords: ['spaces', 'zones', 'seats', 'rooms', 'analytics', 'telemetry'],
          },
          {
            id: 'nav-embeddings',
            category: 'Management' as const,
            title: 'AI Vector Embeddings Engine',
            subtitle: 'Monitor sentence-transformer indexing and coverage',
            icon: '⚡',
            action: () => {
              onSelectTab('embeddings');
              onClose();
            },
            keywords: ['embeddings', 'vector', 'engine', 'indexing', 'transformer'],
          },
          {
            id: 'nav-ai-studio',
            category: 'Management' as const,
            title: 'AI Model Comparison Studio',
            subtitle: 'Side-by-side prompt execution across Gemini & Local models',
            icon: '⚖️',
            action: () => {
              onSelectTab('ai_studio');
              onClose();
            },
            keywords: ['comparison', 'studio', 'models', 'gemini', 'ollama', 'grounding'],
          },
          {
            id: 'nav-intelligence',
            category: 'Management' as const,
            title: 'Librarian Intelligence Centre',
            subtitle: 'Executive KPIs, 14-day demand forecast, turnover & zero-result acquisitions',
            icon: '📈',
            action: () => {
              onSelectTab('intelligence');
              onClose();
            },
            keywords: ['intelligence', 'forecast', 'analytics', 'turnover', 'acquisitions', 'demand', 'snapshot', 'kpi'],
          },
        ]
      : []),

    // Teacher & Faculty Academic Planner
    ...(currentUser && (currentUser.role === 'teacher' || currentUser.role === 'librarian')
      ? [
          {
            id: 'nav-teacher-portal',
            category: 'Academic Tools' as const,
            title: 'Teacher Portal & Syllabus Planner',
            subtitle: 'Create courses, curate syllabus reading lists with live shelf availability, and place course reserves',
            icon: '🎓',
            action: () => {
              onSelectTab('teacher_portal');
              onClose();
            },
            keywords: ['teacher', 'faculty', 'syllabus', 'course', 'reserves', 'reading', 'list', 'curriculum'],
          },
        ]
      : []),

    // Preferences & Help
    {
      id: 'pref-theme',
      category: 'Preferences',
      title: `Switch Theme to ${currentTheme === 'dark' ? 'Academic Aurora (Light)' : 'Midnight Intelligence (Dark)'}`,
      subtitle: `Current active palette: ${currentTheme === 'dark' ? 'Midnight Intelligence' : 'Academic Aurora'}`,
      icon: currentTheme === 'dark' ? '☀️' : '🌙',
      action: () => {
        onToggleTheme();
        onClose();
      },
      keywords: ['theme', 'dark', 'light', 'mode', 'color', 'palette', 'aurora', 'midnight'],
    },
    ...(currentUser
      ? [
          {
            id: 'pref-profile',
            category: 'Preferences' as const,
            title: 'Account Profile & Security',
            subtitle: `Signed in as ${currentUser.full_name} (${currentUser.role})`,
            icon: '👤',
            action: () => {
              onOpenProfile();
              onClose();
            },
            keywords: ['profile', 'account', 'password', 'security', 'email', 'settings'],
          },
          {
            id: 'pref-tour',
            category: 'Preferences' as const,
            title: 'Guided Onboarding Tour & Platform Help',
            subtitle: 'Step-by-step interactive walkthrough of all features',
            icon: '🧭',
            action: () => {
              onOpenTour();
              onClose();
            },
            keywords: ['tour', 'help', 'guide', 'tutorial', 'walkthrough'],
          },
        ]
      : []),
  ];

  const filteredItems = allItems.filter((item) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    if (item.title.toLowerCase().includes(q)) return true;
    if (item.subtitle && item.subtitle.toLowerCase().includes(q)) return true;
    if (item.keywords && item.keywords.some((k) => k.includes(q))) return true;
    return false;
  });

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        filteredItems[selectedIndex].action();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="command-palette-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="command-palette-modal"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="command-palette-input-wrap">
          <span className="command-palette-search-icon">🔍</span>
          <input
            ref={inputRef}
            type="text"
            className="command-palette-input"
            placeholder="Type a command, destination, or jump to view (e.g. 'catalogue', 'copilot', 'theme')..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
          />
          <span className="command-palette-esc-badge" onClick={onClose}>ESC</span>
        </div>

        <div className="command-palette-list">
          {filteredItems.length === 0 ? (
            <div className="command-palette-empty">
              No matching commands or navigation destinations for "{query}".
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  className={`command-palette-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => item.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <span className="command-item-icon">{item.icon}</span>
                  <div className="command-item-content">
                    <div className="command-item-title-row">
                      <span className="command-item-title">{item.title}</span>
                      <span className="command-item-category-tag">{item.category}</span>
                    </div>
                    {item.subtitle && (
                      <span className="command-item-subtitle">{item.subtitle}</span>
                    )}
                  </div>
                  {item.shortcut && (
                    <span className="command-item-shortcut">{item.shortcut}</span>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="command-palette-footer">
          <div className="command-footer-hints">
            <span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span>
            <span><kbd>↵</kbd> Select</span>
            <span><kbd>ESC</kbd> Close</span>
          </div>
          <span className="command-footer-brand">Athenaeum Command Intelligence</span>
        </div>
      </div>
    </div>
  );
};

