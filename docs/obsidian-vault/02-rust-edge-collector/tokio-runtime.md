# Tokio Runtime - Async Rust Patterns

Bu döküman, [[rust-giris|Edge Collector]]'da kullanılan Tokio async runtime pattern'lerini derinlemesine açıklıyor. Rust'ın async/await modeli ile yüksek performanslı, non-blocking I/O işlemlerini nasıl yaptığımızı öğreneceksin.

#rust #tokio #async #edge-collector

---

## Tokio Nedir?

Tokio, Rust için asenkron runtime'dır. Edge Collector'ın aynı anda:
- Log üretmesi
- HTTP istekleri göndermesi
- Timer'ları yönetmesi
- Graceful shutdown yapması

...hepsini tek bir thread pool ile yapabilmesini sağlar.

**Analoji:** Tokio, bir orkestra şefi gibi. Her müzisyen (task) kendi partisini çalar, ama şef (runtime) hepsini koordine eder ve sıranın kime geldiğini belirler.

---

## Runtime Başlatma: `#[tokio::main]`

[[main-rs-analiz|main.rs]]'de gördüğün ilk Tokio pattern'i:

```rust
#[tokio::main]
async fn main() {
    // Burası artık async context içinde
    info!("Starting Edge Collector service...");

    // await kullanabiliriz
    let result = some_async_function().await;
}
```

### Bu Macro Ne Yapar?

`#[tokio::main]` aslında şuna dönüşür:

```rust
fn main() {
    tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .unwrap()
        .block_on(async {
            // async main içeriği
        })
}
```

### Runtime Türleri

| Runtime | Kullanım | Thread Sayısı |
|---------|----------|---------------|
| `multi_thread` | Varsayılan, production | CPU çekirdek sayısı |
| `current_thread` | Test, basit uygulamalar | 1 |

**Projede:** Multi-thread runtime kullanıyoruz çünkü HTTP istekleri ve log generation paralel çalışmalı.

---

## Task Spawning: `tokio::spawn`

Ana runtime'dan bağımsız çalışan task'lar oluşturmak için:

```rust
// Buffer task - logs'ları toplar ve gönderir
let buffer_handle = tokio::spawn(async move {
    info!("Buffer task started");
    buffer_task(rx, config.batch_size, config.flush_interval, |batch| {
        let client = client_clone.clone();
        async move {
            send_batch(&client, batch).await
        }
    })
    .await;
    info!("Buffer task completed");
});

// Generator task - log üretir
let generator_handle = tokio::spawn(async move {
    info!("Generator task started");
    run_generator(generator, tx_clone).await;
    info!("Generator task completed");
});
```

### `tokio::spawn` - Neden Bu?

**Bu nedir?** Async task'ları runtime'a ekleyerek concurrent (eş zamanlı) çalışma.

**Neden burada kullanıldı?**
- Log üretimi ve HTTP gönderimi birbirini beklememeli
- Buffer dolunca gönderim yapılırken üretim devam etmeli

**Olmasaydı ne olurdu?**
- Her HTTP isteği tüm sistemi block ederdi
- Log üretimi durur, buffer taşar
- Throughput dramatik şekilde düşerdi

**Analoji:** Restoran mutfağı gibi. Şef (main task) siparişleri alır, aşçılar (spawned tasks) paralel pişirir. Bir yemek hazırlanırken diğerleri beklemiyor.

**Bağlantılar:** [[buffer-rs-analiz]], [[main-rs-analiz]]

---

## Channels: `tokio::sync::mpsc`

[[mpsc-channels]] dökümanında detaylı anlattığımız pattern:

```rust
use tokio::sync::mpsc;

// Channel oluştur - 1000 log kapasiteli buffer
let (tx, rx) = mpsc::channel(CHANNEL_CAPACITY);

// Producer tarafı (Generator)
match tx.send(entry).await {
    Ok(()) => logs_generated += 1,
    Err(_) => {
        // Channel kapandı
        break;
    }
}

// Consumer tarafı (Buffer Task)
while let Some(entry) = rx.recv().await {
    buffer.push(entry);
}
```

### Channel Kapasitesi Seçimi

| Kapasite | Avantaj | Dezavantaj |
|----------|---------|------------|
| Düşük (100) | Az bellek | Backpressure hızlı devreye girer |
| Orta (1000) | Dengeli | - |
| Yüksek (10000) | Spike'ları absorbe eder | Bellek kullanımı artar |

**Projede:** `CHANNEL_CAPACITY = 1000` - Dengeli bir tercih.

---

## Timer Patterns: `tokio::time`

Edge Collector'da üç timer pattern kullanıyoruz:

### 1. Interval - Düzenli Tekrarlanan İşler

```rust
use tokio::time::interval;

async fn run_generator(generator: LogGenerator, tx: mpsc::Sender<LogEntry>) {
    let mut ticker = interval(Duration::from_millis(50));

    loop {
        ticker.tick().await;  // Her 50ms'de bir çalışır
        let entry = generator.generate();
        tx.send(entry).await.ok();
    }
}
```

### 2. Timeout - Zaman Aşımı Kontrolü

