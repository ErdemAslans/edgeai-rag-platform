//! HTTP client module for sending log batches to the cloud API.
//!
//! This module provides an async HTTP client with connection pooling,
//! retry logic with exponential backoff, and proper error handling.

use std::time::Duration;

use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use tracing::{debug, error, info, warn};

use crate::config::Config;
use crate::log_generator::LogBatch;

/// Default base delay for exponential backoff (in milliseconds).
const DEFAULT_BASE_DELAY_MS: u64 = 500;

/// Maximum delay between retries (in milliseconds).
const MAX_RETRY_DELAY_MS: u64 = 30_000;

/// Response from the log ingestion API.
#[derive(Debug, Clone, Deserialize)]
pub struct IngestResponse {
    /// Status message from the API
    pub status: String,

    /// Number of logs accepted
    #[serde(default)]
    pub accepted: u64,

    /// Number of logs rejected (if any)
    #[serde(default)]
    pub rejected: u64,

    /// Optional batch ID assigned by the server
    #[serde(default)]
    pub batch_id: Option<String>,

    /// Optional error message
    #[serde(default)]
    pub error: Option<String>,
}

/// Errors that can occur during HTTP client operations.
#[derive(Debug)]
pub enum ClientError {
    /// HTTP request failed
    Request(reqwest::Error),

    /// Server returned an error status code
    Status {
        code: StatusCode,
        message: String,
    },

    /// Failed to parse response body
    Parse(String),

    /// All retry attempts exhausted
    RetriesExhausted {
        attempts: u32,
        last_error: String,
    },

    /// Request timeout
    Timeout,

    /// Client configuration error
    Config(String),
}

impl std::fmt::Display for ClientError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ClientError::Request(e) => write!(f, "HTTP request failed: {}", e),
            ClientError::Status { code, message } => {
                write!(f, "Server error ({}): {}", code, message)
            }
            ClientError::Parse(e) => write!(f, "Failed to parse response: {}", e),
            ClientError::RetriesExhausted {
                attempts,
                last_error,
            } => {
                write!(
                    f,
                    "All {} retry attempts exhausted. Last error: {}",
                    attempts, last_error
                )
            }
            ClientError::Timeout => write!(f, "Request timed out"),
            ClientError::Config(e) => write!(f, "Client configuration error: {}", e),
        }
    }
}

impl std::error::Error for ClientError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            ClientError::Request(e) => Some(e),
            _ => None,
        }
    }
}

impl From<reqwest::Error> for ClientError {
    fn from(err: reqwest::Error) -> Self {
        if err.is_timeout() {
            ClientError::Timeout
        } else {
            ClientError::Request(err)
        }
    }
}

/// Statistics about client operations.
#[derive(Debug, Clone, Default)]
pub struct ClientStats {
    /// Total number of batches sent successfully
    pub batches_sent: u64,

    /// Total number of logs sent successfully
    pub logs_sent: u64,

    /// Total number of failed send attempts
    pub failed_attempts: u64,

    /// Total number of retries performed
    pub retries: u64,

    /// Total number of batches that failed after all retries
    pub batches_failed: u64,
}

/// HTTP client for sending log batches to the cloud API.
///
/// The client uses connection pooling (via reqwest's internal pool),
/// implements retry logic with exponential backoff, and respects
/// configured timeouts.
///
/// # Example
///
/// ```no_run
/// use edge_collector::client::LogClient;
/// use edge_collector::config::Config;
/// use edge_collector::log_generator::{LogGenerator, LogBatch};
///
/// #[tokio::main]
/// async fn main() {
///     let config = Config::default();
///     let client = LogClient::new(&config).expect("Failed to create client");
///
///     let generator = LogGenerator::with_defaults();
///     let logs = generator.generate_batch(100);
///     let batch = LogBatch::new(logs);
///
///     match client.send_batch(batch).await {
///         Ok(response) => println!("Sent {} logs", response.accepted),
///         Err(e) => eprintln!("Failed to send: {}", e),
///     }
/// }
/// ```
pub struct LogClient {
    /// The underlying HTTP client (reused for connection pooling)
    client: Client,

