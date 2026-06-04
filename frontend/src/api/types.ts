// ===== Shared Types =====

export interface FiveDimScores {
  originality: number
  rigor: number
  completeness: number
  pedagogy: number
  impact: number
}

// ===== Article Types =====

export interface ArticleSummary {
  id: number
  title: string
  status: string
  authors: AuthorInfo[]
  score: FiveDimScores | null
  review_count: number
  created_at: string
  updated_at: string
}

export interface ArticleDetail {
  id: number
  title: string
  status: string
  authors: AuthorInfo[]
  fork_count: number
  forked_from: number | null
  compiled_format: string | null
  compiled_output: string | null
  compiled_pages: number | null
  score: FiveDimScores | null
  sink_eta: string | null
  days_remaining: number | null
  review_count: number
  created_at: string
  updated_at: string
}

export interface AuthorInfo {
  id: number
  name: string
  anonymous_name: string
  affiliation?: string
}

export interface ArticleCreatePayload {
  authors: number[]
  self_review: FiveDimScores
  title?: string
  abstract?: string
  keywords?: string[]
  categories?: string[]
}

export interface SinkExtensionPayload {
  extra_days: number
}

export interface ArticleHistory {
  commits: CommitInfo[]
}

export interface CommitInfo {
  hash: string
  author: string
  message: string
  timestamp: string
}

export interface ArticleDiff {
  diff_text: string
  files: string[]
}

export interface MergeProposal {
  id: number
  article_id: number
  fork_article_id: number
  proposer_id: number
  status: string
  created_at: string
}

// ===== Review Types =====

export interface ThreadMessage {
  author_id: number
  content: string
  created_at: string
}

export interface ReviewOut {
  id: number
  article_id: number
  commit_hash: string
  reviewer_id: number
  scope: 'pool' | 'published'
  scores: FiveDimScores
  thread: ThreadMessage[]
  reviewer_name: string
  is_self_review: boolean
  created_at: string
  updated_at: string
}

export interface ReviewCreatePayload {
  article_id: number
  commit_hash: string
  reviewer_id: number
  scope: 'pool' | 'published'
  scores: FiveDimScores
}

export interface ReviewMessagePayload {
  content: string
}

// ===== User Types =====

export interface UserProfile {
  id: number
  name: string
  anonymous_name: string
  affiliation?: string
  expertise: string[]
  reputation: ReputationScores
  followers_count: number
  following_count: number
  article_count: number
  created_at: string
}

export interface UserSummary {
  id: number
  name: string
  anonymous_name: string
  affiliation?: string
}

export interface ReputationScores {
  professionalism: number
  objectivity: number
  collaboration: number
  pedagogy: number
}

export interface UserCreatePayload {
  name: string
  affiliation?: string
  expertise?: string[]
}

// ===== Pool Types =====

export interface PoolResponse {
  articles: ArticleSummary[]
}

// ===== Bookmark Types =====

export interface Bookmark {
  id: number
  user_id: number
  article_id: number
  created_at: string
}

// ===== Feed Types =====

export interface FeedItem {
  type: string
  article_id: number
  title: string
  action: string
  user_name: string
  timestamp: string
}

// ===== Search Types =====

export interface SearchResult {
  articles: ArticleSummary[]
  total: number
  query: string
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

export interface Citation {
  id: number
  from_article_id: number
  to_article_id: number
  count: number
}

export interface CitationClickPayload {
  from_article_id: number
  to_article_id: number
}
