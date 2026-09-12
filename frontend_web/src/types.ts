export interface RuntimeConfig {
  cognitoDomain: string;
  cognitoClientId: string;
  oauthScopes: string[];
}

export interface Session {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  email?: string;
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ToolCall {
  sql_query?: string;
  result_count?: number;
  results?: Record<string, unknown>[];
}

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
  tool_calls?: ToolCall[];
  imageUrl?: string;
  details?: DetailBlock[];
  thumbnails?: Thumbnail[];
  pending?: boolean;
  error?: boolean;
}

export interface DetailBlock {
  type: "enhanced_query" | "sql_query" | "query_results" | "retry_feedback";
  data: Record<string, unknown>;
}

export interface Thumbnail {
  file_id?: string;
  file_name?: string;
  file_type?: string;
  thumbnail_url: string;
}

export interface SSEMessage {
  event: string;
  data: Record<string, unknown>;
}