    /// URL for the log ingestion endpoint
    ingest_url: String,

    /// Maximum number of retry attempts
    max_retries: u32,

    /// Request timeout duration
    timeout: Duration,

    /// Client operation statistics
    stats: std::sync::atomic::AtomicU64,
}

impl LogClient {
    /// Create a new log client with the given configuration.
    ///
    /// # Arguments
    ///
    /// * `config` - Configuration containing API URL, timeouts, and retry settings
    ///
    /// # Errors
    ///
    /// Returns `ClientError::Config` if the HTTP client cannot be built.
    pub fn new(config: &Config) -> Result<Self, ClientError> {
        let client = Client::builder()
            .timeout(config.request_timeout)
            .pool_max_idle_per_host(10)
            .pool_idle_timeout(Duration::from_secs(90))
            .build()
            .map_err(|e| ClientError::Config(e.to_string()))?;

        Ok(Self {
            client,
            ingest_url: config.ingest_url.clone(),
            max_retries: config.max_retries,
            timeout: config.request_timeout,
            stats: std::sync::atomic::AtomicU64::new(0),
        })
    }

    /// Create a new log client with custom settings.
    ///
    /// This is useful for testing or when you need more control over the client.
    pub fn with_settings(
        ingest_url: impl Into<String>,
        timeout: Duration,
        max_retries: u32,
    ) -> Result<Self, ClientError> {
        let client = Client::builder()
            .timeout(timeout)
            .pool_max_idle_per_host(10)
            .pool_idle_timeout(Duration::from_secs(90))
            .build()
            .map_err(|e| ClientError::Config(e.to_string()))?;

        Ok(Self {
            client,
            ingest_url: ingest_url.into(),
            max_retries,
            timeout,
            stats: std::sync::atomic::AtomicU64::new(0),
        })
    }

    /// Send a batch of logs to the cloud API.
    ///
    /// This method implements retry logic with exponential backoff.
    /// It will retry up to `max_retries` times on transient failures.
    ///
    /// # Arguments
    ///
    /// * `batch` - The log batch to send
    ///
    /// # Returns
    ///
    /// Returns `IngestResponse` on success, or `ClientError` on failure.
    ///
    /// # Retryable Errors
    ///
    /// The following errors trigger retries:
    /// - Network connection errors
    /// - Request timeouts
    /// - Server errors (5xx status codes)
    ///
    /// # Non-Retryable Errors
    ///
    /// The following errors do NOT trigger retries:
    /// - Client errors (4xx status codes, except 429)
    /// - Parse errors
    pub async fn send_batch(&self, batch: LogBatch) -> Result<IngestResponse, ClientError> {
        let batch_size = batch.len();
        let batch_id = batch.batch_id.map(|id| id.to_string());

        debug!(
            batch_size = batch_size,
            batch_id = ?batch_id,
            url = %self.ingest_url,
            "Sending log batch"
        );

        let mut last_error: Option<ClientError> = None;
        let mut attempt = 0;

        while attempt <= self.max_retries {
            if attempt > 0 {
                let delay = self.calculate_backoff_delay(attempt);
                warn!(
                    attempt = attempt,
                    max_retries = self.max_retries,
                    delay_ms = delay.as_millis(),
                    "Retrying after failure"
                );
                tokio::time::sleep(delay).await;
            }

            match self.send_request(&batch).await {
                Ok(response) => {
                    info!(
                        batch_size = batch_size,
                        accepted = response.accepted,
                        rejected = response.rejected,
                        "Successfully sent log batch"
                    );
                    return Ok(response);
                }
                Err(e) => {
                    let is_retryable = self.is_retryable_error(&e);

                    if is_retryable && attempt < self.max_retries {
                        warn!(
                            error = %e,
                            attempt = attempt + 1,
                            max_retries = self.max_retries,
                            "Request failed, will retry"
                        );
                        last_error = Some(e);
                        attempt += 1;
                    } else {
                        error!(
                            error = %e,
                            attempts = attempt + 1,
                            retryable = is_retryable,
                            "Request failed permanently"
                        );
                        return Err(e);
                    }
                }
            }
        }

        // All retries exhausted
        let last_error_msg = last_error
            .map(|e| e.to_string())
            .unwrap_or_else(|| "Unknown error".to_string());

        Err(ClientError::RetriesExhausted {
            attempts: self.max_retries + 1,
            last_error: last_error_msg,
        })
    }

