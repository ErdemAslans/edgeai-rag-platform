# MPSC Channels - Log Buffering Pattern

Bu döküman, [[rust-giris|Edge Collector]]'da kullanılan MPSC (Multi-Producer Single-Consumer) channel pattern'ini derinlemesine açıklıyor. [[tokio-runtime|Tokio]]'nun async channel'ları ile log girişlerini nasıl topladığımızı ve batch'lediğimizi öğreneceksin.

#rust #mpsc #channels #buffer #edge-collector

---

## MPSC Nedir?

MPSC = Multi-Producer, Single-Consumer

```
┌───────────────┐
│   Producer 1  │──┐
└───────────────┘  │
                   │    ┌─────────────────┐    ┌──────────────┐
┌───────────────┐  ├───▶│  MPSC Channel   │───▶│   Consumer   │
│   Producer 2  │──┤    │   (Bounded)     │    │   (Buffer)   │
└───────────────┘  │    └─────────────────┘    └──────────────┘
                   │
┌───────────────┐  │
│   Producer N  │──┘
└───────────────┘
```

**Analoji:** Postane kutusu gibi düşün. Birden fazla kişi (producer) mektup atabilir, ama tek bir postacı (consumer) kutuyu boşaltır.

---

## Neden MPSC Channel?

### MPSC - Neden Bu?

**Bu nedir?** Thread-safe, async message passing mekanizması.

**Neden burada kullanıldı?**
- Log generator ile buffer task'ı ayırmak için
- Producer ve consumer farklı hızlarda çalışabilsin diye
- Backpressure mekanizması için

**Olmasaydı ne olurdu?**
- Shared mutable state için mutex gerekir → deadlock riski
- Generator her log için buffer'ı bekler → throughput düşer
- Producer çok hızlıysa consumer'ı ezer → veri kaybı

**Alternatifler:**

| Yöntem | Avantaj | Dezavantaj |
|--------|---------|------------|
| Mutex + Vec | Basit | Contention, blocking |
| RwLock | Çoklu okuyucu | Yine blocking |
| MPSC Channel | Non-blocking, backpressure | Biraz overhead |
| Crossbeam Channel | Daha hızlı | Sync API, async değil |

**Bağlantılar:** [[buffer-rs-analiz]], [[tokio-runtime]]

---

## Tokio MPSC Channel Temelleri

### Channel Oluşturma

[[buffer-rs-analiz|buffer.rs]]'den:

```rust
use tokio::sync::mpsc;

// Bounded channel - capacity ile backpressure
let (tx, rx) = mpsc::channel::<LogEntry>(1000);
```

### Sender (Producer) Tarafı

```rust
// async send - channel doluysa bekler
tx.send(entry).await?;

// try_send - beklemeden hemen sonuç
match tx.try_send(entry) {
    Ok(()) => { /* başarılı */ }
    Err(TrySendError::Full(_)) => { /* channel dolu */ }
    Err(TrySendError::Closed(_)) => { /* channel kapandı */ }
}
```

### Receiver (Consumer) Tarafı

```rust
// recv - sonraki mesajı bekle
while let Some(entry) = rx.recv().await {
    process(entry);
}
// None dönerse channel kapanmış demek
```

---

## Edge Collector'da MPSC Kullanımı

### Mimari Genel Bakış

```
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  LogGenerator   │          │   MPSC Channel  │          │   LogBuffer     │
│                 │          │                 │          │                 │
│  generate()     │   send   │   capacity:     │   recv   │  accumulate     │
│      │          │─────────▶│     1000        │─────────▶│      │          │
│      ▼          │          │                 │          │      ▼          │
│  LogEntry       │          │  [entry, ...]   │          │  Vec<LogEntry>  │
└─────────────────┘          └─────────────────┘          └─────────────────┘
                                                                  │
                                                                  ▼
                                                          ┌─────────────────┐
                                                          │   HTTP Client   │
                                                          │   (batch send)  │
                                                          └─────────────────┘
```

### BufferSender Wrapper

[[buffer-rs-analiz|buffer.rs]]'de sender'ı saran yapı:

```rust
/// A sender handle for submitting log entries to the buffer.
///
/// This can be cloned and shared across multiple producer tasks.
#[derive(Clone)]
pub struct BufferSender {
    tx: mpsc::Sender<LogEntry>,
}

impl BufferSender {
    /// Send a log entry to the buffer.
    pub async fn send(&self, entry: LogEntry) -> Result<(), BufferError> {
        self.tx.send(entry).await.map_err(|_| BufferError::Closed)
    }

    /// Try to send a log entry without waiting.
    pub fn try_send(&self, entry: LogEntry) -> Result<(), BufferError> {
        self.tx.try_send(entry).map_err(|e| match e {
            mpsc::error::TrySendError::Full(_) => BufferError::Full,
            mpsc::error::TrySendError::Closed(_) => BufferError::Closed,
        })
    }
}
```

### Neden Wrapper?

