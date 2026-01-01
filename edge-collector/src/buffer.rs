//! Buffer module for accumulating and batching log entries.
//!
//! This module provides async buffering with size-based and time-based flush triggers
//! using tokio mpsc channels and select! for concurrent event handling.

use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::interval;
use tracing::{debug, info, warn};

use crate::log_generator::{LogBatch, LogEntry};

/// Maximum buffer capacity to prevent memory issues.
/// If buffer exceeds this, oldest logs will be dropped.
const MAX_BUFFER_CAPACITY: usize = 10_000;

/// Default channel capacity for the mpsc sender/receiver.
const DEFAULT_CHANNEL_CAPACITY: usize = 1_000;

/// Configuration for the log buffer.
#[derive(Debug, Clone)]
pub struct BufferConfig {
    /// Number of logs to accumulate before triggering a flush
    pub batch_size: usize,

    /// Duration to wait before flushing, even if batch size not reached
    pub flush_interval: Duration,

    /// Maximum number of logs to hold in the buffer
    pub max_capacity: usize,

    /// Capacity of the mpsc channel
    pub channel_capacity: usize,
}

impl Default for BufferConfig {
    fn default() -> Self {
        Self {
            batch_size: 100,
            flush_interval: Duration::from_secs(5),
            max_capacity: MAX_BUFFER_CAPACITY,
            channel_capacity: DEFAULT_CHANNEL_CAPACITY,
        }
    }
}

impl BufferConfig {
    /// Create a new buffer config with the specified batch size and flush interval.
    pub fn new(batch_size: usize, flush_interval: Duration) -> Self {
        Self {
            batch_size,
            flush_interval,
            max_capacity: MAX_BUFFER_CAPACITY,
            channel_capacity: DEFAULT_CHANNEL_CAPACITY,
        }
    }
}

/// Statistics about buffer operations.
#[derive(Debug, Clone, Default)]
pub struct BufferStats {
    /// Total number of logs received
    pub logs_received: u64,

    /// Total number of logs flushed (sent in batches)
    pub logs_flushed: u64,

    /// Total number of logs dropped due to buffer overflow
    pub logs_dropped: u64,

    /// Number of flush operations triggered by size threshold
    pub size_flushes: u64,

    /// Number of flush operations triggered by time interval
    pub time_flushes: u64,
}

/// Result of a flush operation.
#[derive(Debug)]
pub enum FlushResult {
    /// Flush was successful with the given batch
    Success(LogBatch),

    /// Buffer was empty, nothing to flush
    Empty,
}

/// A sender handle for submitting log entries to the buffer.
///
/// This can be cloned and shared across multiple producer tasks.
#[derive(Clone)]
pub struct BufferSender {
    tx: mpsc::Sender<LogEntry>,
}

impl BufferSender {
    /// Send a log entry to the buffer.
    ///
    /// This is an async operation that will wait if the channel is full.
    /// Returns an error if the buffer has been closed.
    pub async fn send(&self, entry: LogEntry) -> Result<(), BufferError> {
        self.tx.send(entry).await.map_err(|_| BufferError::Closed)
    }

    /// Try to send a log entry without waiting.
    ///
    /// Returns an error if the channel is full or closed.
    pub fn try_send(&self, entry: LogEntry) -> Result<(), BufferError> {
        self.tx.try_send(entry).map_err(|e| match e {
            mpsc::error::TrySendError::Full(_) => BufferError::Full,
            mpsc::error::TrySendError::Closed(_) => BufferError::Closed,
        })
    }
}

/// Errors that can occur during buffer operations.
#[derive(Debug)]
pub enum BufferError {
    /// The buffer channel is full (for non-blocking sends)
    Full,

    /// The buffer has been closed and is no longer accepting entries
    Closed,
}

impl std::fmt::Display for BufferError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            BufferError::Full => write!(f, "Buffer channel is full"),
            BufferError::Closed => write!(f, "Buffer has been closed"),
        }
    }
}

impl std::error::Error for BufferError {}

