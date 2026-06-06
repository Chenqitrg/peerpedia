// Shared error type for all IPC commands.
// Serializes to { "code": "...", "message": "..." } for the frontend.

use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct AppErrorPayload {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone)]
pub enum AppError {
    NotFound(String),
    Duplicate(String),
    AuthFailed(String),
    DatabaseError(String),
    IoError(String),
}

impl AppError {
    /// Return a structured payload suitable for IPC serialization.
    pub fn to_payload(&self) -> AppErrorPayload {
        match self {
            AppError::NotFound(msg) => AppErrorPayload {
                code: "NOT_FOUND".into(),
                message: msg.clone(),
            },
            AppError::Duplicate(msg) => AppErrorPayload {
                code: "DUPLICATE".into(),
                message: msg.clone(),
            },
            AppError::AuthFailed(msg) => AppErrorPayload {
                code: "AUTH_FAILED".into(),
                message: msg.clone(),
            },
            AppError::DatabaseError(msg) => AppErrorPayload {
                code: "DATABASE_ERROR".into(),
                message: msg.clone(),
            },
            AppError::IoError(msg) => AppErrorPayload {
                code: "IO_ERROR".into(),
                message: msg.clone(),
            },
        }
    }
}

impl std::fmt::Display for AppError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AppError::NotFound(msg) => write!(f, "Not found: {}", msg),
            AppError::Duplicate(msg) => write!(f, "Duplicate: {}", msg),
            AppError::AuthFailed(msg) => write!(f, "Auth failed: {}", msg),
            AppError::DatabaseError(msg) => write!(f, "Database error: {}", msg),
            AppError::IoError(msg) => write!(f, "IO error: {}", msg),
        }
    }
}

impl std::error::Error for AppError {}

impl From<rusqlite::Error> for AppError {
    fn from(e: rusqlite::Error) -> Self {
        AppError::DatabaseError(e.to_string())
    }
}

impl From<std::io::Error> for AppError {
    fn from(e: std::io::Error) -> Self {
        AppError::IoError(e.to_string())
    }
}

// Serialize as the structured payload for Tauri IPC.
impl Serialize for AppError {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        self.to_payload().serialize(serializer)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_not_found_payload() {
        let err = AppError::NotFound("draft xyz".into());
        let payload = err.to_payload();
        assert_eq!(payload.code, "NOT_FOUND");
        assert!(payload.message.contains("draft xyz"));
    }

    #[test]
    fn test_duplicate_payload() {
        let err = AppError::Duplicate("username alice".into());
        let payload = err.to_payload();
        assert_eq!(payload.code, "DUPLICATE");
        assert!(payload.message.contains("alice"));
    }

    #[test]
    fn test_auth_failed_payload() {
        let err = AppError::AuthFailed("wrong password".into());
        let payload = err.to_payload();
        assert_eq!(payload.code, "AUTH_FAILED");
    }

    #[test]
    fn test_database_error_payload() {
        let err = AppError::DatabaseError("disk full".into());
        let payload = err.to_payload();
        assert_eq!(payload.code, "DATABASE_ERROR");
    }

    #[test]
    fn test_io_error_payload() {
        let err = AppError::IoError("permission denied".into());
        let payload = err.to_payload();
        assert_eq!(payload.code, "IO_ERROR");
    }

    #[test]
    fn test_display_formatting() {
        let err = AppError::NotFound("article abc".into());
        assert_eq!(err.to_string(), "Not found: article abc");
    }

    #[test]
    fn test_from_rusqlite_error() {
        // rusqlite errors can be constructed from a string
        let app_err: AppError = rusqlite::Error::InvalidParameterName("test".into()).into();
        assert!(matches!(app_err, AppError::DatabaseError(_)));
    }

    #[test]
    fn test_from_io_error() {
        let io_err = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
        let app_err: AppError = io_err.into();
        assert!(matches!(app_err, AppError::IoError(_)));
    }

    #[test]
    fn test_serialize_to_json() {
        let err = AppError::NotFound("draft xyz".into());
        let json = serde_json::to_string(&err).unwrap();
        assert!(json.contains("NOT_FOUND"));
        assert!(json.contains("draft xyz"));
    }
}