1. **Hata türlerini özelleştirme** - `mpsc` hatalarını `BufferError`'a dönüştürme
2. **API basitleştirme** - Kullanıcıdan `mpsc` detaylarını gizleme
3. **Genişletilebilirlik** - Gelecekte metrics, logging eklenebilir

---

## Channel Kapasitesi Stratejileri

### Bounded vs Unbounded

| Tür | Kullanım | Risk |
|-----|----------|------|
| `mpsc::channel(N)` | Bounded, backpressure var | Producer bekleyebilir |
| `mpsc::unbounded_channel()` | Unbounded, sınırsız | Memory tükenebilir |

**Projede:** Bounded (1000) tercih edildi çünkü:
- Memory kullanımını sınırlar
- Backpressure ile producer'ı yavaşlatır
- DoS saldırılarına karşı koruma

### Kapasite Seçimi

```rust
/// Default channel capacity for the mpsc sender/receiver.
const DEFAULT_CHANNEL_CAPACITY: usize = 1_000;

pub struct BufferConfig {
    /// Capacity of the mpsc channel
    pub channel_capacity: usize,
    // ...
}
```

**Kapasite hesaplama formülü:**

```
Kapasite = (Producer Rate × Flush Interval) × Safety Factor

Örnek:
- Producer: 100 log/saniye
- Flush interval: 5 saniye
- Safety factor: 2x

Kapasite = (100 × 5) × 2 = 1000
```

---

## Select! ile Multi-Event Handling

[[tokio-runtime|Tokio]]'nun `select!` macro'su ile birden fazla event'i aynı anda bekliyoruz:

```rust
loop {
    tokio::select! {
        // Event 1: Channel'dan yeni log geldi
        maybe_entry = self.rx.recv() => {
            match maybe_entry {
                Some(entry) => {
                    self.add_entry(entry);

                    // Batch size doldu mu?
                    if self.buffer.len() >= self.config.batch_size {
                        self.stats.size_flushes += 1;
                        return Some(self.create_batch());
                    }
                }
                None => {
                    // Channel kapandı, kalan log'ları flush et
                    if !self.buffer.is_empty() {
                        return Some(self.create_batch());
                    }
                    return None;
                }
            }
        }

        // Event 2: Timer tick (time-based flush)
        _ = ticker.tick() => {
            if !self.buffer.is_empty() {
                self.stats.time_flushes += 1;
                return Some(self.create_batch());
            }
        }
    }
}
```

### Select! Akış Diyagramı

```
┌─────────────────────────────────────────────────────────────┐
│                     select! loop                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────────┐         ┌──────────────────┐         │
│   │   rx.recv()      │         │  ticker.tick()   │         │
│   │   (log geldi?)   │         │  (zaman doldu?)  │         │
│   └────────┬─────────┘         └────────┬─────────┘         │
│            │                            │                    │
│            ▼                            ▼                    │
│   ┌──────────────────┐         ┌──────────────────┐         │
│   │ Some(entry):     │         │ buffer.len() > 0:│         │
│   │   buffer.push()  │         │   create_batch() │         │
│   │   if full: flush │         │   return batch   │         │
│   │                  │         │                  │         │
│   │ None:            │         │ else:            │         │
│   │   flush & return │         │   continue       │         │
│   └──────────────────┘         └──────────────────┘         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Backpressure Mekanizması

### Backpressure Nedir?

Consumer (buffer) yavaşladığında producer'ı (generator) otomatik yavaşlatma.

```
Normal durum:
Producer ──100 msg/s──▶ Channel ──100 msg/s──▶ Consumer
                        [░░░░░░░░░░]
                        (10% dolu)

Backpressure:
Producer ──100 msg/s──▶ Channel ──50 msg/s──▶ Consumer (yavaşladı)
                        [██████████]
                        (100% dolu)

                  ⬆ Producer bekliyor (send().await)
```

### Projede Backpressure

```rust
// Producer tarafı
match tx.send(entry).await {
    Ok(()) => logs_generated += 1,
    Err(_) => {
        // Channel kapandı
        break;
    }
}
// send().await channel doluysa otomatik bekler
```

### Overflow Handling

Buffer taşma durumunda en eski log'ları silme:

```rust
fn add_entry(&mut self, entry: LogEntry) {
    self.stats.logs_received += 1;

    // Buffer overflow kontrolü
    if self.buffer.len() >= self.config.max_capacity {
        // En eski %10'u sil
        let drop_count = self.buffer.len() / 10;
        let drop_count = drop_count.max(1);

        warn!(
            buffer_size = self.buffer.len(),
            drop_count = drop_count,
            "Buffer overflow: dropping oldest logs"
        );

        self.buffer.drain(0..drop_count);
        self.stats.logs_dropped += drop_count as u64;
    }

    self.buffer.push(entry);
}
```

---

## Graceful Shutdown Pattern

Channel kapatılınca consumer'ın düzgün kapanması:

### Shutdown Sırası

```
1. SIGINT/Ctrl+C alındı
   │
   ▼