    /// Send a single HTTP request without retry logic.
    async fn send_request(&self, batch: &LogBatch) -> Result<IngestResponse, ClientError> {
        let response = self
            .client
            .post(&self.ingest_url)
            .timeout(self.timeout)
            .json(batch)
            .send()
            .await?;

        let status = response.status();

        if status.is_success() {
            // Parse successful response
            let body = response.text().await?;
            serde_json::from_str(&body).map_err(|e| ClientError::Parse(e.to_string()))
        } else {
            // Handle error response
            let message = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());

            Err(ClientError::Status {
                code: status,
                message,
            })
        }
    }

    /// Calculate the backoff delay for a given retry attempt.
    ///
    /// Uses exponential backoff with jitter:
    /// delay = min(base_delay * 2^attempt + jitter, max_delay)
    fn calculate_backoff_delay(&self, attempt: u32) -> Duration {
        let base_delay = DEFAULT_BASE_DELAY_MS;

        // Calculate exponential delay: base * 2^attempt
        let exponential_delay = base_delay.saturating_mul(1 << attempt.min(10));

        // Add jitter (up to 25% of the delay)
        let jitter = rand::random::<u64>() % (exponential_delay / 4 + 1);

        // Cap at maximum delay
        let total_delay = exponential_delay.saturating_add(jitter).min(MAX_RETRY_DELAY_MS);

        Duration::from_millis(total_delay)
    }

    /// Check if an error is retryable.
    ///
    /// Retryable errors include:
    /// - Connection errors
    /// - Timeouts
    /// - Server errors (5xx)
    /// - Rate limiting (429)
    fn is_retryable_error(&self, error: &ClientError) -> bool {
        match error {
            ClientError::Request(e) => {
                e.is_connect() || e.is_timeout() || e.is_request()
            }
            ClientError::Timeout => true,
            ClientError::Status { code, .. } => {
                code.is_server_error() || *code == StatusCode::TOO_MANY_REQUESTS
            }
            // Non-retryable errors
            ClientError::Parse(_) => false,
            ClientError::RetriesExhausted { .. } => false,
            ClientError::Config(_) => false,
        }
    }

    /// Get the configured ingest URL.
    pub fn ingest_url(&self) -> &str {
        &self.ingest_url
    }

    /// Get the maximum number of retries.
    pub fn max_retries(&self) -> u32 {
        self.max_retries
    }

    /// Get the request timeout duration.
    pub fn timeout(&self) -> Duration {
        self.timeout
    }
}

/// A client wrapper that tracks statistics and provides a higher-level API.
///
/// This wrapper maintains statistics about sent batches and provides
/// additional convenience methods.
pub struct TrackedLogClient {
    /// The underlying log client
    inner: LogClient,

    /// Statistics about client operations
    stats: std::sync::RwLock<ClientStats>,
}

impl TrackedLogClient {
    /// Create a new tracked log client.
    pub fn new(config: &Config) -> Result<Self, ClientError> {
        Ok(Self {
            inner: LogClient::new(config)?,
            stats: std::sync::RwLock::new(ClientStats::default()),
        })
    }

