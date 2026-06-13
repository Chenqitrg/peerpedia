// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

// Local Git operations via CLI.
//
// Every draft save is a git commit. This gives local mode full version
// history — the same primitives the server uses (git_backend.py).
//
// Reuses the same directory layout as the server:
//   ~/.peerpedia/articles/{article_id}/

use crate::error::AppError;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;

/// Returns the base directory for article Git repositories.
/// In tests, respects PEERPEDIA_TEST_HOME for isolation.
fn articles_dir() -> Result<PathBuf, AppError> {
    let home = std::env::var("PEERPEDIA_TEST_HOME")
        .or_else(|_| std::env::var("HOME"))
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));
    let dir = home.join(".peerpedia").join("articles");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

/// Validate article_id contains only safe characters — prevents path traversal.
fn validate_article_id(article_id: &str) -> Result<(), AppError> {
    if article_id.is_empty() {
        return Err(AppError::AuthFailed("article_id cannot be empty".into()));
    }
    if !article_id
        .chars()
        .all(|c| c.is_alphanumeric() || c == '-' || c == '_')
    {
        return Err(AppError::AuthFailed(format!(
            "Invalid article_id '{}': only alphanumeric, hyphens, and underscores allowed",
            article_id
        )));
    }
    Ok(())
}

pub fn repo_path(article_id: &str) -> Result<PathBuf, AppError> {
    validate_article_id(article_id)?;
    Ok(articles_dir()?.join(article_id))
}

// ── Init ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitCommitResult {
    pub hash: String,
    pub message: String,
}

/// Initialize a git repo for a new article. Creates the directory, writes
/// the initial content file, and makes the first commit.
pub fn git_init(
    article_id: &str,
    content: &str,
    format: &str,
    commit_message: &str,
    author_name: &str,
    author_id: &str,
) -> Result<GitCommitResult, AppError> {
    let rp = repo_path(article_id)?;
    std::fs::create_dir_all(&rp)?;

    // git init
    run_git(&rp, &["init"])?;

    // Write article file
    let ext = if format == "typst" { ".typ" } else { ".md" };
    let file_path = rp.join(format!("article{}", ext));
    std::fs::write(&file_path, content)?;

    // git add + commit — author_id is UUID, author_name is display
    run_git(&rp, &["add", "-A"])?;
    let author_email = format!("{}@peerpedia", author_id);
    run_git(
        &rp,
        &[
            "-c",
            &format!("user.name={}", author_name),
            "-c",
            &format!("user.email={}", author_email),
            "commit",
            "-m",
            commit_message,
            "--allow-empty",
        ],
    )?;

    let hash = get_head_hash(&rp)?;
    Ok(GitCommitResult {
        hash,
        message: commit_message.to_string(),
    })
}

/// Commit current content to an existing git repo.
pub fn git_commit(
    article_id: &str,
    content: &str,
    format: &str,
    commit_message: &str,
    author_name: &str,
    author_id: &str,
) -> Result<GitCommitResult, AppError> {
    let rp = repo_path(article_id)?;

    // Check that repo exists
    if !rp.join(".git").is_dir() {
        return Err(AppError::NotFound(format!(
            "Git repo not found for article '{}'. Save the article first.",
            article_id
        )));
    }

    // Write article file
    let ext = if format == "typst" { ".typ" } else { ".md" };
    let file_path = rp.join(format!("article{}", ext));
    std::fs::write(&file_path, content)?;

    // git add + commit — author_id is UUID, author_name is display
    run_git(&rp, &["add", "-A"])?;
    let author_email = format!("{}@peerpedia", author_id);
    run_git(
        &rp,
        &[
            "-c",
            &format!("user.name={}", author_name),
            "-c",
            &format!("user.email={}", author_email),
            "commit",
            "-m",
            commit_message,
            "--allow-empty",
        ],
    )?;

    let hash = get_head_hash(&rp)?;
    Ok(GitCommitResult {
        hash,
        message: commit_message.to_string(),
    })
}

// ── Export ────────────────────────────────────────────────────────────────