/// Async log buffer with size and time-based flushing.
///
/// The buffer accumulates log entries and produces batches when either:
/// - The batch size threshold is reached (size-based flush)
/// - The flush interval elapses (time-based flush)
///
/// # Example
///
/// ```no_run
/// use edge_collector::buffer::{LogBuffer, BufferConfig};
/// use edge_collector::log_generator::LogGenerator;
/// use std::time::Duration;
///
/// #[tokio::main]
/// async fn main() {
///     let config = BufferConfig::new(100, Duration::from_secs(5));
///     let (sender, mut buffer) = LogBuffer::new(config);
///
///     // Spawn a producer task
///     let sender_clone = sender.clone();
///     tokio::spawn(async move {
///         let generator = LogGenerator::with_defaults();
///         loop {
///             let entry = generator.generate();
///             sender_clone.send(entry).await.ok();
///             tokio::time::sleep(Duration::from_millis(10)).await;
///         }
///     });
///
///     // Process batches
///     loop {
///         if let Some(batch) = buffer.next_batch().await {
///             // Send batch to API
///         }
///     }
/// }
/// ```
pub struct LogBuffer {
    /// Receiver for incoming log entries
    rx: mpsc::Receiver<LogEntry>,

    /// Internal buffer for accumulating logs
    buffer: Vec<LogEntry>,

    /// Configuration for the buffer
    config: BufferConfig,

    /// Statistics about buffer operations
    stats: BufferStats,
}

impl LogBuffer {
    /// Create a new log buffer with the given configuration.
    ///
    /// Returns a tuple of (BufferSender, LogBuffer).
    /// The sender can be cloned and shared with producer tasks.
    pub fn new(config: BufferConfig) -> (BufferSender, Self) {
        let (tx, rx) = mpsc::channel(config.channel_capacity);

        let buffer = Self {
            rx,
            buffer: Vec::with_capacity(config.batch_size),
            config,
            stats: BufferStats::default(),
        };

        let sender = BufferSender { tx };

        (sender, buffer)
    }

    /// Create a new log buffer with default configuration.
    pub fn with_defaults() -> (BufferSender, Self) {
        Self::new(BufferConfig::default())
    }

    /// Wait for the next batch of logs to be ready.
    ///
    /// This method uses `tokio::select!` to handle both:
    /// - Incoming log entries from the channel
    /// - Timer-based flush triggers
    ///
    /// Returns `None` if the channel is closed and the buffer is empty.
    pub async fn next_batch(&mut self) -> Option<LogBatch> {
        let mut ticker = interval(self.config.flush_interval);
        // Skip the first immediate tick
        ticker.tick().await;

        loop {
            tokio::select! {
                // Handle incoming log entries
                maybe_entry = self.rx.recv() => {
                    match maybe_entry {
                        Some(entry) => {
                            self.add_entry(entry);

                            // Check if we've reached batch size
                            if self.buffer.len() >= self.config.batch_size {
                                self.stats.size_flushes += 1;
                                debug!(
                                    batch_size = self.buffer.len(),
                                    "Flushing buffer: batch size threshold reached"
                                );
                                return Some(self.create_batch());
                            }
                        }
                        None => {
                            // Channel closed, flush remaining buffer
                            if !self.buffer.is_empty() {
                                info!(
                                    remaining = self.buffer.len(),
                                    "Channel closed, flushing remaining logs"
                                );
                                return Some(self.create_batch());
                            }
                            return None;
                        }
                    }
                }

                // Handle time-based flush
                _ = ticker.tick() => {
                    if !self.buffer.is_empty() {
                        self.stats.time_flushes += 1;
                        debug!(
                            batch_size = self.buffer.len(),
                            interval_secs = self.config.flush_interval.as_secs(),
                            "Flushing buffer: time interval elapsed"
                        );
                        return Some(self.create_batch());
                    }
                }
            }
        }
    }

    /// Add a log entry to the buffer, handling overflow if necessary.
    fn add_entry(&mut self, entry: LogEntry) {
        self.stats.logs_received += 1;

        // Check for buffer overflow
        if self.buffer.len() >= self.config.max_capacity {
            // Drop oldest entries to make room
            let drop_count = self.buffer.len() / 10; // Drop 10% to avoid frequent drops
            let drop_count = drop_count.max(1);

            warn!(
                buffer_size = self.buffer.len(),
                drop_count = drop_count,
                max_capacity = self.config.max_capacity,
                "Buffer overflow: dropping oldest logs"
            );

            self.buffer.drain(0..drop_count);
            self.stats.logs_dropped += drop_count as u64;
        }

        self.buffer.push(entry);
    }

