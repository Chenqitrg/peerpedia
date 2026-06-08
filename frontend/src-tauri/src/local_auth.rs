// Local account system — bcrypt password hashing + SQLite storage.
//
// Accounts are stored in the local SQLite database. Passwords are hashed with bcrypt
// (default cost 12). Multi-account switching is supported — all accounts on the device
// can be listed and switched between.

use crate::error::AppError;
use bcrypt::{hash, verify, DEFAULT_COST};
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Account {
    pub id: String,
    pub username: String,
}

/// Account information plus a session token for authenticating subsequent commands.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountWithToken {
    pub id: String,
    pub username: String,
    pub token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountSummary {
    pub id: String,
    pub username: String,
}

// ── Session management ──────────────────────────────────────────────────

/// Create a session token for a given account. Returns the token string.
fn create_session(conn: &Connection, account_id: &str) -> Result<String, AppError> {
    let token = Uuid::new_v4().to_string();
    conn.execute(
        "INSERT INTO sessions (token, account_id) VALUES (?1, ?2)",
        rusqlite::params![token, account_id],
    )?;
    Ok(token)
}

/// Verify a session token and return the associated account_id.
/// Returns AuthFailed if the token is invalid or expired.
pub fn verify_session(conn: &Connection, token: &str) -> Result<String, AppError> {
    let result = conn.query_row(
        "SELECT account_id FROM sessions WHERE token = ?1",
        [token],
        |row| row.get::<_, String>(0),
    );
    match result {
        Ok(account_id) => Ok(account_id),
        Err(rusqlite::Error::QueryReturnedNoRows) => Err(AppError::AuthFailed(
            "Invalid or expired session token".into(),
        )),
        Err(e) => Err(AppError::from(e)),
    }
}

/// Remove a session token (logout).
pub fn logout_session(conn: &Connection, token: &str) -> Result<(), AppError> {
    conn.execute("DELETE FROM sessions WHERE token = ?1", [token])?;
    Ok(())
}

/// Create a new local account. Returns an error if the username already exists.
pub fn create_account(
    conn: &Connection,
    username: &str,
    password: &str,
    email: &str,
    name: &str,
) -> Result<Account, AppError> {
    let username = username.trim();
    if username.is_empty() {
        return Err(AppError::AuthFailed("Username cannot be empty".into()));
    }
    if password.is_empty() {
        return Err(AppError::AuthFailed("Password cannot be empty".into()));
    }

    let id = Uuid::new_v4().to_string();
    let password_hash =
        hash(password, DEFAULT_COST).map_err(|e| AppError::AuthFailed(e.to_string()))?;

    let result = conn.execute(
        "INSERT INTO local_accounts (id, username, password_hash, email, name) VALUES (?1, ?2, ?3, ?4, ?5)",
        rusqlite::params![id, username, password_hash, email, name],
    );

    match result {
        Ok(_) => Ok(Account {
            id,
            username: username.to_string(),
        }),
        Err(e) => {
            // SQLite constraint violation on UNIQUE(username).
            if e.to_string().contains("UNIQUE") || e.to_string().contains("unique") {
                Err(AppError::Duplicate(format!(
                    "Username '{}' already exists",
                    username
                )))
            } else {
                Err(AppError::from(e))
            }
        }
    }
}

/// Authenticate a user by username and password.
/// Returns the account with a session token on success.
pub fn login(
    conn: &Connection,
    username: &str,
    password: &str,
) -> Result<AccountWithToken, AppError> {
    let username = username.trim();
    if username.is_empty() || password.is_empty() {
        return Err(AppError::AuthFailed(
            "Username and password are required".into(),
        ));
    }

    let result = conn.query_row(
        "SELECT id, username, password_hash FROM local_accounts WHERE username = ?1",
        [username],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        },
    );

    match result {
        Ok((id, uname, password_hash)) => {
            let valid = verify(password, &password_hash)
                .map_err(|e| AppError::AuthFailed(e.to_string()))?;
            if valid {
                let token = create_session(conn, &id)?;
                Ok(AccountWithToken {
                    id,
                    username: uname,
                    token,
                })
            } else {
                Err(AppError::AuthFailed("Incorrect password".into()))
            }
        }
        Err(rusqlite::Error::QueryReturnedNoRows) => {
            Err(AppError::NotFound(format!("User '{}' not found", username)))
        }
        Err(e) => Err(AppError::from(e)),
    }
}