```rust
use tokio::time::timeout;

// Buffer shutdown'ına 10 saniye ver
let shutdown_timeout = Duration::from_secs(10);
match timeout(shutdown_timeout, buffer_handle).await {
    Ok(Ok(())) => info!("Buffer task shut down gracefully"),
    Ok(Err(e)) => warn!(error = %e, "Buffer task panicked"),
    Err(_) => warn!("Buffer task shutdown timed out"),
}
```

### 3. Sleep - Tek Seferlik Bekleme

```rust
use tokio::time::sleep;

// Retry öncesi bekleme
sleep(Duration::from_secs(1)).await;
retry_request().await;
```

### Timer Patterns - Neden Bu?

**Bu nedir?** Zaman tabanlı async operasyonlar.

**Neden burada kullanıldı?**
- Log generation: Sabit hızda log üretimi (interval)
- Buffer flush: Belirli aralıklarla batch gönderimi (interval)
- Graceful shutdown: Timeout ile sonsuz beklemeyi önleme (timeout)
- Retry logic: Başarısız istekler arası bekleme (sleep)

**Olmasaydı ne olurdu?**
- Busy-loop ile CPU %100 olurdu
- Shutdown sonsuz sürebilirdi
- Rate limiting yapılamazdı

**Analoji:** Mutfak timer'ı gibi. Yemeği kontrol etmek için sürekli fırına bakmak yerine, timer kurup alarm beklersin.

---

## Concurrent Event Handling: `tokio::select!`

[[buffer-rs-analiz|buffer.rs]]'deki en kritik pattern:

```rust
loop {
    tokio::select! {
        // Event 1: Yeni log geldi
        Some(log) = rx.recv() => {
            buffer.push(log);

            if buffer.len() >= batch_size {
                // Size-based flush
                flush_buffer(&mut buffer).await;
            }
        }

        // Event 2: Timer tick
        _ = ticker.tick() => {
            if !buffer.is_empty() {
                // Time-based flush
                flush_buffer(&mut buffer).await;
            }
        }
    }
}
```

### `select!` - Neden Bu?

**Bu nedir?** Birden fazla async event'i aynı anda bekleyip, hangisi önce hazırsa onu işleme.

**Neden burada kullanıldı?** Buffer iki koşulda flush olmalı:
1. Batch size dolduğunda (log sayısı)
2. Zaman aşımında (interval geçti)

Her ikisini de bekleyip hangisi önce olursa onu işlemeliyiz.

**Olmasaydı ne olurdu?**
- İki ayrı task gerekir → karmaşıklık artar
- Shared state için mutex gerekir → deadlock riski
- Ya size-based ya time-based olur, ikisi birden olmaz

**Analoji:** Kapı zili + telefon gibi. İkisini de duyuyorsun, hangisi önce çalarsa ona cevap veriyorsun.

**Bağlantılar:** [[buffer-rs-analiz]], [[mpsc-channels]]

---

## Signal Handling: `tokio::signal`

Graceful shutdown için SIGINT/SIGTERM yakalama:

```rust
// Ctrl+C bekle
match tokio::signal::ctrl_c().await {
    Ok(()) => {
        info!("Shutdown signal received, stopping...");
    }
    Err(e) => {
        error!(error = %e, "Failed to listen for shutdown signal");
    }
}

// Graceful shutdown başlat
info!("Initiating graceful shutdown...");

// Sender'ı drop et → channel kapanır → consumer task biter
drop(tx);

// Generator'ı abort et
generator_handle.abort();

// Buffer'ın remaining logs'ları flush etmesini bekle
match timeout(Duration::from_secs(10), buffer_handle).await {
    Ok(Ok(())) => info!("Buffer task shut down gracefully"),
    // ...
}
```

### Graceful Shutdown Sırası

```
1. Ctrl+C alındı
2. tx (Sender) drop edildi
   └── rx.recv() None döner
       └── Buffer kalan log'ları flush eder
3. Generator task abort edildi
4. Buffer task completion bekleniyor (timeout ile)
5. Uygulama kapanır
```

### Signal Handling - Neden Bu?

**Bu nedir?** OS sinyallerini async olarak yakalama.

**Neden burada kullanıldı?**
- Ctrl+C ile düzgün kapanma
- Docker/K8s SIGTERM sinyallerini yakalama
- Veri kaybını önleme (buffer'daki log'ları flush etme)

**Olmasaydı ne olurdu?**
- Ani kapanma ile buffer'daki log'lar kaybolur
- HTTP istekleri yarım kalır
- Resource leak oluşabilir

**Analoji:** Bilgisayarı kapatmak gibi. Güç düğmesine basıp beklemek yerine, düzgün shutdown yaparak açık dosyaları kaydetmek.

**Bağlantılar:** [[main-rs-analiz]], [[error-handling-rust]]

---

## JoinHandle ve Task Yönetimi

`tokio::spawn` bir `JoinHandle` döner:

```rust
let handle: JoinHandle<()> = tokio::spawn(async {
    // task içeriği
});

// Task'ın bitmesini bekle
handle.await.unwrap();

// Veya abort et
handle.abort();

// Abort sonrası await
match handle.await {
    Ok(()) => println!("Completed normally"),
    Err(e) if e.is_cancelled() => println!("Task was aborted"),
    Err(e) => println!("Task panicked: {:?}", e),
}
```

