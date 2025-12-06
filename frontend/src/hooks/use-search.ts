/**
 * Search hook for conversation history.
 *
 * Features:
 * - Full-text search with debouncing
 * - Filter by date, message type, content type
 * - Recent searches stored in localStorage
 * - Keyboard shortcut support (Cmd/Ctrl+K)
 */

import { useCallback, useEffect, useRef } from 'react';
import { useSearchStore, SearchFilters, SearchMatch, SearchResult, SearchPagination } from '@/stores/search-store';

// Re-export types for backwards compatibility
export type { SearchMatch, SearchResult, SearchPagination, SearchFilters };

export function useSearch() {
  const store = useSearchStore();
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Keyboard shortcut: Cmd/Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        // Access store state directly to avoid stale closure
        const { isOpen, open, close } = useSearchStore.getState();
        if (isOpen) {
          close();
        } else {
          open();
        }
      }
      if (e.key === 'Escape') {
        const { isOpen, close } = useSearchStore.getState();
        if (isOpen) {
          close();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const search = useCallback(
    (newFilters: Partial<SearchFilters>) => {
      const updatedFilters = { ...store.filters, ...newFilters };
      store.setFilters(newFilters);

      // Debounce search
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      debounceRef.current = setTimeout(() => {
        store.performSearch(updatedFilters, 1);
      }, 300);
    },
    [store]
  );

  const searchImmediate = useCallback(
    (query: string) => {
      const updatedFilters = { ...store.filters, query };
      store.setFilters({ query });
      store.performSearch(updatedFilters, 1);
    },
    [store]
  );

  const nextPage = useCallback(() => {
    if (store.results && store.currentPage < store.results.pagination.total_pages) {
      store.performSearch(store.filters, store.currentPage + 1);
    }
  }, [store]);

  const prevPage = useCallback(() => {
    if (store.currentPage > 1) {
      store.performSearch(store.filters, store.currentPage - 1);
    }
  }, [store]);

  return {
    isOpen: store.isOpen,
    open: store.open,
    close: store.close,
    filters: store.filters,
    setFilters: search,
    searchImmediate,
    results: store.results,
    isSearching: store.isSearching,
    error: store.error,
    recentSearches: store.recentSearches,
    clearRecentSearches: store.clearRecentSearches,
    currentPage: store.currentPage,
    nextPage,
    prevPage,
    resetFilters: store.resetFilters,
  };
}
