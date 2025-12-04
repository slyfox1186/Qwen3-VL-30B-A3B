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
  thumbnail?: string;
  original_image?: string;
  snippet?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  images?: string[]; // Base64 strings or URLs (input)
  search_results?: SearchResult[]; // Images found by search
  search_query?: string; // Query used for search
  created_at: string;
}

export interface ChatRequest {
  message: string;
  images?: {
    data: string; // base64
    media_type?: string;
  }[];
  max_tokens?: number;
  temperature?: number;
}

export interface ChatResponseSync {
  request_id: string;
  session_id: string;
  content: string;
  search_results?: SearchResult[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
  };
  created_at: string;
}

export type SSEEventType =
  | 'start'
  | 'content_start'
  | 'content_delta'
  | 'content_end'
  | 'images'
  | 'done'
  | 'error';

export interface SSEEvent {
  type: SSEEventType;
  request_id?: string;
  content?: string;
  images?: SearchResult[];
  query?: string;
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