/// Create a tar.gz bundle of the article git repository and return base64-encoded bytes.
pub fn export_article(article_id: &str) -> Result<String, AppError> {
    use base64::Engine;
    use std::io::Read;

    let rp = repo_path(article_id)?;
    if !rp.join(".git").is_dir() {
        return Err(AppError::NotFound(format!(
            "Git repo not found for article '{}'",
            article_id
        )));
    }

    let tmp_path = std::env::temp_dir().join(format!("peerpedia-{}.tar.gz", article_id));
    let parent = rp.parent().unwrap_or(&rp);
    let dirname = rp.file_name().unwrap_or(rp.as_os_str());

    let output = Command::new("tar")
        .args([
            "-czf",
            tmp_path.to_str().unwrap_or("export.tar.gz"),
            "-C",
            parent.to_str().unwrap_or("."),
            dirname.to_str().unwrap_or("article"),
        ])
        .output()
        .map_err(|e| AppError::IoError(format!("Failed to run tar: {}", e)))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let _ = std::fs::remove_file(&tmp_path);
        return Err(AppError::IoError(format!("tar failed: {}", stderr)));
    }

    let mut buf = Vec::new();
    std::fs::File::open(&tmp_path)
        .and_then(|mut f| f.read_to_end(&mut buf))
        .map_err(|e| AppError::IoError(format!("Failed to read archive: {}", e)))?;
    let _ = std::fs::remove_file(&tmp_path);

    Ok(base64::engine::general_purpose::STANDARD.encode(&buf))
}

// ── History ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitEntry {
    pub hash: String,
    pub message: String,
    pub author: String,
    pub timestamp: String,
}

/// Get commit history for an article.
pub fn git_history(article_id: &str) -> Result<Vec<CommitEntry>, AppError> {
    let rp = repo_path(article_id)?;
    if !rp.join(".git").is_dir() {
        return Err(AppError::NotFound(format!(
            "Git repo not found for article '{}'",
            article_id
        )));
    }

    let output = Command::new("git")
        .args([
            "log",
            "--pretty=format:%H%x00%s%x00%an%x00%aI",
            "--name-only",
        ])
        .current_dir(&rp)
        .output()
        .map_err(|e| AppError::IoError(format!("git log failed: {}", e)))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(AppError::DatabaseError(format!(
            "git log error: {}",
            stderr
        )));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut entries = Vec::new();
    // Each commit is on one line: hash\0message\0author\0timestamp
    for line in stdout.lines() {
        let parts: Vec<&str> = line.split('\0').collect();
        if parts.len() >= 4 {
            entries.push(CommitEntry {
                hash: parts[0].to_string(),
                message: parts[1].to_string(),
                author: parts[2].to_string(),
                timestamp: parts[3].to_string(),
            });
        }
    }

    Ok(entries)
}

// ── Show ─────────────────────────────────────────────────────────────────

/// Return the content of an article file at a given commit.
/// Returns (content, format) where format is "md" or "typ"
pub fn git_show(article_id: &str, commit_hash: &str) -> Result<(String, String), AppError> {
    let rp = repo_path(article_id)?;

    // Try .md first, then .typ
    for ext in &[".md", ".typ"] {
        let file = format!("article{}", ext);
        let output = Command::new("git")
            .args(["show", &format!("{}:{}", commit_hash, file)])
            .current_dir(&rp)
            .output();

        match output {
            Ok(o) if o.status.success() => {
                let content = String::from_utf8_lossy(&o.stdout).to_string();
                let fmt = if *ext == ".typ" { "typst" } else { "markdown" };
                return Ok((content, fmt.to_string()));
            }
            _ => continue,
        }
    }

    Err(AppError::NotFound(format!(
        "Could not read article file at commit '{}'",
        commit_hash
    )))
}

// ── Helpers ──────────────────────────────────────────────────────────────

fn run_git(repo_path: &PathBuf, args: &[&str]) -> Result<(), AppError> {
    let output = Command::new("git")
        .args(args)
        .current_dir(repo_path)
        .output()
        .map_err(|e| AppError::IoError(format!("Failed to run git: {}", e)))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(AppError::DatabaseError(format!("git error: {}", stderr)));
    }
    Ok(())
}

