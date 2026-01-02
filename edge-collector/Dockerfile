# EdgeAI Edge Collector - Multi-stage Dockerfile
# Stage 1: Builder (compile Rust binary)
# Stage 2: Runtime (minimal Alpine image)

# =============================================================================
# Stage 1: Build the Rust application
# =============================================================================
FROM rust:1.83-alpine AS builder

# Install build dependencies for Alpine
RUN apk add --no-cache \
    musl-dev \
    openssl-dev \
    openssl-libs-static \
    pkgconfig

WORKDIR /build

# Copy manifests
COPY Cargo.toml ./

# Create a dummy main.rs to cache dependencies
RUN mkdir src && \
    echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -rf src

# Copy actual source code
COPY src ./src

# Build the actual binary
# Touch main.rs to ensure it's rebuilt
RUN touch src/main.rs && \
    cargo build --release --locked

# Verify binary exists
RUN ls -lh /build/target/release/edge-collector

# =============================================================================
# Stage 2: Runtime environment
# =============================================================================
FROM alpine:3.19 AS runtime

# Install runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    libgcc

# Create non-root user for security
RUN addgroup -g 1000 edgecollector && \
    adduser -D -u 1000 -G edgecollector edgecollector

# Set working directory
WORKDIR /app

# Copy the compiled binary from builder
COPY --from=builder /build/target/release/edge-collector /usr/local/bin/edge-collector

# Ensure binary is executable
RUN chmod +x /usr/local/bin/edge-collector

# Switch to non-root user
USER edgecollector

# Environment variables with defaults
ENV EDGE_COLLECTOR_API_URL=http://localhost:8000 \
    EDGE_COLLECTOR_BATCH_SIZE=100 \
    EDGE_COLLECTOR_FLUSH_INTERVAL_SECS=5 \
    EDGE_COLLECTOR_REQUEST_TIMEOUT_SECS=30 \
    EDGE_COLLECTOR_MAX_RETRIES=3 \
    RUST_LOG=info

# Health check (checks if process is running)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD pgrep -x edge-collector || exit 1

# Run the edge collector
ENTRYPOINT ["/usr/local/bin/edge-collector"]