    /// Create a batch from the current buffer contents and clear the buffer.
    fn create_batch(&mut self) -> LogBatch {
        let logs = std::mem::take(&mut self.buffer);
        self.stats.logs_flushed += logs.len() as u64;

        // Re-allocate with capacity for efficiency
        self.buffer = Vec::with_capacity(self.config.batch_size);

        LogBatch::new(logs)
    }

    /// Get the current number of logs in the buffer.
    pub fn len(&self) -> usize {
        self.buffer.len()
    }

    /// Check if the buffer is empty.
    pub fn is_empty(&self) -> bool {
        self.buffer.is_empty()
    }

    /// Get current buffer statistics.
    pub fn stats(&self) -> &BufferStats {
        &self.stats
    }

    /// Get the buffer configuration.
    pub fn config(&self) -> &BufferConfig {
        &self.config
    }

    /// Manually flush the buffer regardless of thresholds.
    ///
    /// Returns the batch if there were any logs, or None if the buffer was empty.
    pub fn flush(&mut self) -> Option<LogBatch> {
        if self.buffer.is_empty() {
            None
        } else {
            debug!(
                batch_size = self.buffer.len(),
                "Manual buffer flush"
            );
            Some(self.create_batch())
        }
    }
}

/// A standalone buffer task that can be spawned as a tokio task.
///
/// This task receives logs from a channel, buffers them, and calls
/// the provided flush callback when batches are ready.
///
/// # Arguments
///
/// * `rx` - Receiver for incoming log entries
/// * `batch_size` - Number of logs to accumulate before flushing
/// * `flush_interval` - Duration to wait before flushing even if batch size not reached
/// * `on_flush` - Async callback function to handle flushed batches
///
/// # Example
///
/// ```no_run
/// use edge_collector::buffer::{buffer_task, BufferConfig};
/// use edge_collector::log_generator::LogBatch;
/// use tokio::sync::mpsc;
///
/// #[tokio::main]
/// async fn main() {
///     let config = BufferConfig::default();
///     let (tx, rx) = mpsc::channel(1000);
///
///     // Spawn the buffer task
///     tokio::spawn(async move {
///         buffer_task(
///             rx,
///             config.batch_size,
///             config.flush_interval,
///             |batch: LogBatch| async move {
///                 println!("Flushing {} logs", batch.len());
///                 Ok(())
///             },
///         ).await;
///     });
/// }
/// ```
pub async fn buffer_task<F, Fut>(
    mut rx: mpsc::Receiver<LogEntry>,
    batch_size: usize,
    flush_interval: Duration,
    on_flush: F,
) where
    F: Fn(LogBatch) -> Fut,
    Fut: std::future::Future<Output = Result<(), Box<dyn std::error::Error + Send + Sync>>>,
{
    let mut buffer: Vec<LogEntry> = Vec::with_capacity(batch_size);
    let mut ticker = interval(flush_interval);
    let mut logs_dropped: u64 = 0;

    // Skip the first immediate tick
    ticker.tick().await;

    loop {
        tokio::select! {
            Some(log) = rx.recv() => {
                // Handle buffer overflow
                if buffer.len() >= MAX_BUFFER_CAPACITY {
                    let drop_count = buffer.len() / 10;
                    let drop_count = drop_count.max(1);
                    warn!(
                        buffer_size = buffer.len(),
                        drop_count = drop_count,
                        "Buffer overflow: dropping oldest logs"
                    );
                    buffer.drain(0..drop_count);
                    logs_dropped += drop_count as u64;
                }

                buffer.push(log);

                // Flush if batch size reached
                if buffer.len() >= batch_size {
                    debug!(batch_size = buffer.len(), "Size-based flush triggered");
                    let logs = std::mem::take(&mut buffer);
                    buffer = Vec::with_capacity(batch_size);
                    let batch = LogBatch::new(logs);

                    if let Err(e) = on_flush(batch).await {
                        warn!(error = %e, "Failed to flush batch");
                    }
                }
            }

            _ = ticker.tick() => {
                // Time-based flush if buffer not empty
                if !buffer.is_empty() {
                    debug!(batch_size = buffer.len(), "Time-based flush triggered");
                    let logs = std::mem::take(&mut buffer);
                    buffer = Vec::with_capacity(batch_size);
                    let batch = LogBatch::new(logs);

                    if let Err(e) = on_flush(batch).await {
                        warn!(error = %e, "Failed to flush batch");
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::log_generator::{LogEntry, LogLevel};
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;
    use tokio::time::timeout;

    fn create_test_entry() -> LogEntry {
        LogEntry::new("test-source", LogLevel::Info, "Test message")
    }

    #[tokio::test]
    async fn test_buffer_config_default() {
        let config = BufferConfig::default();
        assert_eq!(config.batch_size, 100);
        assert_eq!(config.flush_interval, Duration::from_secs(5));
        assert_eq!(config.max_capacity, MAX_BUFFER_CAPACITY);
    }

    #[tokio::test]
    async fn test_buffer_config_new() {
        let config = BufferConfig::new(50, Duration::from_secs(10));
        assert_eq!(config.batch_size, 50);
        assert_eq!(config.flush_interval, Duration::from_secs(10));
    }

    #[tokio::test]
    async fn test_buffer_creation() {
        let config = BufferConfig::new(10, Duration::from_secs(1));
        let (sender, buffer) = LogBuffer::new(config);

        assert!(buffer.is_empty());
        assert_eq!(buffer.len(), 0);

        // Sender should be able to send
        let entry = create_test_entry();
        sender.send(entry).await.expect("Send should succeed");
    }

    #[tokio::test]
    async fn test_buffer_size_based_flush() {
        let batch_size = 5;
        let config = BufferConfig::new(batch_size, Duration::from_secs(60)); // Long interval
        let (sender, mut buffer) = LogBuffer::new(config);

        // Send exactly batch_size entries
        for _ in 0..batch_size {
            sender.send(create_test_entry()).await.unwrap();
        }

        // Should get a batch due to size threshold
        let result = timeout(Duration::from_millis(100), buffer.next_batch()).await;
        let batch = result.expect("Should complete quickly").expect("Should get batch");

        assert_eq!(batch.len(), batch_size);
        assert!(buffer.is_empty());
        assert_eq!(buffer.stats().size_flushes, 1);
    }

    #[tokio::test]
    async fn test_buffer_time_based_flush() {
        let config = BufferConfig::new(100, Duration::from_millis(50)); // Short interval
        let (sender, mut buffer) = LogBuffer::new(config);

        // Send fewer than batch_size entries
        sender.send(create_test_entry()).await.unwrap();
        sender.send(create_test_entry()).await.unwrap();

        // Should get a batch due to time threshold
        let result = timeout(Duration::from_millis(200), buffer.next_batch()).await;
        let batch = result.expect("Should complete").expect("Should get batch");

        assert_eq!(batch.len(), 2);
        assert!(buffer.is_empty());
        assert_eq!(buffer.stats().time_flushes, 1);
    }

    #[tokio::test]
    async fn test_buffer_channel_close() {
        let config = BufferConfig::new(100, Duration::from_secs(60));
        let (sender, mut buffer) = LogBuffer::new(config);

        // Send some entries
        sender.send(create_test_entry()).await.unwrap();
        sender.send(create_test_entry()).await.unwrap();

        // Drop sender to close channel
        drop(sender);

        // Should get remaining entries
        let result = timeout(Duration::from_millis(100), buffer.next_batch()).await;
        let batch = result.expect("Should complete").expect("Should get batch");

        assert_eq!(batch.len(), 2);

        // Next call should return None
        let result = timeout(Duration::from_millis(100), buffer.next_batch()).await;
        let batch = result.expect("Should complete");
        assert!(batch.is_none());
    }

    #[tokio::test]
    async fn test_buffer_manual_flush() {
        let config = BufferConfig::new(100, Duration::from_secs(60));
        let (sender, mut buffer) = LogBuffer::new(config);

        // Send entries via the internal mechanism (simulating received entries)
        // We need to receive them first
        sender.send(create_test_entry()).await.unwrap();
        drop(sender); // Close channel to allow next_batch to complete

        // Get the batch (channel closed)
        let batch = buffer.next_batch().await;
        assert!(batch.is_some());

        // After getting batch, buffer should be empty
        assert!(buffer.flush().is_none());
    }

    #[tokio::test]
    async fn test_sender_try_send() {
        let config = BufferConfig {
            channel_capacity: 2,
            ..BufferConfig::default()
        };
        let (sender, _buffer) = LogBuffer::new(config);

        // First sends should succeed
        sender.try_send(create_test_entry()).unwrap();
        sender.try_send(create_test_entry()).unwrap();

        // Channel is now full
        let result = sender.try_send(create_test_entry());
        assert!(matches!(result, Err(BufferError::Full)));
    }

    #[tokio::test]
    async fn test_sender_closed_error() {
        let config = BufferConfig::default();
        let (sender, buffer) = LogBuffer::new(config);

        // Drop buffer (which owns the receiver)
        drop(buffer);

        // Try to send should fail
        let result = sender.send(create_test_entry()).await;
        assert!(matches!(result, Err(BufferError::Closed)));
    }

    #[tokio::test]
    async fn test_buffer_stats() {
        let config = BufferConfig::new(3, Duration::from_secs(60));
        let (sender, mut buffer) = LogBuffer::new(config);

        // Send entries
        for _ in 0..6 {
            sender.send(create_test_entry()).await.unwrap();
        }
        drop(sender);

        // Get first batch (size-based)
        buffer.next_batch().await.unwrap();
        assert_eq!(buffer.stats().logs_received, 3);
        assert_eq!(buffer.stats().logs_flushed, 3);

        // Get second batch (size-based)
        buffer.next_batch().await.unwrap();
        assert_eq!(buffer.stats().logs_received, 6);
        assert_eq!(buffer.stats().logs_flushed, 6);
        assert_eq!(buffer.stats().size_flushes, 2);
    }

    #[tokio::test]
    async fn test_buffer_error_display() {
        assert_eq!(format!("{}", BufferError::Full), "Buffer channel is full");
        assert_eq!(
            format!("{}", BufferError::Closed),
            "Buffer has been closed"
        );
    }

    #[tokio::test]
    async fn test_buffer_task_size_flush() {
        let (tx, rx) = mpsc::channel::<LogEntry>(100);
        let flush_count = Arc::new(AtomicUsize::new(0));
        let flush_count_clone = flush_count.clone();

        // Spawn buffer task
        let handle = tokio::spawn(async move {
            buffer_task(
                rx,
                3,
                Duration::from_secs(60),
                |batch| {
                    let count = flush_count_clone.clone();
                    async move {
                        count.fetch_add(batch.len(), Ordering::SeqCst);
                        Ok(())
                    }
                },
            )
            .await;
        });

        // Send entries
        for _ in 0..3 {
            tx.send(create_test_entry()).await.unwrap();
        }

        // Wait for flush to process
        tokio::time::sleep(Duration::from_millis(50)).await;

        // Should have flushed
        assert_eq!(flush_count.load(Ordering::SeqCst), 3);

        // Cleanup
        drop(tx);
        handle.abort();
    }

    #[tokio::test]
    async fn test_buffer_task_time_flush() {
        let (tx, rx) = mpsc::channel::<LogEntry>(100);
        let flush_count = Arc::new(AtomicUsize::new(0));
        let flush_count_clone = flush_count.clone();

        // Spawn buffer task with short interval
        let handle = tokio::spawn(async move {
            buffer_task(
                rx,
                100, // High batch size
                Duration::from_millis(50),
                |batch| {
                    let count = flush_count_clone.clone();
                    async move {
                        count.fetch_add(batch.len(), Ordering::SeqCst);
                        Ok(())
                    }
                },
            )
            .await;
        });

        // Send fewer entries than batch size
        tx.send(create_test_entry()).await.unwrap();
        tx.send(create_test_entry()).await.unwrap();

        // Wait for time-based flush
        tokio::time::sleep(Duration::from_millis(100)).await;

        // Should have flushed due to time
        assert_eq!(flush_count.load(Ordering::SeqCst), 2);

        // Cleanup
        drop(tx);
        handle.abort();
    }
}
