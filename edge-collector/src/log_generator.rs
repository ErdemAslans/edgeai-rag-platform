//! Log generator module for simulating edge sensor logs.
//!
//! This module provides functionality to generate realistic dummy sensor logs
//! for testing and development of the edge-to-cloud log streaming pipeline.

use chrono::{DateTime, Utc};
use rand::distributions::{Distribution, WeightedIndex};
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Log severity levels matching the Python API schema.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LogLevel {
    Trace,
    Debug,
    Info,
    Warn,
    Error,
    Fatal,
}

impl LogLevel {
    /// Get all possible log levels.
    pub fn all() -> &'static [LogLevel] {
        &[
            LogLevel::Trace,
            LogLevel::Debug,
            LogLevel::Info,
            LogLevel::Warn,
            LogLevel::Error,
            LogLevel::Fatal,
        ]
    }
}

impl std::fmt::Display for LogLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LogLevel::Trace => write!(f, "trace"),
            LogLevel::Debug => write!(f, "debug"),
            LogLevel::Info => write!(f, "info"),
            LogLevel::Warn => write!(f, "warn"),
            LogLevel::Error => write!(f, "error"),
            LogLevel::Fatal => write!(f, "fatal"),
        }
    }
}

/// A single log entry from an edge sensor.
///
/// This struct matches the `LogEntry` Pydantic schema in the Python API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    /// Optional client-generated log ID
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<Uuid>,

    /// Timestamp when the log was generated at edge
    pub timestamp: DateTime<Utc>,

    /// Identifier of the edge device or sensor
    pub source_id: String,

    /// Log severity level
    pub level: LogLevel,

    /// Log message content
    pub message: String,

    /// Additional structured metadata
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, serde_json::Value>>,
}

impl LogEntry {
    /// Create a new log entry with the given parameters.
    pub fn new(
        source_id: impl Into<String>,
        level: LogLevel,
        message: impl Into<String>,
    ) -> Self {
        Self {
            id: Some(Uuid::new_v4()),
            timestamp: Utc::now(),
            source_id: source_id.into(),
            level,
            message: message.into(),
            metadata: None,
        }
    }

    /// Add metadata to the log entry.
    pub fn with_metadata(mut self, metadata: HashMap<String, serde_json::Value>) -> Self {
        self.metadata = Some(metadata);
        self
    }
}

/// A batch of log entries to send to the API.
///
/// This struct matches the `LogBatchRequest` Pydantic schema in the Python API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogBatch {
    /// List of log entries to ingest
    pub logs: Vec<LogEntry>,

    /// Optional client-generated batch ID for idempotency
    #[serde(skip_serializing_if = "Option::is_none")]
    pub batch_id: Option<Uuid>,

    /// Identifier of the edge collector sending the batch
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
}

impl LogBatch {
    /// Create a new log batch from a vector of log entries.
    pub fn new(logs: Vec<LogEntry>) -> Self {
        Self {
            logs,
            batch_id: Some(Uuid::new_v4()),
            source: Some("edge-collector-rust".to_string()),
        }
    }

    /// Get the number of logs in the batch.
    pub fn len(&self) -> usize {
        self.logs.len()
    }

    /// Check if the batch is empty.
    pub fn is_empty(&self) -> bool {
        self.logs.is_empty()
    }
}

/// Sensor types for dummy log generation.
#[derive(Debug, Clone, Copy)]
pub enum SensorType {
    Temperature,
    Humidity,
    Pressure,
    Motion,
    Light,
    Vibration,
    AirQuality,
    Power,
}

impl SensorType {
    /// Get all sensor types.
    pub fn all() -> &'static [SensorType] {
        &[
            SensorType::Temperature,
            SensorType::Humidity,
            SensorType::Pressure,
            SensorType::Motion,
            SensorType::Light,
            SensorType::Vibration,
            SensorType::AirQuality,
            SensorType::Power,
        ]
    }

    /// Get the sensor type name as a string.
    pub fn name(&self) -> &'static str {
        match self {
            SensorType::Temperature => "temperature",
            SensorType::Humidity => "humidity",
            SensorType::Pressure => "pressure",
            SensorType::Motion => "motion",
            SensorType::Humidity => "humidity",
            SensorType::Light => "light",
            SensorType::Vibration => "vibration",
            SensorType::AirQuality => "air_quality",
            SensorType::Power => "power",
        }
    }

    /// Get the unit for this sensor type.
    pub fn unit(&self) -> &'static str {
        match self {
            SensorType::Temperature => "celsius",
            SensorType::Humidity => "percent",
            SensorType::Pressure => "hpa",
            SensorType::Motion => "detected",
            SensorType::Light => "lux",
            SensorType::Vibration => "g",
            SensorType::AirQuality => "aqi",
            SensorType::Power => "watts",
        }
    }
}

