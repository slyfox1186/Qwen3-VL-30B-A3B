'use client';

import { ChevronDown, Cpu, Eye, Sparkles, Wrench, Zap } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

interface ModelMetrics {
  success_rate: number;
  avg_latency_ms: number;
  avg_tokens_per_second: number;
  total_requests: number;
}

interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  capabilities: string[];
  max_tokens: number;
  context_window: number;
  status: string;
  priority: number;
  metrics: ModelMetrics;
}

interface ModelSelectorProps {
  selectedModel: string | null;
  onModelChange: (modelId: string) => void;
  disabled?: boolean;
}

const CAPABILITY_ICONS: Record<string, React.ReactNode> = {
  vision: <Eye className="w-3 h-3" />,
  tool_use: <Wrench className="w-3 h-3" />,
  thinking: <Sparkles className="w-3 h-3" />,
  streaming: <Zap className="w-3 h-3" />,
};

export function ModelSelector({
  selectedModel,
  onModelChange,
  disabled = false,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch models
  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/v1/models');
      if (!response.ok) {
        throw new Error('Failed to fetch models');
      }

      const data = await response.json();
      setModels(data.models || []);

      // Auto-select first available model if none selected
      if (!selectedModel && data.models?.length > 0) {
        const available = data.models.find(
          (m: ModelInfo) => m.status === 'available'
        );
        if (available) {
          onModelChange(available.id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setLoading(false);
    }
  }, [selectedModel, onModelChange]);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Get selected model info
  const selected = models.find((m) => m.id === selectedModel);

  // Group models by status
  const availableModels = models.filter((m) => m.status === 'available');
  const degradedModels = models.filter((m) => m.status === 'degraded');
  const unavailableModels = models.filter((m) => m.status === 'unavailable');

  const handleModelSelect = (modelId: string) => {
    const model = models.find((m) => m.id === modelId);
    if (model && model.status !== 'unavailable') {
      onModelChange(modelId);
      setIsOpen(false);
    }
  };

  const formatLatency = (ms: number) => {
    if (ms === 0) return '-';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatSuccessRate = (rate: number) => {
    return `${Math.round(rate * 100)}%`;
  };

  const formatContextWindow = (tokens: number) => {
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${Math.round(tokens / 1000)}K`;
    return tokens.toString();
  };

  const renderModelOption = (model: ModelInfo) => {
    const isSelected = model.id === selectedModel;
    const isDisabled = model.status === 'unavailable';

    return (
      <div
        key={model.id}
        className={`model-option ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
        onClick={() => !isDisabled && handleModelSelect(model.id)}
      >
        <span className={`model-status-dot ${model.status}`} />
        <div className="model-option-content">
          <div className="model-option-header">
            <span className="model-option-name">{model.name}</span>
            <span className="model-option-provider">{model.provider}</span>
          </div>

          <div className="model-option-meta">
            {model.capabilities
              .filter((cap) => ['vision', 'tool_use', 'thinking'].includes(cap))
              .map((cap) => (
                <span key={cap} className={`capability-badge ${cap}`}>
                  {CAPABILITY_ICONS[cap]}
                  {cap.replace('_', ' ')}
                </span>
              ))}
            <span className="capability-badge">
              {formatContextWindow(model.context_window)} ctx
            </span>
          </div>

          {model.metrics.total_requests > 0 && (
            <div className="model-metrics">
              <span className="metric">
                Success:{' '}
                <span className="metric-value">
                  {formatSuccessRate(model.metrics.success_rate)}
                </span>
              </span>
              <span className="metric">
                Latency:{' '}
                <span className="metric-value">
                  {formatLatency(model.metrics.avg_latency_ms)}
                </span>
              </span>
              {model.metrics.avg_tokens_per_second > 0 && (
                <span className="metric">
                  Speed:{' '}
                  <span className="metric-value">
                    {Math.round(model.metrics.avg_tokens_per_second)} tok/s
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="model-selector" ref={dropdownRef}>
      <button
        className="model-selector-trigger"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        data-state={isOpen ? 'open' : 'closed'}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <Cpu className="model-icon" />
        <span className="model-name">
          {selected ? selected.name : 'Select model'}
        </span>
        {selected && <span className={`model-status-dot ${selected.status}`} />}
        <ChevronDown className="chevron" />
      </button>

      <div
        className="model-selector-dropdown"
        data-state={isOpen ? 'open' : 'closed'}
        role="listbox"
      >
        {loading ? (
          <div className="model-selector-loading">Loading models...</div>
        ) : error ? (
          <div className="model-selector-error">{error}</div>
        ) : (
          <>
            {availableModels.length > 0 && (
              <>
                <div className="model-section-header">Available</div>
                {availableModels.map(renderModelOption)}
              </>
            )}

            {degradedModels.length > 0 && (
              <>
                <div className="model-section-divider" />
                <div className="model-section-header">Degraded</div>
                {degradedModels.map(renderModelOption)}
              </>
            )}

            {unavailableModels.length > 0 && (
              <>
                <div className="model-section-divider" />
                <div className="model-section-header">Unavailable</div>
                {unavailableModels.map(renderModelOption)}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
