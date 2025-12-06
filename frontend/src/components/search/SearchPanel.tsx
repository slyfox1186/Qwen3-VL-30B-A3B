'use client';

import React, { useRef, useEffect } from 'react';
import { Search, X, Filter, User, Bot, Image as ImageIcon, Code, Clock, ChevronLeft, ChevronRight } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useSearch, SearchMatch } from '@/hooks/use-search';
import { cn } from '@/lib/utils';
import '@/styles/components/search-panel.css';

interface SearchPanelProps {
  onResultClick?: (match: SearchMatch) => void;
}

export default function SearchPanel({ onResultClick }: SearchPanelProps) {
  const {
    isOpen,
    close,
    filters,
    setFilters,
    searchImmediate,
    results,
    isSearching,
    error,
    recentSearches,
    clearRecentSearches,
    currentPage,
    nextPage,
    prevPage,
    resetFilters,
  } = useSearch();

  const inputRef = useRef<HTMLInputElement>(null);
  const [showFilters, setShowFilters] = React.useState(false);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleResultClick = (match: SearchMatch) => {
    onResultClick?.(match);
    close();
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderHighlights = (highlights: string[]) => {
    if (highlights.length === 0) return null;
    return (
      <div className="search-highlights">
        {highlights.map((h, i) => (
          <span
            key={i}
            className="highlight-snippet"
            dangerouslySetInnerHTML={{
              __html: h.replace(/\*\*(.*?)\*\*/g, '<mark>$1</mark>'),
            }}
          />
        ))}
      </div>
    );
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="search-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={close}
          />
          <motion.div
            className="search-panel"
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Search Input */}
            <div className="search-header">
              <div className="search-input-wrapper">
                <Search className="search-icon" />
                <input
                  ref={inputRef}
                  type="text"
                  value={filters.query}
                  onChange={(e) => setFilters({ query: e.target.value })}
                  placeholder="Search conversations..."
                  className="search-input"
                />
                {filters.query && (
                  <button
                    onClick={() => setFilters({ query: '' })}
                    className="clear-input-btn"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              <div className="search-actions">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={cn('filter-toggle', showFilters && 'active')}
                >
                  <Filter className="w-4 h-4" />
                </button>
                <button onClick={close} className="close-btn">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Filters */}
            <AnimatePresence>
              {showFilters && (
                <motion.div
                  className="search-filters"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                >
                  <div className="filter-row">
                    <label className="filter-label">Type</label>
                    <div className="filter-options">
                      <button
                        onClick={() => setFilters({ messageType: 'all' })}
                        className={cn('filter-btn', filters.messageType === 'all' && 'active')}
                      >
                        All
                      </button>
                      <button
                        onClick={() => setFilters({ messageType: 'user' })}
                        className={cn('filter-btn', filters.messageType === 'user' && 'active')}
                      >
                        <User className="w-3 h-3" /> User
                      </button>
                      <button
                        onClick={() => setFilters({ messageType: 'assistant' })}
                        className={cn('filter-btn', filters.messageType === 'assistant' && 'active')}
                      >
                        <Bot className="w-3 h-3" /> Assistant
                      </button>
                    </div>
                  </div>

                  <div className="filter-row">
                    <label className="filter-label">Content</label>
                    <div className="filter-options">
                      <button
                        onClick={() =>
                          setFilters({
                            hasImages: filters.hasImages === true ? null : true,
                          })
                        }
                        className={cn('filter-btn', filters.hasImages === true && 'active')}
                      >
                        <ImageIcon className="w-3 h-3" /> Has Images
                      </button>
                      <button
                        onClick={() =>
                          setFilters({
                            hasCode: filters.hasCode === true ? null : true,
                          })
                        }
                        className={cn('filter-btn', filters.hasCode === true && 'active')}
                      >
                        <Code className="w-3 h-3" /> Has Code
                      </button>
                    </div>
                  </div>

                  <button onClick={resetFilters} className="reset-filters-btn">
                    Reset Filters
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results */}
            <div className="search-results">
              {isSearching && (
                <div className="search-loading">
                  <div className="loading-spinner" />
                  <span>Searching...</span>
                </div>
              )}

              {error && (
                <div className="search-error">
                  <span>{error}</span>
                </div>
              )}

              {!isSearching && !results && !filters.query && recentSearches.length > 0 && (
                <div className="recent-searches">
                  <div className="recent-header">
                    <Clock className="w-4 h-4" />
                    <span>Recent Searches</span>
                    <button onClick={clearRecentSearches} className="clear-recent">
                      Clear
                    </button>
                  </div>
                  <div className="recent-list">
                    {recentSearches.map((query, i) => (
                      <button
                        key={i}
                        onClick={() => searchImmediate(query)}
                        className="recent-item"
                      >
                        <Search className="w-3 h-3" />
                        {query}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {!isSearching && results && (
                <>
                  {results.matches.length === 0 ? (
                    <div className="no-results">
                      <span>No results found for &ldquo;{results.query}&rdquo;</span>
                    </div>
                  ) : (
                    <>
                      <div className="results-header">
                        <span>
                          {results.pagination.total} result{results.pagination.total !== 1 ? 's' : ''}
                        </span>
                      </div>
                      <div className="results-list">
                        {results.matches.map((match) => (
                          <button
                            key={match.message_id}
                            onClick={() => handleResultClick(match)}
                            className="result-item"
                          >
                            <div className="result-meta">
                              <span className={cn('result-role', match.role)}>
                                {match.role === 'user' ? (
                                  <User className="w-3 h-3" />
                                ) : (
                                  <Bot className="w-3 h-3" />
                                )}
                                {match.role}
                              </span>
                              <span className="result-date">{formatDate(match.created_at)}</span>
                              {match.has_images && <ImageIcon className="w-3 h-3 text-muted-foreground" />}
                              {match.has_code && <Code className="w-3 h-3 text-muted-foreground" />}
                            </div>
                            {renderHighlights(match.highlights)}
                            {match.highlights.length === 0 && (
                              <p className="result-content">{match.content}</p>
                            )}
                          </button>
                        ))}
                      </div>

                      {results.pagination.total_pages > 1 && (
                        <div className="pagination">
                          <button
                            onClick={prevPage}
                            disabled={currentPage === 1}
                            className="page-btn"
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </button>
                          <span className="page-info">
                            Page {currentPage} of {results.pagination.total_pages}
                          </span>
                          <button
                            onClick={nextPage}
                            disabled={currentPage === results.pagination.total_pages}
                            className="page-btn"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              {!isSearching && !results && !recentSearches.length && (
                <div className="search-empty">
                  <Search className="w-8 h-8 text-muted-foreground" />
                  <p>Search across all your conversations</p>
                  <p className="search-hint">
                    <kbd>Ctrl</kbd> + <kbd>K</kbd> to toggle search
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
