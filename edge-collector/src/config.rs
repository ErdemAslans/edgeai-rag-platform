//! Configuration module for the Edge Collector service.
//!
//! This module provides environment-based configuration for the edge collector,
//! including API URL, batch size, and flush interval settings.

use std::env;
use std::time::Duration;

/// Default API URL for the Python FastAPI backend
const DEFAULT_API_URL: &str = "http://localhost:8000";

/// Default batch size (number of logs per batch)
const DEFAULT_BATCH_SIZE: usize = 100;

/// Default flush interval in seconds
const DEFAULT_FLUSH_INTERVAL_SECS: u64 = 5;

/// Maximum allowed batch size to prevent memory issues
const MAX_BATCH_SIZE: usize = 10_000;

/// Minimum flush interval to prevent overwhelming the API
const MIN_FLUSH_INTERVAL_SECS: u64 = 1;

/// Maximum flush interval to ensure reasonable data freshness
const MAX_FLUSH_INTERVAL_SECS: u64 = 300;

/// Configuration for the Edge Collector service.
///
/// All settings can be configured via environment variables:
/// - `EDGE_COLLECTOR_API_URL`: Python API URL (default: http://localhost:8000)
/// - `EDGE_COLLECTOR_BATCH_SIZE`: Logs per batch (default: 100)
/// - `EDGE_COLLECTOR_FLUSH_INTERVAL_SECS`: Seconds between flushes (default: 5)
#[derive(Debug, Clone)]
pub struct Config {
    /// Base URL for the Python FastAPI backend API
    pub api_url: String,

    /// Full URL for the log ingestion endpoint
    pub ingest_url: String,

    /// Number of logs to accumulate before sending a batch
    pub batch_size: usize,

    /// Duration to wait before flushing buffered logs, even if batch size not reached
    pub flush_interval: Duration,

    /// HTTP request timeout duration
    pub request_timeout: Duration,

    /// Maximum number of retry attempts for failed requests
    pub max_retries: u32,
}

/// Error type for configuration loading failures
#[derive(Debug)]
pub struct ConfigError {
    pub message: String,
    pub env_var: Option<String>,
}

impl std::fmt::Display for ConfigError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match &self.env_var {
            Some(var) => write!(f, "Configuration error for {}: {}", var, self.message),
            None => write!(f, "Configuration error: {}", self.message),
        }
    }
}

impl std::error::Error for ConfigError {}

impl Config {
    /// Load configuration from environment variables.
    ///
    /// Returns a new `Config` instance with values from environment variables,
    /// falling back to sensible defaults where appropriate.
    ///
    /// # Errors
    ///
    /// Returns `ConfigError` if:
    /// - `EDGE_COLLECTOR_BATCH_SIZE` is not a valid number or exceeds limits
    /// - `EDGE_COLLECTOR_FLUSH_INTERVAL_SECS` is not a valid number or exceeds limits
    ///
    /// # Examples
    ///
    /// ```no_run
    /// use edge_collector::config::Config;
    ///
    /// let config = Config::from_env().expect("Failed to load config");
    /// println!("API URL: {}", config.api_url);
    /// ```
    pub fn from_env() -> Result<Self, ConfigError> {
        // Load API URL
        let api_url = env::var("EDGE_COLLECTOR_API_URL")
            .unwrap_or_else(|_| DEFAULT_API_URL.to_string());

        // Validate and normalize API URL
        let api_url = api_url.trim_end_matches('/').to_string();

        // Construct full ingest endpoint URL
        let ingest_url = format!("{}/api/v1/ingest/logs", api_url);

        // Load and parse batch size
        let batch_size = Self::parse_batch_size()?;

        // Load and parse flush interval
        let flush_interval_secs = Self::parse_flush_interval()?;
        let flush_interval = Duration::from_secs(flush_interval_secs);

        // Load request timeout (optional, defaults to 30 seconds)
        let request_timeout_secs: u64 = env::var("EDGE_COLLECTOR_REQUEST_TIMEOUT_SECS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(30);
        let request_timeout = Duration::from_secs(request_timeout_secs);

        // Load max retries (optional, defaults to 3)
        let max_retries: u32 = env::var("EDGE_COLLECTOR_MAX_RETRIES")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(3);

        Ok(Self {
            api_url,
            ingest_url,
            batch_size,
            flush_interval,
            request_timeout,
            max_retries,
        })
    }

    /// Parse batch size from environment variable with validation.
    fn parse_batch_size() -> Result<usize, ConfigError> {
        let env_var = "EDGE_COLLECTOR_BATCH_SIZE";

        match env::var(env_var) {
            Ok(value) => {
                let batch_size: usize = value.parse().map_err(|_| ConfigError {
                    message: format!("'{}' is not a valid number", value),
                    env_var: Some(env_var.to_string()),
                })?;

                if batch_size == 0 {
                    return Err(ConfigError {
                        message: "batch size must be greater than 0".to_string(),
                        env_var: Some(env_var.to_string()),
                    });
                }

                if batch_size > MAX_BATCH_SIZE {
                    return Err(ConfigError {
                        message: format!(
                            "batch size {} exceeds maximum allowed ({})",
                            batch_size, MAX_BATCH_SIZE
                        ),
                        env_var: Some(env_var.to_string()),
                    });
                }

                Ok(batch_size)
            }
            Err(_) => Ok(DEFAULT_BATCH_SIZE),
        }
    }

    /// Parse flush interval from environment variable with validation.
    fn parse_flush_interval() -> Result<u64, ConfigError> {
        let env_var = "EDGE_COLLECTOR_FLUSH_INTERVAL_SECS";

        match env::var(env_var) {
            Ok(value) => {
                let interval: u64 = value.parse().map_err(|_| ConfigError {
                    message: format!("'{}' is not a valid number", value),
                    env_var: Some(env_var.to_string()),
                })?;

                if interval < MIN_FLUSH_INTERVAL_SECS {
                    return Err(ConfigError {
                        message: format!(
                            "flush interval {} is below minimum ({}s)",
                            interval, MIN_FLUSH_INTERVAL_SECS
                        ),
                        env_var: Some(env_var.to_string()),
                    });
                }

                if interval > MAX_FLUSH_INTERVAL_SECS {
                    return Err(ConfigError {
                        message: format!(
                            "flush interval {} exceeds maximum ({}s)",
                            interval, MAX_FLUSH_INTERVAL_SECS
                        ),
                        env_var: Some(env_var.to_string()),
                    });
                }

                Ok(interval)
            }
            Err(_) => Ok(DEFAULT_FLUSH_INTERVAL_SECS),
        }
    }
}

impl Default for Config {
    /// Create a default configuration using default values.
    ///
    /// This is useful for testing or when environment variables are not set.
    fn default() -> Self {
        Self {
            api_url: DEFAULT_API_URL.to_string(),
            ingest_url: format!("{}/api/v1/ingest/logs", DEFAULT_API_URL),
            batch_size: DEFAULT_BATCH_SIZE,
            flush_interval: Duration::from_secs(DEFAULT_FLUSH_INTERVAL_SECS),
            request_timeout: Duration::from_secs(30),
            max_retries: 3,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    // Helper to temporarily set environment variables for testing
    struct EnvGuard {
        key: String,
        original: Option<String>,
    }

    impl EnvGuard {
        fn set(key: &str, value: &str) -> Self {
            let original = env::var(key).ok();
            env::set_var(key, value);
            Self {
                key: key.to_string(),
                original,
            }
        }

        fn remove(key: &str) -> Self {
            let original = env::var(key).ok();
            env::remove_var(key);
            Self {
                key: key.to_string(),
                original,
            }
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            match &self.original {
                Some(val) => env::set_var(&self.key, val),
                None => env::remove_var(&self.key),
            }
        }
    }

    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.api_url, "http://localhost:8000");
        assert_eq!(config.batch_size, 100);
        assert_eq!(config.flush_interval, Duration::from_secs(5));
        assert_eq!(config.max_retries, 3);
    }