/// List all local accounts on this device (summary only — no password hashes).
pub fn list_accounts(conn: &Connection) -> Result<Vec<AccountSummary>, AppError> {
    let mut stmt = conn.prepare("SELECT id, username FROM local_accounts ORDER BY username")?;
    let rows = stmt.query_map([], |row| {
        Ok(AccountSummary {
            id: row.get(0)?,
            username: row.get(1)?,
        })
    })?;

    let mut accounts = Vec::new();
    for row in rows {
        accounts.push(row?);
    }
    Ok(accounts)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::run_migrations;

    fn setup() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        run_migrations(&conn).unwrap();
        conn
    }

    #[test]
    fn test_create_account_success() {
        let conn = setup();
        let account =
            create_account(&conn, "alice", "password123", "alice@test.com", "Alice").unwrap();
        assert!(!account.id.is_empty());
        assert_eq!(account.username, "alice");
    }

    #[test]
    fn test_create_duplicate_username_fails() {
        let conn = setup();
        create_account(&conn, "alice", "pass1", "", "Alice").unwrap();
        let result = create_account(&conn, "alice", "pass2", "", "Alice2");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::Duplicate(_)));
    }

    #[test]
    fn test_create_empty_username_fails() {
        let conn = setup();
        let result = create_account(&conn, "", "password", "", "");
        assert!(result.is_err());
    }

    #[test]
    fn test_create_empty_password_fails() {
        let conn = setup();
        let result = create_account(&conn, "alice", "", "", "");
        assert!(result.is_err());
    }

    #[test]
    fn test_login_correct_password() {
        let conn = setup();
        create_account(&conn, "bob", "correcthorse", "", "Bob").unwrap();
        let result = login(&conn, "bob", "correcthorse").unwrap();
        assert_eq!(result.username, "bob");
        assert!(!result.token.is_empty());
        // Token should be verifiable.
        let account_id = verify_session(&conn, &result.token).unwrap();
        assert_eq!(account_id, result.id);
    }

    #[test]
    fn test_verify_session_invalid_token() {
        let conn = setup();
        let result = verify_session(&conn, "nonexistent-token");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::AuthFailed(_)));
    }

    #[test]
    fn test_login_logout_verify_sequence() {
        let conn = setup();
        create_account(&conn, "carol", "secret", "", "Carol").unwrap();
        let result = login(&conn, "carol", "secret").unwrap();

        // Token works
        assert!(verify_session(&conn, &result.token).is_ok());

        // After logout, token no longer works
        logout_session(&conn, &result.token).unwrap();
        let verify = verify_session(&conn, &result.token);
        assert!(verify.is_err());
        assert!(matches!(verify.unwrap_err(), AppError::AuthFailed(_)));
    }

    #[test]
    fn test_login_wrong_password() {
        let conn = setup();
        create_account(&conn, "bob", "correcthorse", "", "Bob").unwrap();
        let result = login(&conn, "bob", "wrongpassword");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::AuthFailed(_)));
    }

    #[test]
    fn test_login_nonexistent_user() {
        let conn = setup();
        let result = login(&conn, "ghost", "password");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::NotFound(_)));
    }

    #[test]
    fn test_login_empty_credentials() {
        let conn = setup();
        let result = login(&conn, "", "");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::AuthFailed(_)));
    }

    #[test]
    fn test_bcrypt_hash_not_plaintext() {
        let conn = setup();
        create_account(&conn, "carol", "secret123", "", "Carol").unwrap();
        // Verify the stored hash is not the plaintext password.
        let hash: String = conn
            .query_row(
                "SELECT password_hash FROM local_accounts WHERE username = 'carol'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert!(!hash.contains("secret123"));
        assert!(hash.starts_with("$2b$") || hash.starts_with("$2a$") || hash.starts_with("$2y$"));
    }

    #[test]
    fn test_list_accounts_empty() {
        let conn = setup();
        let accounts = list_accounts(&conn).unwrap();
        assert!(accounts.is_empty());
    }

    #[test]
    fn test_list_accounts_populated() {
        let conn = setup();
        create_account(&conn, "alice", "pass1", "", "Alice").unwrap();
        create_account(&conn, "bob", "pass2", "", "Bob").unwrap();
        let accounts = list_accounts(&conn).unwrap();
        assert_eq!(accounts.len(), 2);
        assert_eq!(accounts[0].username, "alice"); // alphabetical
        assert_eq!(accounts[1].username, "bob");
    }

    #[test]
    fn test_username_trimmed() {
        let conn = setup();
        let account = create_account(&conn, "  alice  ", "password", "", "Alice").unwrap();
        assert_eq!(account.username, "alice");
        // Login with untrimmed should also work.
        let logged = login(&conn, "  alice  ", "password").unwrap();
        assert_eq!(logged.username, "alice");
    }
}
