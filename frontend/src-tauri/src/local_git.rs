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

fn articles_dir() -> Result<PathBuf, AppError> {
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));
    let dir = home.join(".peerpedia").join("articles");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn repo_path(article_id: &str) -> Result<PathBuf, AppError> {
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
    author: &str,
) -> Result<GitCommitResult, AppError> {
    let rp = repo_path(article_id)?;
    std::fs::create_dir_all(&rp)?;

    // git init
    run_git(&rp, &["init"])?;

    // Write article file
    let ext = if format == "typst" { ".typ" } else { ".md" };
    let file_path = rp.join(format!("article{}", ext));
    std::fs::write(&file_path, content)?;

    // git add + commit
    run_git(&rp, &["add", "-A"])?;
    let author_email = format!("{}@peerpedia.local", author);
    run_git(
        &rp,
        &[
            "-c",
            &format!("user.name={}", author),
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
    author: &str,
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

    // git add + commit
    run_git(&rp, &["add", "-A"])?;
    let author_email = format!("{}@peerpedia.local", author);
    run_git(
        &rp,
        &[
            "-c",
            &format!("user.name={}", author),
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
pub fn git_show(article_id: &str, commit_hash: &str) -> Result<String, AppError> {
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
                return Ok(String::from_utf8_lossy(&o.stdout).to_string());
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

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
        let dir = setup_dir();
        // Override articles_dir by setting HOME
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("HOME", &home);

        let result = git_init("test-art", "# Hello", "markdown", "Initial draft", "alice");
        assert!(result.is_ok(), "git_init failed: {:?}", result.err());
        let commit = result.unwrap();
        assert!(!commit.hash.is_empty());

        let history = git_history("test-art").unwrap();
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].message, "Initial draft");
        assert_eq!(history[0].author, "alice");

        let content = git_show("test-art", &commit.hash).unwrap();
        assert_eq!(content, "# Hello");

        cleanup(&dir);
    }

    #[test]
    fn test_multiple_commits() {
        let dir = setup_dir();
        let home = dir.join("home");
        fs::create_dir_all(&home).unwrap();
        std::env::set_var("HOME", &home);

        git_init("multi", "v1", "markdown", "First", "bob").unwrap();
        git_commit("multi", "v2", "markdown", "Second", "bob").unwrap();
        git_commit("multi", "v3", "markdown", "Third", "bob").unwrap();

        let history = git_history("multi").unwrap();
        assert_eq!(history.len(), 3);
        assert_eq!(history[0].message, "Third"); // newest first
        assert_eq!(history[2].message, "First"); // oldest last

        // Show v1 content
        let v1_content = git_show("multi", &history[2].hash).unwrap();
        assert_eq!(v1_content, "v1");

        cleanup(&dir);
    }

    #[test]
    fn test_commit_nonexistent_repo() {
        let result = git_commit("no-such-repo", "content", "markdown", "msg", "bob");
        assert!(result.is_err());
    }

    #[test]
    fn test_history_nonexistent_repo() {
        let result = git_history("ghost-repo");
        assert!(result.is_err());
    }
}
