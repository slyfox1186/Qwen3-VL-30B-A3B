import { create } from 'zustand';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';
const RECENT_SEARCHES_KEY = 'qwen-chat-recent-searches';
const MAX_RECENT_SEARCHES = 10;

export interface SearchMatch {
  message_id: string;
  session_id: string;
  role: string;
  content: string;
  thought: string | null;
  created_at: string;
  highlights: string[];
  relevance: number;
  has_images: boolean;
  has_code: boolean;
}

export interface SearchPagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SearchResult {
  matches: SearchMatch[];
  pagination: SearchPagination;
  query: string | null;
}

export interface SearchFilters {
  query: string;
  messageType: 'all' | 'user' | 'assistant';
  dateFrom: string | null;
  dateTo: string | null;
  hasImages: boolean | null;
  hasCode: boolean | null;
  sessionId: string | null;
}

const defaultFilters: SearchFilters = {
  query: '',
  messageType: 'all',
  dateFrom: null,
  dateTo: null,
  hasImages: null,
  hasCode: null,
  sessionId: null,
};

interface SearchState {
  isOpen: boolean;
  filters: SearchFilters;
  results: SearchResult | null;
  isSearching: boolean;
  error: string | null;
  recentSearches: string[];
  currentPage: number;

  // Actions
  open: () => void;
  close: () => void;
  setFilters: (filters: Partial<SearchFilters>) => void;
  setResults: (results: SearchResult | null) => void;
  setIsSearching: (searching: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentPage: (page: number) => void;
  setRecentSearches: (searches: string[]) => void;
  saveRecentSearch: (query: string) => void;
  clearRecentSearches: () => void;
  resetFilters: () => void;
  performSearch: (searchFilters: SearchFilters, page?: number) => Promise<void>;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  isOpen: false,
  filters: defaultFilters,
  results: null,
  isSearching: false,
  error: null,
  recentSearches: [],
  currentPage: 1,

  open: () => set({ isOpen: true }),

  close: () => {
    set({
      isOpen: false,
      filters: defaultFilters,
      results: null,
      currentPage: 1,
    });
  },

  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
    })),

  setResults: (results) => set({ results }),
  setIsSearching: (isSearching) => set({ isSearching }),
  setError: (error) => set({ error }),
  setCurrentPage: (currentPage) => set({ currentPage }),
  setRecentSearches: (recentSearches) => set({ recentSearches }),

  saveRecentSearch: (query) => {
    if (!query.trim()) return;

    const { recentSearches } = get();
    const updated = [query, ...recentSearches.filter((s) => s !== query)].slice(
      0,
      MAX_RECENT_SEARCHES
    );

    set({ recentSearches: updated });

    try {
      localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
    } catch {
      // Ignore localStorage errors
    }
  },

  clearRecentSearches: () => {
    set({ recentSearches: [] });
    try {
      localStorage.removeItem(RECENT_SEARCHES_KEY);
    } catch {
      // Ignore localStorage errors
    }
  },

  resetFilters: () => {
    set({
      filters: defaultFilters,
      results: null,
      currentPage: 1,
    });
  },

  performSearch: async (searchFilters, page = 1) => {
    if (!searchFilters.query.trim() && !searchFilters.hasImages && !searchFilters.hasCode) {
      set({ results: null });
      return;
    }

    set({ isSearching: true, error: null });

    try {
      const response = await fetch(`${API_BASE_URL}/sessions/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchFilters.query || null,
          message_type: searchFilters.messageType === 'all' ? null : searchFilters.messageType,
          date_from: searchFilters.dateFrom || null,
          date_to: searchFilters.dateTo || null,
          has_images: searchFilters.hasImages,
          has_code: searchFilters.hasCode,
          session_id: searchFilters.sessionId,
          page,
          page_size: 20,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.error?.message || `Search failed: ${response.status}`);
      }

      const data: SearchResult = await response.json();
      set({ results: data, currentPage: page });

      if (searchFilters.query.trim()) {
        get().saveRecentSearch(searchFilters.query.trim());
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Search failed',
        results: null,
      });
    } finally {
      set({ isSearching: false });
    }
  },
}));

// Initialize recent searches from localStorage (client-side only)
if (typeof window !== 'undefined') {
  try {
    const stored = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (stored) {
      useSearchStore.setState({ recentSearches: JSON.parse(stored) });
    }
  } catch {
    // Ignore localStorage errors
  }
}
