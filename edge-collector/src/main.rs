//! Edge Collector - Log streaming service for edge-to-cloud pipeline
//!
//! This service generates simulated sensor logs, buffers them efficiently,
//! and batch-transmits to the Python FastAPI cloud backend.
//!
//! ## Features
//!
//! - Async log generation using tokio runtime
//! - Size-based and time-based buffer flushing
//! - HTTP batch transmission with retry logic
//! - Graceful shutdown on SIGINT/SIGTERM
//!
//! ## Configuration
//!
//! Configuration is loaded from environment variables:
//!
//! - `EDGE_COLLECTOR_API_URL`: Python API URL (default: http://localhost:8000)
//! - `EDGE_COLLECTOR_BATCH_SIZE`: Logs per batch (default: 100)
//! - `EDGE_COLLECTOR_FLUSH_INTERVAL_SECS`: Seconds between flushes (default: 5)
//! - `EDGE_COLLECTOR_REQUEST_TIMEOUT_SECS`: HTTP request timeout (default: 30)
//! - `EDGE_COLLECTOR_MAX_RETRIES`: Max retry attempts (default: 3)
//! - `RUST_LOG`: Logging level filter (default: info)

use std::sync::Arc;
use std::time::Duration;

use tokio::sync::mpsc;
use tokio::time::interval;
use tracing::{error, info, warn};
use tracing_subscriber::EnvFilter;

use edge_collector::buffer::buffer_task;
use edge_collector::client::{send_batch, LogClient};
use edge_collector::config::Config;
use edge_collector::log_generator::LogGenerator;

/// Default log generation interval in milliseconds
const DEFAULT_GENERATION_INTERVAL_MS: u64 = 50;

/// Channel capacity for the log buffer
const CHANNEL_CAPACITY: usize = 1000;

#[tokio::main]
async fn main() {
    // Initialize tracing subscriber with environment filter
    init_tracing();

    info!("Starting Edge Collector service...");

    // Load configuration from environment
    let config = match Config::from_env() {
        Ok(config) => {
            info!(
                api_url = %config.api_url,
                batch_size = config.batch_size,
                flush_interval_secs = config.flush_interval.as_secs(),
                max_retries = config.max_retries,
                "Configuration loaded"
            );
            config
        }
        Err(e) => {
            error!(error = %e, "Failed to load configuration");
            std::process::exit(1);
        }
    };

    // Create HTTP client with connection pooling
    let client = match LogClient::new(&config) {
        Ok(client) => {
            info!(
                ingest_url = %client.ingest_url(),
                "HTTP client initialized"
            );
            Arc::new(client)
        }
        Err(e) => {
            error!(error = %e, "Failed to create HTTP client");
            std::process::exit(1);
        }
    };

    // Create channel for log entries
    let (tx, rx) = mpsc::channel(CHANNEL_CAPACITY);

    // Create log generator
    let generator = LogGenerator::with_defaults();
    info!("Log generator initialized");

    // Clone client for buffer task
    let client_clone = client.clone();

    // Spawn buffer task - handles batching and sending logs
    let buffer_handle = tokio::spawn(async move {
        info!("Buffer task started");
        buffer_task(
            rx,
            config.batch_size,
            config.flush_interval,
            move |batch| {
                let client = client_clone.clone();
                async move {
                    send_batch(&client, batch).await
                }
            },
        )
        .await;
        info!("Buffer task completed");
    });

    // Spawn generator task - generates logs at regular intervals
    let tx_clone = tx.clone();
    let generator_handle = tokio::spawn(async move {
        info!("Generator task started");
        run_generator(generator, tx_clone).await;
        info!("Generator task completed");
    });

    // Wait for shutdown signal
    info!("Edge Collector running. Press Ctrl+C to stop.");
    match tokio::signal::ctrl_c().await {
        Ok(()) => {
            info!("Shutdown signal received, stopping...");
        }
        Err(e) => {
            error!(error = %e, "Failed to listen for shutdown signal");
        }
    }

    // Graceful shutdown
    info!("Initiating graceful shutdown...");

    // Drop the sender to signal the buffer task to flush remaining logs
    drop(tx);

    // Wait for generator to complete (it will stop when tx is dropped)
    generator_handle.abort();

    // Wait for buffer to flush remaining logs (with timeout)
    let shutdown_timeout = Duration::from_secs(10);
    match tokio::time::timeout(shutdown_timeout, buffer_handle).await {
        Ok(Ok(())) => {
            info!("Buffer task shut down gracefully");
        }
        Ok(Err(e)) => {
            warn!(error = %e, "Buffer task panicked during shutdown");
        }
        Err(_) => {
            warn!("Buffer task shutdown timed out after {:?}", shutdown_timeout);
        }
    }

    info!("Edge Collector stopped");
}

/// Initialize the tracing subscriber with environment-based filtering.
fn init_tracing() {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info"));

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(true)
        .with_thread_ids(false)
        .with_file(false)
        .with_line_number(false)
        .compact()
        .init();
}

/// Run the log generator task, producing logs at regular intervals.
///
/// This task generates simulated sensor logs and sends them to the buffer
/// channel. It runs until the channel is closed.
async fn run_generator(generator: LogGenerator, tx: mpsc::Sender<edge_collector::LogEntry>) {
    let mut ticker = interval(Duration::from_millis(DEFAULT_GENERATION_INTERVAL_MS));
    let mut logs_generated: u64 = 0;
    let mut last_report_time = std::time::Instant::now();
    let report_interval = Duration::from_secs(30);

    loop {
        ticker.tick().await;

        // Generate a new log entry
        let entry = generator.generate();

        // Send to buffer channel
        match tx.send(entry).await {
            Ok(()) => {
                logs_generated += 1;

                // Periodic progress report
                if last_report_time.elapsed() >= report_interval {
                    info!(
                        logs_generated = logs_generated,
                        rate = format!("{:.1}/s", logs_generated as f64 / last_report_time.elapsed().as_secs_f64()),
                        "Generator progress"
                    );
                    logs_generated = 0;
                    last_report_time = std::time::Instant::now();
                }
            }
            Err(_) => {
                // Channel closed, stop generating
                info!("Channel closed, generator stopping");
                break;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_generation_interval() {
        assert!(DEFAULT_GENERATION_INTERVAL_MS > 0);
        assert!(DEFAULT_GENERATION_INTERVAL_MS <= 1000);
    }

    #[test]
    fn test_channel_capacity() {
        assert!(CHANNEL_CAPACITY >= 100);
        assert!(CHANNEL_CAPACITY <= 10000);
    }
}