// ── Diff ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiffLineType {
    #[serde(rename = "add")]
    Add,
    #[serde(rename = "del")]
    Delete,
    #[serde(rename = "ctx")]
    Context,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffLine {
    pub line_type: DiffLineType,
    pub content: String,
    pub old_lineno: Option<u32>,
    pub new_lineno: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffHunk {
    pub old_start: u32,
    pub old_lines: u32,
    pub new_start: u32,
    pub new_lines: u32,
    pub header: String,
    pub lines: Vec<DiffLine>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffResult {
    pub files: Vec<String>,
    pub hunks: Vec<DiffHunk>,
}

/// Parse `git diff hash1..hash2 --unified=3` output into structured DiffResult.
pub fn git_diff(article_id: &str, hash1: &str, hash2: &str) -> Result<DiffResult, AppError> {
    let rp = repo_path(article_id)?;
    if !rp.join(".git").is_dir() {
        return Err(AppError::NotFound(format!(
            "Git repo not found for article '{}'",
            article_id
        )));
    }

    let output = Command::new("git")
        .args(["diff", &format!("{}..{}", hash1, hash2), "--unified=3"])
        .current_dir(&rp)
        .output()
        .map_err(|e| AppError::IoError(format!("git diff failed: {}", e)))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(AppError::DatabaseError(format!(
            "git diff error: {}",
            stderr
        )));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_diff_output(&stdout)
}

fn parse_diff_output(output: &str) -> Result<DiffResult, AppError> {
    let mut files: Vec<String> = Vec::new();
    let mut hunks: Vec<DiffHunk> = Vec::new();
    let mut current_hunk: Option<DiffHunk> = None;
    let mut old_line = 0u32;
    let mut new_line = 0u32;

    for line in output.lines() {
        if line.starts_with("diff --git ") {
            // Push current hunk if any
            if let Some(hunk) = current_hunk.take() {
                hunks.push(hunk);
            }
            // Extract filename from "diff --git a/path b/path"
            let parts: Vec<&str> = line.split_whitespace().collect();
            if let Some(path) = parts.get(3) {
                let path = path.trim_start_matches("b/");
                if !files.contains(&path.to_string()) {
                    files.push(path.to_string());
                }
            }
        } else if line.starts_with("@@") {
            // Push previous hunk
            if let Some(hunk) = current_hunk.take() {
                hunks.push(hunk);
            }
            // Parse "@@ -old_start,old_lines +new_start,new_lines @@ header"
            if let Some(parsed) = parse_hunk_header(line) {
                old_line = parsed.0;
                new_line = parsed.1;
                current_hunk = Some(DiffHunk {
                    old_start: parsed.0,
                    old_lines: parsed.2,
                    new_start: parsed.1,
                    new_lines: parsed.3,
                    header: parsed.4.clone(),
                    lines: Vec::new(),
                });
            }
        } else if let Some(ref mut hunk) = current_hunk {
            let (lt, ct, old_no, new_no) = if line.starts_with("+") && !line.starts_with("+++") {
                let content = if line.len() > 1 { &line[1..] } else { "" };
                let ln = new_line;
                new_line += 1;
                (DiffLineType::Add, content.to_string(), None, Some(ln))
            } else if line.starts_with("-") && !line.starts_with("---") {
                let content = if line.len() > 1 { &line[1..] } else { "" };
                let ln = old_line;
                old_line += 1;
                (DiffLineType::Delete, content.to_string(), Some(ln), None)
            } else if line.starts_with("\\ ") && line.contains("No newline") {
                // Skip git "No newline" markers — they break diff pairing
                continue;
            } else {
                let content = if !line.is_empty() { line } else { "" };
                let (o, n) = (old_line, new_line);
                old_line += 1;
                new_line += 1;
                (DiffLineType::Context, content.to_string(), Some(o), Some(n))
            };
            hunk.lines.push(DiffLine {
                line_type: lt,
                content: ct,
                old_lineno: old_no,
                new_lineno: new_no,
            });
        }
    }

    // Push last hunk
    if let Some(hunk) = current_hunk {
        hunks.push(hunk);
    }

    Ok(DiffResult { files, hunks })
}

fn parse_hunk_header(line: &str) -> Option<(u32, u32, u32, u32, String)> {
    // @@ -old_start,old_lines +new_start,new_lines @@ optional header
    let rest = line.strip_prefix("@@")?.trim();
    let rest = rest.strip_suffix("@@")?.trim();
    // Split into parts by space: the first part is "-old,lines" the second is "+new,lines"
    let parts: Vec<&str> = rest.splitn(3, ' ').collect();
    if parts.len() < 2 {
        return None;
    }
    let old_part = parts[0].trim_start_matches('-');
    let new_part = parts[1].trim_start_matches('+');
    let header = parts.get(2).unwrap_or(&"").to_string();

    let (old_start, old_lines) = parse_range(old_part);
    let (new_start, new_lines) = parse_range(new_part);

    Some((old_start, new_start, old_lines, new_lines, header))
}

fn parse_range(s: &str) -> (u32, u32) {
    if let Some((start, count)) = s.split_once(',') {
        (start.parse().unwrap_or(1), count.parse().unwrap_or(1))
    } else {
        (s.parse().unwrap_or(1), 1)
    }
}

fn get_head_hash(repo_path: &PathBuf) -> Result<String, AppError> {
    let output = Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(repo_path)
        .output()
        .map_err(|e| AppError::IoError(format!("git rev-parse failed: {}", e)))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        Err(AppError::DatabaseError("Could not resolve HEAD".into()))
    }
}

// ── Rollback ──────────────────────────────────────────────────────────────

/// Hard-reset to a previous commit. Does NOT create a new commit — the branch
/// pointer moves back and all later commits are discarded. Use for discard/revert
/// of offline changes where no trace should remain.
pub fn git_reset_hard(article_id: &str, commit_hash: &str) -> Result<(), AppError> {
    let rp = repo_path(article_id)?;
    if !rp.join(".git").is_dir() {
        return Err(AppError::NotFound(format!(
            "Git repo not found for article '{}'",
            article_id
        )));
    }
    run_git(&rp, &["reset", "--hard", commit_hash])?;
    Ok(())
}

/// Rollback to a previous commit by composing git_show + git_commit.
/// Retrieves content at `commit_hash`, then commits it as a new "Rollback to ..." commit.
pub fn git_rollback(
    article_id: &str,
    commit_hash: &str,
    author_name: &str,
    author_id: &str,
) -> Result<GitCommitResult, AppError> {
    let rp = repo_path(article_id)?;
    let (old_content, format) = git_show(article_id, commit_hash)?;
    let short_hash = if commit_hash.len() >= 8 {
        &commit_hash[..8]
    } else {
        commit_hash
    };
    let message = format!("Rollback to {}", short_hash);

    // Clean up stale file from wrong-format extension (caused by previous buggy rollbacks).
    // If the primary file is article.typ, remove article.md if it exists, and vice versa.
    let stale_ext = if format == "typst" { ".md" } else { ".typ" };
    let stale_path = rp.join(format!("article{}", stale_ext));
    if stale_path.exists() {
        std::fs::remove_file(&stale_path).ok();
    }

    git_commit(
        article_id,
        &old_content,
        &format,
        &message,
        author_name,
        author_id,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::OnceLock;

    /// A mutex to serialize git tests that set PEERPEDIA_TEST_HOME.
    /// This prevents parallel test threads from clobbering each other's env vars.
    static GIT_TEST_LOCK: OnceLock<std::sync::Mutex<()>> = OnceLock::new();
    fn git_test_lock() -> &'static std::sync::Mutex<()> {
        GIT_TEST_LOCK.get_or_init(|| std::sync::Mutex::new(()))
    }

    fn setup_dir() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("peerpedia-test-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn cleanup(dir: &PathBuf) {
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn test_init_and_history() {
        let _lock = git_test_lock().lock().unwrap();
        let dir = setup_dir();
        // Override articles_dir by setting PEERPEDIA_TEST_HOME
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("PEERPEDIA_TEST_HOME", &home);

        let result = git_init(
            "test-art",
            "# Hello",
            "markdown",
            "Initial draft",
            "alice",
            "uuid-1",
        );
        assert!(result.is_ok(), "git_init failed: {:?}", result.err());
        let commit = result.unwrap();
        assert!(!commit.hash.is_empty());

        let history = git_history("test-art").unwrap();
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].message, "Initial draft");
        assert_eq!(history[0].author, "alice");

        let (content, _fmt) = git_show("test-art", &commit.hash).unwrap();
        assert_eq!(content, "# Hello");

        cleanup(&dir);
    }

    #[test]
    fn test_multiple_commits() {
        let _lock = git_test_lock().lock().unwrap();
        let dir = setup_dir();
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("PEERPEDIA_TEST_HOME", &home);

        git_init("multi", "v1", "markdown", "First", "bob", "uuid-bob").unwrap();
        git_commit("multi", "v2", "markdown", "Second", "bob", "uuid-bob").unwrap();
        git_commit("multi", "v3", "markdown", "Third", "bob", "uuid-bob").unwrap();

        let history = git_history("multi").unwrap();
        assert_eq!(history.len(), 3);
        assert_eq!(history[0].message, "Third"); // newest first
        assert_eq!(history[2].message, "First"); // oldest last

        // Show v1 content
        let (v1_content, _fmt) = git_show("multi", &history[2].hash).unwrap();
        assert_eq!(v1_content, "v1");

        cleanup(&dir);
    }

    #[test]
    fn test_commit_nonexistent_repo() {
        let result = git_commit(
            "no-such-repo",
            "content",
            "markdown",
            "msg",
            "bob",
            "uuid-bob",
        );
        assert!(result.is_err());
    }

    #[test]
    fn test_history_nonexistent_repo() {
        let result = git_history("ghost-repo");
        assert!(result.is_err());
    }

    #[test]
    fn test_rollback_creates_revert_commit() {
        let _lock = git_test_lock().lock().unwrap();
        let dir = setup_dir();
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("PEERPEDIA_TEST_HOME", &home);

        // Create an article with 3 commits
        git_init("rb-test", "v1", "markdown", "First", "alice", "uuid-alice").unwrap();
        git_commit("rb-test", "v2", "markdown", "Second", "alice", "uuid-alice").unwrap();
        let third =
            git_commit("rb-test", "v3", "markdown", "Third", "alice", "uuid-alice").unwrap();

        // Get the hash of the first commit
        let history = git_history("rb-test").unwrap();
        assert_eq!(history.len(), 3);
        let first_hash = &history[2].hash; // oldest commit

        // Rollback to first commit
        let result = git_rollback("rb-test", first_hash, "alice", "uuid-alice");
        assert!(result.is_ok(), "git_rollback failed: {:?}", result.err());
        let rb = result.unwrap();
        assert!(
            rb.message.contains("Rollback to"),
            "message should contain 'Rollback to'"
        );

        // Content should be restored to v1
        let (content, fmt) = git_show("rb-test", &rb.hash).unwrap();
        assert_eq!(
            fmt, "markdown",
            "rollback to markdown repo should detect markdown format"
        );
        assert_eq!(content, "v1");

        // History should now have 4 commits
        let history2 = git_history("rb-test").unwrap();
        assert_eq!(history2.len(), 4);

        cleanup(&dir);
    }

    #[test]
    fn test_rollback_bad_hash_returns_error() {
        let _lock = git_test_lock().lock().unwrap();
        let dir = setup_dir();
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("PEERPEDIA_TEST_HOME", &home);

        git_init("rb-bad", "v1", "markdown", "First", "alice", "uuid-alice").unwrap();
        let result = git_rollback("rb-bad", "deadbeef12345678", "alice", "uuid-alice");
        assert!(result.is_err());

        cleanup(&dir);
    }

    #[test]
    fn test_rollback_creates_revert_commit_typst() {
        let _lock = git_test_lock().lock().unwrap();
        let dir = setup_dir();
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("PEERPEDIA_TEST_HOME", &home);

        // Create a Typst article with 3 commits
        git_init("rb-typst", "= v1", "typst", "First", "alice", "uuid-alice").unwrap();
        git_commit("rb-typst", "= v2", "typst", "Second", "alice", "uuid-alice").unwrap();
        let third =
            git_commit("rb-typst", "= v3", "typst", "Third", "alice", "uuid-alice").unwrap();

        let history = git_history("rb-typst").unwrap();
        assert_eq!(history.len(), 3);
        let first_hash = &history[2].hash;

        // Rollback to first commit — auto-detects typst format, no format param
        let result = git_rollback("rb-typst", first_hash, "alice", "uuid-alice");
        assert!(result.is_ok(), "git_rollback failed: {:?}", result.err());
        let rb = result.unwrap();

        // Content restored to = v1, format auto-detected as "typst"
        let (content, fmt) = git_show("rb-typst", &rb.hash).unwrap();
        assert_eq!(
            fmt, "typst",
            "rollback to typst repo should detect typst format"
        );
        assert_eq!(content, "= v1");

        // Verify no stale .md file was created
        let rp = repo_path("rb-typst").unwrap();
        assert!(
            !rp.join("article.md").exists(),
            "rollback should not create article.md in a typst repo"
        );

        cleanup(&dir);
    }

    #[test]
    fn test_rejects_path_traversal_article_id() {
        // article_id with slashes or dots that escape the articles dir
        // These should fail at validation before any filesystem op.
        assert!(git_init("../../etc/passwd", "x", "md", "msg", "alice", "uuid-alice").is_err());
        assert!(git_commit("../../etc/passwd", "x", "md", "msg", "alice", "uuid-alice").is_err());
        assert!(git_history("../../etc/passwd").is_err());
        assert!(git_show("../../etc/passwd", "abc123").is_err());
        assert!(git_rollback("../../etc/passwd", "abc123", "alice", "uuid-alice").is_err());

        // article_id with backslashes (Windows)
        assert!(git_init(
            "..\\..\\windows\\system32",
            "x",
            "md",
            "msg",
            "alice",
            "uuid-alice"
        )
        .is_err());

        // article_id with null byte
        assert!(git_init("bad\0art", "x", "md", "msg", "alice", "uuid-alice").is_err());

        // empty article_id
        assert!(git_init("", "x", "md", "msg", "alice", "uuid-alice").is_err());

        // normal ids still pass validation
        assert!(validate_article_id("normal-id_123").is_ok());
        assert!(validate_article_id("abc123").is_ok());
        assert!(validate_article_id("a-b_c").is_ok());
    }
}
