export interface Session {
  id: string;
  user_id?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  metadata?: Record<string, unknown>;
}

export interface SearchResult {
  title: string;
  link: string;
  snippet?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thought?: string;
  search_results?: SearchResult[]; // LLM web search results
  search_query?: string; // Query used for web search
  created_at: string;
  // Thread system fields
  thread_id?: string; // ID of thread this message belongs to
  is_pinned?: boolean; // Whether message is pinned to top
  thread_position?: number; // Position within thread
}

export interface Thread {
  id: string;
  name?: string;
  messages: string[]; // Message IDs
  created_at: string;
  updated_at: string;
  collapsed?: boolean;
}

export interface ChatRequest {
  message: string;
  max_tokens?: number;
  temperature?: number;
}

export interface ChatResponseSync {
  request_id: string;
  session_id: string;
  content: string;
  thought?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
  };
  created_at: string;
}

export type SSEEventType =
  | 'start'
  | 'thought_start'
  | 'thought_delta'
  | 'thought_end'
  | 'content_start'
  | 'content_delta'
  | 'content_end'
  | 'done'
  | 'error';

export interface SSEEvent {
  type: SSEEventType;
  request_id?: string;
  content?: string;
  thought?: string;
  error?: string;
  code?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
  };
}

export interface TitleGenerateResponse {
  title: string;
  generated: boolean;
}