/// Configuration for the log generator.
#[derive(Debug, Clone)]
pub struct GeneratorConfig {
    /// Number of simulated sensors per type
    pub sensors_per_type: usize,

    /// Base log generation interval in milliseconds
    pub base_interval_ms: u64,

    /// Whether to include metadata in logs
    pub include_metadata: bool,

    /// Error rate (0.0 - 1.0) for generating error/warning logs
    pub error_rate: f64,
}

impl Default for GeneratorConfig {
    fn default() -> Self {
        Self {
            sensors_per_type: 3,
            base_interval_ms: 100,
            include_metadata: true,
            error_rate: 0.05, // 5% error rate
        }
    }
}

/// Log generator for simulating edge sensor data.
///
/// The generator creates realistic dummy sensor logs with weighted log levels
/// (mostly INFO, occasional WARN/ERROR) and sensor-specific metadata.
pub struct LogGenerator {
    config: GeneratorConfig,
    level_weights: WeightedIndex<u32>,
}

impl LogGenerator {
    /// Create a new log generator with the given configuration.
    pub fn new(config: GeneratorConfig) -> Self {
        // Weight log levels: mostly INFO, some DEBUG, occasional WARN/ERROR
        // Trace: 5%, Debug: 15%, Info: 60%, Warn: 12%, Error: 7%, Fatal: 1%
        let weights = vec![5, 15, 60, 12, 7, 1];
        let level_weights = WeightedIndex::new(&weights).expect("Invalid weights");

        Self {
            config,
            level_weights,
        }
    }