    /// Send a batch of logs and update statistics.
    pub async fn send_batch(&self, batch: LogBatch) -> Result<IngestResponse, ClientError> {
        let batch_size = batch.len() as u64;

        match self.inner.send_batch(batch).await {
            Ok(response) => {
                if let Ok(mut stats) = self.stats.write() {
                    stats.batches_sent += 1;
                    stats.logs_sent += response.accepted;
                }
                Ok(response)
            }
            Err(e) => {
                if let Ok(mut stats) = self.stats.write() {
                    stats.batches_failed += 1;
                    if let ClientError::RetriesExhausted { attempts, .. } = &e {
                        stats.retries += (*attempts as u64).saturating_sub(1);
                    }
                }
                Err(e)
            }
        }
    }

    /// Get current client statistics.
    pub fn stats(&self) -> ClientStats {
        self.stats.read().map(|s| s.clone()).unwrap_or_default()
    }

    /// Get a reference to the inner client.
    pub fn inner(&self) -> &LogClient {
        &self.inner
    }
}

/// Send a batch of logs using a provided client (convenience function).
///
/// This is a standalone function for use with the buffer_task callback pattern.
///
/// # Arguments
///
/// * `client` - Reference to a LogClient
/// * `batch` - The log batch to send
///
/// # Example
///
/// ```no_run
/// use edge_collector::client::{LogClient, send_batch};
/// use edge_collector::config::Config;
/// use edge_collector::log_generator::{LogGenerator, LogBatch};
/// use std::sync::Arc;
///
/// #[tokio::main]
/// async fn main() {
///     let config = Config::default();
///     let client = Arc::new(LogClient::new(&config).unwrap());
///
///     let generator = LogGenerator::with_defaults();
///     let logs = generator.generate_batch(100);
///     let batch = LogBatch::new(logs);
///
///     send_batch(&client, batch).await.ok();
/// }
/// ```
pub async fn send_batch(
    client: &LogClient,
    batch: LogBatch,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    client.send_batch(batch).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::log_generator::{LogEntry, LogLevel};

    fn create_test_batch(size: usize) -> LogBatch {
        let entries: Vec<LogEntry> = (0..size)
            .map(|i| LogEntry::new(format!("test-{}", i), LogLevel::Info, "Test message"))
            .collect();
        LogBatch::new(entries)
    }

    #[test]
    fn test_client_error_display() {
        let err = ClientError::Timeout;
        assert_eq!(format!("{}", err), "Request timed out");

        let err = ClientError::Status {
            code: StatusCode::BAD_REQUEST,
            message: "Invalid JSON".to_string(),
        };
        assert!(format!("{}", err).contains("400"));
        assert!(format!("{}", err).contains("Invalid JSON"));

        let err = ClientError::RetriesExhausted {
            attempts: 3,
            last_error: "Connection refused".to_string(),
        };
        assert!(format!("{}", err).contains("3"));
        assert!(format!("{}", err).contains("Connection refused"));
    }

    #[test]
    fn test_client_creation() {
        let config = Config::default();
        let client = LogClient::new(&config);
        assert!(client.is_ok());

        let client = client.unwrap();
        assert_eq!(client.ingest_url(), "http://localhost:8000/api/v1/ingest/logs");
        assert_eq!(client.max_retries(), 3);
        assert_eq!(client.timeout(), Duration::from_secs(30));
    }

    #[test]
    fn test_client_with_settings() {
        let client = LogClient::with_settings(
            "http://example.com/api/logs",
            Duration::from_secs(60),
            5,
        );
        assert!(client.is_ok());

        let client = client.unwrap();
        assert_eq!(client.ingest_url(), "http://example.com/api/logs");
        assert_eq!(client.max_retries(), 5);
        assert_eq!(client.timeout(), Duration::from_secs(60));
    }

    #[test]
    fn test_backoff_delay_increases() {
        let config = Config::default();
        let client = LogClient::new(&config).unwrap();

        let delay1 = client.calculate_backoff_delay(0);
        let delay2 = client.calculate_backoff_delay(1);
        let delay3 = client.calculate_backoff_delay(2);

        // Delays should generally increase (allowing for jitter)
        // Base delay is 500ms, so delay1 should be around 500ms
        assert!(delay1.as_millis() >= 375); // 500 - 25% jitter
        assert!(delay1.as_millis() <= 625); // 500 + 25% jitter

        // delay2 should be around 1000ms (500 * 2)
        assert!(delay2.as_millis() >= 750);
        assert!(delay2.as_millis() <= 1250);

        // delay3 should be around 2000ms (500 * 4)
        assert!(delay3.as_millis() >= 1500);
        assert!(delay3.as_millis() <= 2500);
    }

    #[test]
    fn test_backoff_delay_caps_at_max() {
        let config = Config::default();
        let client = LogClient::new(&config).unwrap();

        // Very high attempt number should cap at MAX_RETRY_DELAY_MS
        let delay = client.calculate_backoff_delay(20);
        assert!(delay.as_millis() <= MAX_RETRY_DELAY_MS as u128);
    }

    #[test]
    fn test_retryable_error_detection() {
        let config = Config::default();
        let client = LogClient::new(&config).unwrap();

        // Timeout should be retryable
        assert!(client.is_retryable_error(&ClientError::Timeout));

        // Parse errors should not be retryable
        assert!(!client.is_retryable_error(&ClientError::Parse("invalid json".to_string())));

        // 5xx errors should be retryable
        assert!(client.is_retryable_error(&ClientError::Status {
            code: StatusCode::INTERNAL_SERVER_ERROR,
            message: "Server error".to_string(),
        }));

        // 429 Too Many Requests should be retryable
        assert!(client.is_retryable_error(&ClientError::Status {
            code: StatusCode::TOO_MANY_REQUESTS,
            message: "Rate limited".to_string(),
        }));

        // 4xx errors (except 429) should not be retryable
        assert!(!client.is_retryable_error(&ClientError::Status {
            code: StatusCode::BAD_REQUEST,
            message: "Bad request".to_string(),
        }));

        // Config errors should not be retryable
        assert!(!client.is_retryable_error(&ClientError::Config("config error".to_string())));
    }

    #[test]
    fn test_ingest_response_deserialization() {
        let json = r#"{
            "status": "accepted",
            "accepted": 100,
            "rejected": 0,
            "batch_id": "abc-123"
        }"#;

        let response: IngestResponse = serde_json::from_str(json).unwrap();
        assert_eq!(response.status, "accepted");
        assert_eq!(response.accepted, 100);
        assert_eq!(response.rejected, 0);
        assert_eq!(response.batch_id, Some("abc-123".to_string()));
        assert!(response.error.is_none());
    }

    #[test]
    fn test_ingest_response_partial_deserialization() {
        // Response with only required fields
        let json = r#"{"status": "accepted"}"#;

        let response: IngestResponse = serde_json::from_str(json).unwrap();
        assert_eq!(response.status, "accepted");
        assert_eq!(response.accepted, 0); // default
        assert_eq!(response.rejected, 0); // default
        assert!(response.batch_id.is_none()); // default
    }

    #[test]
    fn test_create_test_batch() {
        let batch = create_test_batch(10);
        assert_eq!(batch.len(), 10);
        assert!(batch.batch_id.is_some());
    }

    #[test]
    fn test_client_stats_default() {
        let stats = ClientStats::default();
        assert_eq!(stats.batches_sent, 0);
        assert_eq!(stats.logs_sent, 0);
        assert_eq!(stats.failed_attempts, 0);
        assert_eq!(stats.retries, 0);
        assert_eq!(stats.batches_failed, 0);
    }

    #[tokio::test]
    async fn test_tracked_client_creation() {
        let config = Config::default();
        let client = TrackedLogClient::new(&config);
        assert!(client.is_ok());

        let client = client.unwrap();
        let stats = client.stats();
        assert_eq!(stats.batches_sent, 0);
        assert_eq!(stats.logs_sent, 0);
    }
}
