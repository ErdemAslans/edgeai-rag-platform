//! Edge Collector Library
//!
//! This library provides components for edge-to-cloud log streaming:
//!
//! - **config**: Environment-based configuration for the edge collector
//! - **log_generator**: Simulated sensor log generation for testing
//! - **buffer**: Async buffering with size and time-based flush triggers
//! - **client**: HTTP client with connection pooling and retry logic
//!
//! # Example
//!
//! ```no_run
//! use edge_collector::config::Config;
//! use edge_collector::log_generator::{LogGenerator, LogBatch};
//! use edge_collector::buffer::{LogBuffer, BufferConfig};
//! use edge_collector::client::LogClient;
//!
//! #[tokio::main]
//! async fn main() {
//!     // Load configuration from environment
//!     let config = Config::from_env().expect("Failed to load config");
//!
//!     // Create log generator
//!     let generator = LogGenerator::with_defaults();
//!
//!     // Create buffer for batching
//!     let buffer_config = BufferConfig::new(
//!         config.batch_size,
//!         config.flush_interval,
//!     );
//!     let (sender, mut buffer) = LogBuffer::new(buffer_config);
//!
//!     // Create HTTP client
//!     let client = LogClient::new(&config).expect("Failed to create client");
//!
//!     // Generate and send logs
//!     let logs = generator.generate_batch(100);
//!     let batch = LogBatch::new(logs);
//!     client.send_batch(batch).await.ok();
//! }
//! ```

// Module declarations
pub mod buffer;
pub mod client;
pub mod config;
pub mod log_generator;

// Re-export commonly used types at crate root for convenience
pub use buffer::{BufferConfig, BufferError, BufferSender, BufferStats, LogBuffer};
pub use client::{ClientError, ClientStats, IngestResponse, LogClient, TrackedLogClient};
pub use config::{Config, ConfigError};
pub use log_generator::{GeneratorConfig, LogBatch, LogEntry, LogGenerator, LogLevel, SensorType};