    /// Create a new log generator with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(GeneratorConfig::default())
    }

    /// Generate a single random log entry.
    pub fn generate(&self) -> LogEntry {
        let mut rng = rand::thread_rng();

        // Select random sensor type
        let sensor_types = SensorType::all();
        let sensor_type = sensor_types[rng.gen_range(0..sensor_types.len())];

        // Generate source ID based on sensor type and instance
        let sensor_instance = rng.gen_range(1..=self.config.sensors_per_type);
        let source_id = format!("edge-{}-{:03}", sensor_type.name(), sensor_instance);

        // Select log level using weighted distribution
        let level = LogLevel::all()[self.level_weights.sample(&mut rng)];

        // Generate message and metadata based on sensor type and level
        let (message, metadata) = self.generate_sensor_data(&mut rng, sensor_type, level);

        let mut entry = LogEntry::new(source_id, level, message);

        if self.config.include_metadata {
            entry = entry.with_metadata(metadata);
        }

        entry
    }

    /// Generate multiple random log entries.
    pub fn generate_batch(&self, count: usize) -> Vec<LogEntry> {
        (0..count).map(|_| self.generate()).collect()
    }

    /// Generate sensor-specific message and metadata.
    fn generate_sensor_data(
        &self,
        rng: &mut impl Rng,
        sensor_type: SensorType,
        level: LogLevel,
    ) -> (String, HashMap<String, serde_json::Value>) {
        let mut metadata = HashMap::new();

        // Add common metadata
        metadata.insert(
            "sensor_type".to_string(),
            serde_json::Value::String(sensor_type.name().to_string()),
        );
        metadata.insert(
            "unit".to_string(),
            serde_json::Value::String(sensor_type.unit().to_string()),
        );

        // Generate sensor-specific reading and message
        let (reading, message) = match sensor_type {
            SensorType::Temperature => {
                let temp = self.generate_temperature(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(temp).unwrap()),
                );
                (temp, self.format_temp_message(temp, level))
            }
            SensorType::Humidity => {
                let humidity = self.generate_humidity(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(humidity).unwrap()),
                );
                (humidity, self.format_humidity_message(humidity, level))
            }
            SensorType::Pressure => {
                let pressure = self.generate_pressure(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(pressure).unwrap()),
                );
                (pressure, self.format_pressure_message(pressure, level))
            }
            SensorType::Motion => {
                let detected = rng.gen_bool(0.3); // 30% motion detection rate
                metadata.insert(
                    "motion_detected".to_string(),
                    serde_json::Value::Bool(detected),
                );
                let confidence = rng.gen_range(70..=100);
                metadata.insert(
                    "confidence".to_string(),
                    serde_json::Value::Number(serde_json::Number::from(confidence)),
                );
                (
                    if detected { 1.0 } else { 0.0 },
                    self.format_motion_message(detected, confidence, level),
                )
            }
            SensorType::Light => {
                let lux = self.generate_light(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(lux).unwrap()),
                );
                (lux, self.format_light_message(lux, level))
            }
            SensorType::Vibration => {
                let vibration = self.generate_vibration(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(vibration).unwrap()),
                );
                let frequency = rng.gen_range(10.0..500.0);
                metadata.insert(
                    "frequency_hz".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(frequency).unwrap()),
                );
                (vibration, self.format_vibration_message(vibration, level))
            }
            SensorType::AirQuality => {
                let aqi = self.generate_air_quality(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from(aqi as i64)),
                );
                let pm25 = rng.gen_range(0.0..100.0);
                metadata.insert(
                    "pm25".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(pm25).unwrap()),
                );
                (aqi as f64, self.format_aqi_message(aqi, level))
            }
            SensorType::Power => {
                let power = self.generate_power(rng, level);
                metadata.insert(
                    "reading".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(power).unwrap()),
                );
                let voltage = rng.gen_range(118.0..122.0);
                metadata.insert(
                    "voltage".to_string(),
                    serde_json::Value::Number(serde_json::Number::from_f64(voltage).unwrap()),
                );
                (power, self.format_power_message(power, level))
            }
        };

        // Add timestamp and sequence number for tracing
        metadata.insert(
            "sequence".to_string(),
            serde_json::Value::Number(serde_json::Number::from(rng.gen_range(1..=999999))),
        );

        (message, metadata)
    }

    // Temperature generation (normal: 18-26C, warning: 26-35C or 10-18C, error: >35C or <10C)
    fn generate_temperature(&self, rng: &mut impl Rng, level: LogLevel) -> f64 {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(35.0..50.0)
                } else {
                    rng.gen_range(-10.0..10.0)
                }
            }
            LogLevel::Warn => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(26.0..35.0)
                } else {
                    rng.gen_range(10.0..18.0)
                }
            }
            _ => rng.gen_range(18.0..26.0),
        }
    }

    fn format_temp_message(&self, temp: f64, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("CRITICAL: Temperature reading {:.1}C is outside safe range", temp)
            }
            LogLevel::Warn => {
                format!("Temperature {:.1}C approaching threshold limits", temp)
            }
            LogLevel::Info => {
                format!("Temperature reading: {:.1}C", temp)
            }
            LogLevel::Debug => {
                format!("Sensor calibration check: {:.1}C within tolerance", temp)
            }
            LogLevel::Trace => {
                format!("Raw temperature ADC value converted to {:.1}C", temp)
            }
        }
    }

    // Humidity generation (normal: 30-70%, warning: 70-85% or 15-30%, error: >85% or <15%)
    fn generate_humidity(&self, rng: &mut impl Rng, level: LogLevel) -> f64 {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(85.0..100.0)
                } else {
                    rng.gen_range(0.0..15.0)
                }
            }
            LogLevel::Warn => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(70.0..85.0)
                } else {
                    rng.gen_range(15.0..30.0)
                }
            }
            _ => rng.gen_range(30.0..70.0),
        }
    }

    fn format_humidity_message(&self, humidity: f64, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("ALERT: Humidity {:.1}% outside operational limits", humidity)
            }
            LogLevel::Warn => {
                format!("Humidity {:.1}% nearing threshold", humidity)
            }
            _ => {
                format!("Humidity reading: {:.1}%", humidity)
            }
        }
    }

    // Pressure generation (normal: 1000-1025 hPa)
    fn generate_pressure(&self, rng: &mut impl Rng, level: LogLevel) -> f64 {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(1040.0..1060.0)
                } else {
                    rng.gen_range(950.0..980.0)
                }
            }
            LogLevel::Warn => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(1025.0..1040.0)
                } else {
                    rng.gen_range(980.0..1000.0)
                }
            }
            _ => rng.gen_range(1000.0..1025.0),
        }
    }

    fn format_pressure_message(&self, pressure: f64, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("CRITICAL: Barometric pressure {:.1} hPa is abnormal", pressure)
            }
            LogLevel::Warn => {
                format!("Pressure {:.1} hPa deviation detected", pressure)
            }
            _ => {
                format!("Pressure reading: {:.1} hPa", pressure)
            }
        }
    }

    fn format_motion_message(&self, detected: bool, confidence: u32, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                "Motion sensor communication failure".to_string()
            }
            LogLevel::Warn => {
                format!("Motion detection confidence low: {}%", confidence)
            }
            _ => {
                if detected {
                    format!("Motion detected with {}% confidence", confidence)
                } else {
                    "No motion detected".to_string()
                }
            }
        }
    }

    // Light level generation (normal: 300-700 lux)
    fn generate_light(&self, rng: &mut impl Rng, level: LogLevel) -> f64 {
        match level {
            LogLevel::Error | LogLevel::Fatal => rng.gen_range(0.0..10.0),
            LogLevel::Warn => {
                if rng.gen_bool(0.5) {
                    rng.gen_range(10.0..100.0)
                } else {
                    rng.gen_range(1000.0..2000.0)
                }
            }
            _ => rng.gen_range(300.0..700.0),
        }
    }

    fn format_light_message(&self, lux: f64, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("CRITICAL: Light sensor reading {:.0} lux indicates failure", lux)
            }
            LogLevel::Warn => {
                format!("Light level {:.0} lux outside normal range", lux)
            }
            _ => {
                format!("Light level: {:.0} lux", lux)
            }
        }
    }

    // Vibration generation (normal: 0.0-0.5g)
    fn generate_vibration(&self, rng: &mut impl Rng, level: LogLevel) -> f64 {
        match level {
            LogLevel::Error | LogLevel::Fatal => rng.gen_range(2.0..5.0),
            LogLevel::Warn => rng.gen_range(0.5..2.0),
            _ => rng.gen_range(0.0..0.5),
        }
    }

    fn format_vibration_message(&self, vibration: f64, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("CRITICAL: Excessive vibration {:.2}g detected", vibration)
            }
            LogLevel::Warn => {
                format!("Elevated vibration level: {:.2}g", vibration)
            }
            _ => {
                format!("Vibration reading: {:.3}g", vibration)
            }
        }
    }

    // Air Quality Index generation (normal: 0-50 Good)
    fn generate_air_quality(&self, rng: &mut impl Rng, level: LogLevel) -> u32 {
        match level {
            LogLevel::Error | LogLevel::Fatal => rng.gen_range(200..500), // Very Unhealthy to Hazardous
            LogLevel::Warn => rng.gen_range(100..200),                    // Unhealthy
            _ => rng.gen_range(0..50),                                    // Good
        }
    }

    fn format_aqi_message(&self, aqi: u32, level: LogLevel) -> String {
        let category = match aqi {
            0..=50 => "Good",
            51..=100 => "Moderate",
            101..=150 => "Unhealthy for Sensitive Groups",
            151..=200 => "Unhealthy",
            201..=300 => "Very Unhealthy",
            _ => "Hazardous",
        };
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("ALERT: Air quality index {} ({}) - take action", aqi, category)
            }
            LogLevel::Warn => {
                format!("Air quality degraded: AQI {} ({})", aqi, category)
            }
            _ => {
                format!("Air quality: AQI {} ({})", aqi, category)
            }
        }
    }

    // Power consumption generation (normal: 50-500W)
    fn generate_power(&self, rng: &mut impl Rng, level: LogLevel) -> f64 {
        match level {
            LogLevel::Error | LogLevel::Fatal => rng.gen_range(1000.0..2000.0),
            LogLevel::Warn => rng.gen_range(500.0..1000.0),
            _ => rng.gen_range(50.0..500.0),
        }
    }

    fn format_power_message(&self, power: f64, level: LogLevel) -> String {
        match level {
            LogLevel::Error | LogLevel::Fatal => {
                format!("CRITICAL: Power consumption {:.1}W exceeds limit", power)
            }
            LogLevel::Warn => {
                format!("High power consumption: {:.1}W", power)
            }
            _ => {
                format!("Power consumption: {:.1}W", power)
            }
        }
    }
}

