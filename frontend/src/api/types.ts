// ===== Shared Types =====

export interface FiveDimScores {
  originality: number
  rigor: number
  completeness: number
  pedagogy: number
  impact: number
}

/** Per-author 5-dim contribution ratios. Each dimension sums to 1.0 across all authors. */
export interface AuthorContributions {
  [authorId: string]: FiveDimScores
}

// ===== Pagination =====

export interface PaginationParams {
  page?: number
  size?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

// ===== Article Types =====

export interface ArticleSummary {
  id: string
  title: string
  status: 'draft' | 'sedimentation' | 'published'
  authors: AuthorInfo[]
  abstract: string | null
  content_preview: string
  commit_hash: string
  fork_count: number
  forked_from: string | null
  commit_count: number
  score: FiveDimScores | null
  sink_eta: string | null
  days_remaining: number | null
  sink_duration_days: number | null
  is_bookmarked: boolean
  is_own_article: boolean
  created_at: string
  updated_at: string
}

export interface ArticleDetail {
  id: string
  title: string
  status: 'draft' | 'sedimentation' | 'published'
  authors: AuthorInfo[]
  commit_hash: string
  fork_count: number
  forked_from: string | null
  commit_count: number
  compiled_format: string | null
  compiled_output: string | null
  compiled_pages: number | null
  score: FiveDimScores | null
  sink_eta: string | null
  days_remaining: number | null
  sink_duration_days: number | null
  review_count: number
  is_bookmarked: boolean
  is_own_article: boolean
  created_at: string
  updated_at: string
}

export interface AuthorInfo {
  id: string
  name: string
  anonymous_name: string
  affiliation?: string
  expertise?: string[]
}

export interface ArticleCreatePayload {
  authors: string[]
  self_review: FiveDimScores
  contributions?: AuthorContributions
  commit_message: string
  title?: string
  abstract?: string
  keywords?: string[]
  categories?: string[]
  content?: string
  format?: 'markdown' | 'typst'
  forked_from?: string
}

export interface ArticleUpdatePayload {
  commit_message?: string
  title?: string
  abstract?: string
  keywords?: string[]
  categories?: string[]
  content?: string
  self_review?: FiveDimScores
  contributions?: AuthorContributions
  publish?: boolean
}

export interface SinkExtensionPayload {
  extra_days: number
}

export interface ArticleSource {
  content: string
  format: 'markdown' | 'typst'
}

export interface ArticleHistory {
  commits: CommitInfo[]
}

export interface CommitInfo {
  hash: string
  parents: string[]
  author: string
  message: string
  timestamp: string
  score?: FiveDimScores | null
}

export interface ArticleDiff {
  diff_text: string
  files: string[]
}

export interface MergeProposal {
  id: string
  article_id: string
  fork_article_id: string
  proposer_id: string
  status: 'open' | 'accepted' | 'rejected'
  created_at: string
}

// ===== Review Types =====

export interface ThreadMessage {
  author_id: string
  content: string
  author_name: string  // resolved at post time; empty string for pre-existing messages
  created_at: string
}

export interface ReviewOut {
  id: string
  article_id: string
  commit_hash: string
  reviewer_id: string
  scope: 'pool' | 'published'
  scores: FiveDimScores
  contributions?: AuthorContributions | null
  thread: ThreadMessage[]
  reviewer_name: string
  is_self_review: boolean
  created_at: string
  updated_at: string
}

/** reviewer_id is set server-side from JWT — do not send */
export interface ReviewCreatePayload {
  article_id: string
  commit_hash: string
  scope: 'pool' | 'published'
  scores: FiveDimScores
  contributions?: AuthorContributions
}

export interface ReviewMessagePayload {
  content: string
}

// ===== User Types =====

export interface UserProfile {
  id: string
  username: string
  name: string
  anonymous_name: string
  affiliation?: string
  expertise: string[]
  avatar_url?: string | null
  contact?: string | null
  reputation: ReputationScores
  followers_count: number
  following_count: number
  article_count: number
  created_at: string
}

export interface UserSummary {
  id: string
  name: string
  anonymous_name: string
  affiliation?: string
  expertise?: string[]
  avatar_url?: string | null
  article_count: number
  reputation: ReputationScores
}

export interface ReputationScores {
  professionalism: number
  objectivity: number
  collaboration: number
  pedagogy: number
}

export interface UserCreatePayload {
  username: string
  password: string
  email: string
  name: string
  affiliation?: string
  expertise?: string[]
  avatar_url?: string
  contact?: string
}

export interface UserUpdatePayload {
  anonymous_name?: string
  affiliation?: string
  expertise?: string[]
  avatar_url?: string
  contact?: string
}

// ===== Pool Types =====

export interface PoolResponse {
  articles: ArticleSummary[]
  total: number
}

// ===== Bookmark Types =====

export interface Bookmark {
  id: string
  user_id: string
  article_id: string
  created_at: string
}

// ===== Feed Types =====

/** Feed items are article summaries from followed users, sorted by recency. */
export interface FeedResponse {
  articles: ArticleSummary[]
  total: number
  page?: number
  size?: number
}

// ===== Search Types =====

export interface SearchResult {
  articles: ArticleSummary[]
  total: number
  query: string
  page?: number
  size?: number
}

// ===== Compile Preview Types =====

export interface CompilePreviewPayload {
  content: string
  format: 'markdown' | 'typst'
}

export interface CompilePreviewResponse {
  output: string
  format: string
}

// ===== Citation Types =====

export interface CitationEdge {
  article_id: string
  title: string
  forward_prob: number
  backward_prob: number
}

export interface CitationGraph {
  cites: CitationEdge[]
  cited_by: CitationEdge[]
}

export interface CitationClickPayload {
  from_article_id: string
  to_article_id: string
}

// ===== Fork Check =====

export interface HasForkedResponse {
  has_forked: boolean
  fork_article_id: string | null
}

// ===== Auth Types =====

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  email: string
  name: string
}

export interface AuthResponse {
  user: UserProfile
  token: string
}