### JoinHandle Pattern'leri

| Pattern | Kullanım |
|---------|----------|
| `handle.await` | Task bitene kadar bekle |
| `handle.abort()` | Task'ı iptal et |
| `handle.is_finished()` | Task bitti mi kontrol et |
| `timeout(dur, handle)` | Timeout ile bekle |

---

## Move Semantics ve Async Closures

Tokio task'larına veri geçirmek için `move`:

```rust
// Arc clone ile shared ownership
let client_clone = client.clone();

// move ile ownership transfer
let buffer_handle = tokio::spawn(async move {
    // client_clone artık bu task'ın
    buffer_task(rx, batch_size, flush_interval, move |batch| {
        let client = client_clone.clone();  // Her flush için clone
        async move {
            send_batch(&client, batch).await
        }
    }).await;
});
```

### Move Kuralları

1. **`async move`**: Tüm capture edilen değerlerin ownership'i task'a geçer
2. **Nested closures**: Her closure için ayrı clone gerekebilir
3. **Arc kullanımı**: Shared data için [[rust-giris#7. Arc - Thread-Safe Shared Ownership|Arc]] pattern'i

**Bağlantılar:** [[rust-giris]], [[buffer-rs-analiz]]

---

## Error Handling in Async

Async context'te hata yönetimi:

```rust
// ? operatörü ile propagation
async fn send_batch(client: &LogClient, batch: LogBatch) -> Result<(), SendError> {
    let response = client.post(batch).await?;

    if !response.status().is_success() {
        return Err(SendError::HttpError(response.status()));
    }

    Ok(())
}

// Match ile explicit handling
match send_batch(&client, batch).await {
    Ok(()) => info!("Batch sent successfully"),
    Err(e) => warn!(error = %e, "Failed to send batch"),
}
```

**Bağlantılar:** [[error-handling-rust]], [[client-rs-analiz]]

---

## Performans İpuçları

### 1. Task Granularity

```rust
// KÖTÜ: Her log için ayrı task
for log in logs {
    tokio::spawn(async move {
        send_log(log).await;
    });
}

// İYİ: Batch processing
tokio::spawn(async move {
    let batch = logs.into_iter().collect();
    send_batch(batch).await;
});
```

### 2. Blocking Operations

```rust
// KÖTÜ: Async task içinde blocking
tokio::spawn(async {
    std::fs::read_to_string("large_file.txt");  // BLOCKER!
});

// İYİ: spawn_blocking kullan
tokio::spawn(async {
    let content = tokio::task::spawn_blocking(|| {
        std::fs::read_to_string("large_file.txt")
    }).await.unwrap();
});
```

### 3. Channel Backpressure

```rust
// Bounded channel ile backpressure
let (tx, rx) = mpsc::channel(1000);

// try_send ile non-blocking check
match tx.try_send(entry) {
    Ok(()) => {},
    Err(TrySendError::Full(_)) => {
        warn!("Channel full, applying backpressure");
    }
    Err(TrySendError::Closed(_)) => {
        break;
    }
}
```

---

## Özet: Edge Collector'daki Tokio Patterns

```
┌─────────────────────────────────────────────────────────────┐
│                     #[tokio::main]                          │
│                     (Multi-thread Runtime)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    mpsc::channel     ┌─────────────────┐  │
│  │  Generator  │ ──────────────────▶  │   Buffer Task   │  │
│  │   Task      │    (tx → rx)         │                 │  │
│  │             │                      │  select! {      │  │
│  │ interval()  │                      │    rx.recv()    │  │
│  │   tick()    │                      │    ticker.tick()│  │
│  └─────────────┘                      │  }              │  │
│                                       └────────┬────────┘  │
│                                                │            │
│                                       ┌────────▼────────┐  │
│                                       │  HTTP Client    │  │
│  ┌─────────────┐                      │  (Arc shared)   │  │
│  │ ctrl_c()   │                       └─────────────────┘  │
│  │ signal     │                                            │
│  └──────┬─────┘                                            │
│         │                                                   │
│         ▼                                                   │
│  Graceful Shutdown: drop(tx) → flush → abort → timeout    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Bağlantılar

- [[rust-giris]] - Temel Rust kavramları
- [[mpsc-channels]] - Channel pattern detayları
- [[buffer-rs-analiz]] - Buffer modülü ve select! kullanımı
- [[main-rs-analiz]] - Ana uygulama yapısı
- [[client-rs-analiz]] - HTTP client ve retry logic
- [[error-handling-rust]] - Async error handling
- [[why-rust-why-python]] - Neden Rust tercih edildi
- [[edge-cloud-hybrid]] - Genel mimari

---

## Kaynaklar

- [Tokio Tutorial](https://tokio.rs/tokio/tutorial) - Resmi Tokio öğretici
- [Async Book](https://rust-lang.github.io/async-book/) - Rust async programlama kitabı
- [Tokio API Docs](https://docs.rs/tokio/latest/tokio/) - Tokio API referansı