    #[test]
    fn test_config_from_env_with_defaults() {
        let _guard1 = EnvGuard::remove("EDGE_COLLECTOR_API_URL");
        let _guard2 = EnvGuard::remove("EDGE_COLLECTOR_BATCH_SIZE");
        let _guard3 = EnvGuard::remove("EDGE_COLLECTOR_FLUSH_INTERVAL_SECS");

        let config = Config::from_env().expect("Should load with defaults");
        assert_eq!(config.api_url, "http://localhost:8000");
        assert_eq!(config.batch_size, 100);
        assert_eq!(config.flush_interval, Duration::from_secs(5));
    }

    #[test]
    fn test_config_from_env_custom_values() {
        let _guard1 = EnvGuard::set("EDGE_COLLECTOR_API_URL", "http://custom:9000/");
        let _guard2 = EnvGuard::set("EDGE_COLLECTOR_BATCH_SIZE", "200");
        let _guard3 = EnvGuard::set("EDGE_COLLECTOR_FLUSH_INTERVAL_SECS", "10");

        let config = Config::from_env().expect("Should load custom values");
        assert_eq!(config.api_url, "http://custom:9000"); // Trailing slash removed
        assert_eq!(config.ingest_url, "http://custom:9000/api/v1/ingest/logs");
        assert_eq!(config.batch_size, 200);
        assert_eq!(config.flush_interval, Duration::from_secs(10));
    }

    #[test]
    fn test_invalid_batch_size() {
        let _guard = EnvGuard::set("EDGE_COLLECTOR_BATCH_SIZE", "not_a_number");

        let result = Config::from_env();
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.message.contains("not a valid number"));
    }

    #[test]
    fn test_zero_batch_size() {
        let _guard = EnvGuard::set("EDGE_COLLECTOR_BATCH_SIZE", "0");

        let result = Config::from_env();
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.message.contains("greater than 0"));
    }

    #[test]
    fn test_batch_size_exceeds_max() {
        let _guard = EnvGuard::set("EDGE_COLLECTOR_BATCH_SIZE", "99999");

        let result = Config::from_env();
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.message.contains("exceeds maximum"));
    }

    #[test]
    fn test_flush_interval_below_min() {
        let _guard = EnvGuard::set("EDGE_COLLECTOR_FLUSH_INTERVAL_SECS", "0");

        let result = Config::from_env();
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.message.contains("below minimum"));
    }

    #[test]
    fn test_flush_interval_exceeds_max() {
        let _guard = EnvGuard::set("EDGE_COLLECTOR_FLUSH_INTERVAL_SECS", "999");

        let result = Config::from_env();
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.message.contains("exceeds maximum"));
    }

    #[test]
    fn test_config_error_display() {
        let error = ConfigError {
            message: "test error".to_string(),
            env_var: Some("TEST_VAR".to_string()),
        };
        assert_eq!(
            format!("{}", error),
            "Configuration error for TEST_VAR: test error"
        );

        let error_no_var = ConfigError {
            message: "general error".to_string(),
            env_var: None,
        };
        assert_eq!(
            format!("{}", error_no_var),
            "Configuration error: general error"
        );
    }
}