impl Default for LogGenerator {
    fn default() -> Self {
        Self::with_defaults()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_level_serialization() {
        assert_eq!(
            serde_json::to_string(&LogLevel::Info).unwrap(),
            r#""info""#
        );
        assert_eq!(
            serde_json::to_string(&LogLevel::Error).unwrap(),
            r#""error""#
        );
    }

    #[test]
    fn test_log_level_deserialization() {
        let level: LogLevel = serde_json::from_str(r#""warn""#).unwrap();
        assert_eq!(level, LogLevel::Warn);
    }

    #[test]
    fn test_log_entry_creation() {
        let entry = LogEntry::new("test-sensor-001", LogLevel::Info, "Test message");

        assert!(entry.id.is_some());
        assert_eq!(entry.source_id, "test-sensor-001");
        assert_eq!(entry.level, LogLevel::Info);
        assert_eq!(entry.message, "Test message");
        assert!(entry.metadata.is_none());
    }

    #[test]
    fn test_log_entry_with_metadata() {
        let mut metadata = HashMap::new();
        metadata.insert(
            "reading".to_string(),
            serde_json::Value::Number(serde_json::Number::from_f64(25.5).unwrap()),
        );

        let entry = LogEntry::new("test-sensor-001", LogLevel::Info, "Test message")
            .with_metadata(metadata);

        assert!(entry.metadata.is_some());
        let meta = entry.metadata.as_ref().unwrap();
        assert_eq!(meta.get("reading").unwrap().as_f64().unwrap(), 25.5);
    }

    #[test]
    fn test_log_entry_serialization() {
        let entry = LogEntry::new("test-sensor-001", LogLevel::Info, "Test message");
        let json = serde_json::to_string(&entry).unwrap();

        assert!(json.contains(r#""source_id":"test-sensor-001""#));
        assert!(json.contains(r#""level":"info""#));
        assert!(json.contains(r#""message":"Test message""#));
    }

    #[test]
    fn test_log_batch_creation() {
        let entries = vec![
            LogEntry::new("sensor-001", LogLevel::Info, "Message 1"),
            LogEntry::new("sensor-002", LogLevel::Warn, "Message 2"),
        ];
        let batch = LogBatch::new(entries);

        assert_eq!(batch.len(), 2);
        assert!(!batch.is_empty());
        assert!(batch.batch_id.is_some());
        assert_eq!(batch.source.as_ref().unwrap(), "edge-collector-rust");
    }

    #[test]
    fn test_log_batch_serialization() {
        let entries = vec![LogEntry::new("sensor-001", LogLevel::Info, "Test")];
        let batch = LogBatch::new(entries);
        let json = serde_json::to_string(&batch).unwrap();

        assert!(json.contains(r#""logs":[{"#));
        assert!(json.contains(r#""batch_id""#));
        assert!(json.contains(r#""source":"edge-collector-rust""#));
    }

    #[test]
    fn test_generator_default_config() {
        let config = GeneratorConfig::default();

        assert_eq!(config.sensors_per_type, 3);
        assert_eq!(config.base_interval_ms, 100);
        assert!(config.include_metadata);
        assert!((config.error_rate - 0.05).abs() < f64::EPSILON);
    }

    #[test]
    fn test_generator_produces_valid_logs() {
        let generator = LogGenerator::with_defaults();
        let entry = generator.generate();

        assert!(entry.id.is_some());
        assert!(!entry.source_id.is_empty());
        assert!(!entry.message.is_empty());
        assert!(entry.metadata.is_some());
    }

    #[test]
    fn test_generator_batch_size() {
        let generator = LogGenerator::with_defaults();
        let batch = generator.generate_batch(50);

        assert_eq!(batch.len(), 50);
    }

    #[test]
    fn test_generator_source_id_format() {
        let generator = LogGenerator::with_defaults();
        let entry = generator.generate();

        // Source ID should start with "edge-"
        assert!(entry.source_id.starts_with("edge-"));

        // Source ID should end with a 3-digit number
        let parts: Vec<&str> = entry.source_id.split('-').collect();
        assert!(parts.len() >= 2);
        let last_part = parts.last().unwrap();
        assert!(last_part.len() == 3);
        assert!(last_part.chars().all(|c| c.is_ascii_digit()));
    }

    #[test]
    fn test_sensor_type_names() {
        assert_eq!(SensorType::Temperature.name(), "temperature");
        assert_eq!(SensorType::Humidity.name(), "humidity");
        assert_eq!(SensorType::Pressure.name(), "pressure");
        assert_eq!(SensorType::Motion.name(), "motion");
        assert_eq!(SensorType::Light.name(), "light");
        assert_eq!(SensorType::Vibration.name(), "vibration");
        assert_eq!(SensorType::AirQuality.name(), "air_quality");
        assert_eq!(SensorType::Power.name(), "power");
    }

    #[test]
    fn test_sensor_type_units() {
        assert_eq!(SensorType::Temperature.unit(), "celsius");
        assert_eq!(SensorType::Humidity.unit(), "percent");
        assert_eq!(SensorType::Pressure.unit(), "hpa");
        assert_eq!(SensorType::Light.unit(), "lux");
    }

    #[test]
    fn test_generated_metadata_contains_sensor_info() {
        let generator = LogGenerator::with_defaults();
        let entry = generator.generate();

        let metadata = entry.metadata.as_ref().unwrap();
        assert!(metadata.contains_key("sensor_type"));
        assert!(metadata.contains_key("unit"));
        assert!(metadata.contains_key("sequence"));
    }

    #[test]
    fn test_log_level_display() {
        assert_eq!(format!("{}", LogLevel::Info), "info");
        assert_eq!(format!("{}", LogLevel::Error), "error");
        assert_eq!(format!("{}", LogLevel::Warn), "warn");
    }
}