2. tx (Sender) drop edildi
   │
   ▼
3. rx.recv() None döndü
   │
   ▼
4. Buffer kalan log'ları flush etti
   │
   ▼
5. Consumer task tamamlandı
```

### Kod Örneği

```rust
// main.rs'de
match tokio::signal::ctrl_c().await {
    Ok(()) => {
        info!("Shutdown signal received");
    }
    Err(e) => {
        error!(error = %e, "Failed to listen for shutdown");
    }
}

// Sender'ı drop et → channel kapanır
drop(tx);

// Buffer task'ın bitmesini bekle (timeout ile)
match timeout(Duration::from_secs(10), buffer_handle).await {
    Ok(Ok(())) => info!("Buffer shut down gracefully"),
    Ok(Err(e)) => warn!(error = %e, "Buffer task panicked"),
    Err(_) => warn!("Buffer shutdown timed out"),
}
```

---

## İstatistik Toplama

### BufferStats Yapısı

```rust
#[derive(Debug, Clone, Default)]
pub struct BufferStats {
    /// Toplam alınan log sayısı
    pub logs_received: u64,

    /// Toplam flush edilen log sayısı
    pub logs_flushed: u64,

    /// Overflow nedeniyle silinen log sayısı
    pub logs_dropped: u64,

    /// Size threshold ile tetiklenen flush sayısı
    pub size_flushes: u64,

    /// Timer ile tetiklenen flush sayısı
    pub time_flushes: u64,
}
```

### Monitoring için Kullanım

```rust
let stats = buffer.stats();
info!(
    received = stats.logs_received,
    flushed = stats.logs_flushed,
    dropped = stats.logs_dropped,
    "Buffer statistics"
);
```

---

## Best Practices

### 1. Clone Sender, Move Receiver

```rust
// Sender clone edilebilir
let tx1 = tx.clone();
let tx2 = tx.clone();

// Receiver sadece bir tane olabilir (Single-Consumer)
// rx.clone() → HATA!
```

### 2. Error Handling

```rust
// İyi: Tüm hata durumlarını handle et
match tx.try_send(entry) {
    Ok(()) => metrics.sent.inc(),
    Err(TrySendError::Full(entry)) => {
        metrics.dropped.inc();
        warn!("Channel full, dropping log");
    }
    Err(TrySendError::Closed(_)) => {
        info!("Channel closed, shutting down");
        break;
    }
}
```

### 3. Bounded Channel Kullan

```rust
// İyi: Bounded channel
let (tx, rx) = mpsc::channel(1000);

// Riskli: Unbounded channel (memory tükenebilir)
let (tx, rx) = mpsc::unbounded_channel();
```

### 4. Timeout ile Shutdown

```rust
// İyi: Timeout ile bekleme
match timeout(Duration::from_secs(10), handle).await {
    Ok(result) => handle_result(result),
    Err(_) => warn!("Task did not complete in time"),
}

// Riskli: Sonsuz bekleme
handle.await;  // Sonsuza kadar bekleyebilir
```

---

## Performans Karşılaştırması

| Özellik | tokio::sync::mpsc | std::sync::mpsc | crossbeam |
|---------|-------------------|-----------------|-----------|
| Async desteği | Var | Yok | Yok |
| Multi-producer | Var | Var | Var |
| Bounded | Var | Yok | Var |
| Backpressure | Var | Yok | Var |
| Overhead | Orta | Düşük | Düşük |
| Tokio uyumu | Mükemmel | Blocking | Blocking |

**Projede `tokio::sync::mpsc` tercih edildi çünkü:**
- Async/await ile doğal entegrasyon
- Tokio runtime ile uyum
- Built-in backpressure

---

## Özet

MPSC channel pattern'i Edge Collector'da şunları sağlıyor:

1. **Decoupling** - Producer ve consumer birbirinden bağımsız
2. **Backpressure** - Otomatik rate limiting
3. **Non-blocking** - Async I/O ile yüksek throughput
4. **Graceful shutdown** - Channel kapatılınca düzgün kapanma
5. **Statistics** - Buffer durumu monitoring

---

## Bağlantılar

- [[rust-giris]] - Temel Rust kavramları (ownership, borrowing)
- [[tokio-runtime]] - Async runtime ve select! macro
- [[buffer-rs-analiz]] - Buffer modülü detaylı analizi
- [[main-rs-analiz]] - Ana uygulama ve task orchestration
- [[error-handling-rust]] - Hata yönetimi pattern'leri
- [[edge-cloud-hybrid]] - Genel mimari ve data flow
- [[why-rust-why-python]] - Dil seçimi gerekçesi

---

## Kaynaklar

- [Tokio MPSC Documentation](https://docs.rs/tokio/latest/tokio/sync/mpsc/index.html)
- [Async Channels in Rust](https://tokio.rs/tokio/tutorial/channels)
- [Backpressure Explained](https://medium.com/@jayphelps/backpressure-explained-the-flow-of-data-through-software-2350b3e77ce7)
