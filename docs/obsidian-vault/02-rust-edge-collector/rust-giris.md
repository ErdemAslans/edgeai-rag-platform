# Rust'a Giriş - Edge Collector Perspektifi

Bu döküman, EdgeAI RAG Platform'un [[edge-cloud-hybrid|edge-collector]] servisinde kullanılan Rust kavramlarını açıklıyor. Eğer Rust'a yeniysen veya bu projede kullanılan pattern'leri anlamak istiyorsan, doğru yerdesin.

#rust #giris #edge-collector

---

## Rust Neden Edge Collector İçin Seçildi?

[[why-rust-why-python]] dökümanında detaylı açıkladığımız gibi, Rust'ın seçilme nedenleri:

1. **Bellek güvenliği** - Garbage Collector olmadan memory-safe kod
2. **Performans** - C/C++ seviyesinde hız
3. **Async desteği** - Tokio ile yüksek performanslı I/O
4. **Zero-cost abstractions** - Yüksek seviye yazıp düşük seviye performans alma

**Analoji:** Rust, "güvenlik kemeri takılı yarış arabası" gibi. Hem hızlısın hem de kaza yapsan bile zarar görmezsin.

---

## Temel Kavramlar

Bu projede kullandığımız temel Rust kavramlarını öğrenelim:

### 1. Ownership (Sahiplik)

Rust'ın en önemli özelliği ownership sistemi. Her değerin tek bir "sahibi" var.

```rust
let log_entry = LogEntry::new("sensor-1", LogLevel::Info, "Temperature: 25°C");
// log_entry artık bu satırın "sahibi"

let moved_entry = log_entry;
// Sahiplik transfer edildi, log_entry artık kullanılamaz!
```

#### Ownership - Neden Bu?

**Bu nedir?** Her değerin bellekte tek bir sahibi olması kuralı.

**Neden burada kullanıldı?** Garbage Collector olmadan bellek güvenliği sağlamak için.

**Olmasaydı ne olurdu?**
- Memory leak'ler oluşabilirdi
- Use-after-free bug'ları olabilirdi
- Double-free crash'leri yaşanabilirdi

**Analoji:** Bir evin tapusu gibi düşün. Evi sadece tapu sahibi satabilir. Tapu devredilince eski sahibin yetkisi kalmaz.

**Bağlantılar:** [[buffer-rs-analiz]], [[main-rs-analiz]]

---

### 2. Borrowing (Ödünç Alma)

Değeri taşımadan (move etmeden) kullanmak için referans alabilirsin:

```rust
fn log_level_to_string(entry: &LogEntry) -> String {
    // entry'yi ödünç aldık, sahiplik değişmedi
    format!("Level: {:?}", entry.level)
}

let entry = LogEntry::new("sensor-1", LogLevel::Info, "Test");
let level_str = log_level_to_string(&entry); // & ile referans
println!("{}", entry.message); // entry hala kullanılabilir!
```

#### Borrowing Kuralları

1. **İstediğin kadar immutable referans (`&T`)** alabilirsin
2. **Ya da tek bir mutable referans (`&mut T`)** alabilirsin
3. İkisi aynı anda olmaz!

**Analoji:** Kütüphane kitabı gibi. Herkes okuyabilir (immutable), ama sadece bir kişi üzerine not alabilir (mutable).

---

### 3. Result ve Option - Hata Yönetimi

Rust'ta null yok! Bunun yerine `Option` ve `Result` kullanıyoruz.

```rust
// Option - değer olabilir veya olmayabilir
fn find_sensor(id: &str) -> Option<Sensor> {
    // Some(sensor) veya None döner
}

// Result - başarı veya hata
fn send_batch(batch: LogBatch) -> Result<(), SendError> {
    // Ok(()) veya Err(SendError) döner
}
```

#### Result ve Option - Neden Bu?

**Bu nedir?** Rust'ın type-safe hata yönetimi sistemi.

**Neden burada kullanıldı?** [[config-rs-analiz|Config loading]] ve [[client-rs-analiz|HTTP requests]] gibi başarısız olabilecek işlemlerde.

**Olmasaydı ne olurdu?**
- NullPointerException tarzı runtime hatalar olurdu
- Hata handling'i unutulabilirdi
- "Happy path" varsayımı ile kod yazılırdı

**Projeden örnek:**
```rust
// config.rs'den
let config = match Config::from_env() {
    Ok(config) => config,
    Err(e) => {
        error!(error = %e, "Failed to load configuration");
        std::process::exit(1);
    }
};
```

**Bağlantılar:** [[error-handling-rust]], [[config-rs-analiz]]

---

### 4. Structs ve Enums

Rust'ta custom type'lar oluşturmak için struct ve enum kullanıyoruz:

```rust
// Struct - veri gruplamak için
#[derive(Debug, Clone)]
pub struct BufferConfig {
    pub batch_size: usize,
    pub flush_interval: Duration,
    pub max_capacity: usize,
}

// Enum - farklı durumları temsil etmek için
#[derive(Debug)]
pub enum LogLevel {
    Debug,
    Info,
    Warning,
    Error,
}

// Enum with data - Rust'ın güçlü özelliği
pub enum BufferError {
    Full,
    Closed,
}
```

#### Derive Macro Nedir?

`#[derive(...)]` ile Rust otomatik kod üretir:

| Derive | Ne Yapar? |
|--------|-----------|
| `Debug` | `{:?}` ile print edilebilir |
| `Clone` | `.clone()` ile kopyalanabilir |
| `Default` | `Type::default()` ile varsayılan değer |
| `Serialize` | JSON'a dönüştürülebilir (serde) |
| `Deserialize` | JSON'dan okunabilir (serde) |

**Bağlantılar:** [[buffer-rs-analiz]], [[singleton-pattern]]

---

### 5. Async/Await ve Tokio

[[tokio-runtime]] bu konuyu derinlemesine anlatıyor. Kısa özet:

```rust
// async fonksiyon tanımla
async fn fetch_data() -> Result<Data, Error> {
    // await ile bekle
    let response = client.get(url).send().await?;
    Ok(response.json().await?)
}

// Tokio runtime ile çalıştır
#[tokio::main]
async fn main() {
    fetch_data().await.unwrap();
}
```

#### Async - Neden Bu?

**Bu nedir?** Non-blocking I/O için Rust'ın asenkron programlama modeli.

**Neden burada kullanıldı?** Edge collector'ın aynı anda log üretme ve HTTP gönderme yapması gerekiyor.

**Olmasaydı ne olurdu?**
- Her HTTP isteği thread block ederdi
- Binlerce concurrent connection için binlerce thread gerekir → memory patlar
- Log generation HTTP beklerken durur

**Analoji:** Garson örneği. Tek garson 20 masaya bakabilir çünkü mutfağı beklerken boş durmuyor, diğer masalara gidiyor.

**Bağlantılar:** [[tokio-runtime]], [[mpsc-channels]]

---

### 6. MPSC Channels

Multi-Producer Single-Consumer channel'lar, thread'ler arası iletişim için:

```rust
use tokio::sync::mpsc;

// Channel oluştur
let (tx, mut rx) = mpsc::channel::<LogEntry>(1000);

// Producer (üretici)
tx.send(log_entry).await?;

// Consumer (tüketici)
while let Some(entry) = rx.recv().await {
    process(entry);
}
```

[[mpsc-channels]] dökümanında bu konuyu derinlemesine inceliyoruz.

**Bağlantılar:** [[buffer-rs-analiz]], [[mpsc-channels]]

---

### 7. Arc - Thread-Safe Shared Ownership

Birden fazla task'ın aynı veriye erişmesi gerektiğinde:

```rust
use std::sync::Arc;

let client = Arc::new(LogClient::new(&config)?);

// Clone ile referans sayısı artar, veri kopyalanmaz
let client_for_task = client.clone();

tokio::spawn(async move {
    client_for_task.send(data).await;
});
```

#### Arc - Neden Bu?

**Bu nedir?** Atomically Reference Counted pointer - thread-safe shared ownership.

**Neden burada kullanıldı?** Buffer task ve main task'ın aynı HTTP client'ı kullanması için.

**Olmasaydı ne olurdu?**
- Her task için ayrı HTTP client → connection pool avantajı yok
- Ya da unsafe shared state → race condition

**Analoji:** Banka kasası gibi. Herkes giriş kartına sahip (Arc clone), ama kasa tek ve herkes aynı kasaya erişiyor.

**Bağlantılar:** [[main-rs-analiz]], [[client-rs-analiz]]

---

### 8. Pattern Matching

Rust'ın güçlü pattern matching özelliği:

```rust
// Match expression
match result {
    Ok(value) => println!("Success: {}", value),
    Err(e) => println!("Error: {}", e),
}

// if let - tek case için
if let Some(config) = config_option {
    use_config(config);
}

// while let - loop içinde
while let Some(entry) = rx.recv().await {
    process(entry);
}
```

**Projeden örnek (main.rs):**
```rust
match tokio::time::timeout(shutdown_timeout, buffer_handle).await {
    Ok(Ok(())) => info!("Buffer task shut down gracefully"),
    Ok(Err(e)) => warn!(error = %e, "Buffer task panicked"),
    Err(_) => warn!("Buffer task shutdown timed out"),
}
```

---

### 9. Traits - Interface'ler

Trait'ler, type'ların implement etmesi gereken davranışları tanımlar:

```rust
// Trait tanımı
pub trait Display {
    fn fmt(&self, f: &mut Formatter) -> Result;
}

// Implementation
impl std::fmt::Display for BufferError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            BufferError::Full => write!(f, "Buffer channel is full"),
            BufferError::Closed => write!(f, "Buffer has been closed"),
        }
    }
}
```

**Yaygın standart trait'ler:**
- `Display` - kullanıcı dostu string formatı
- `Debug` - debug formatı
- `Clone` - deep copy
- `Send` - thread'ler arası gönderilebilir
- `Sync` - thread'ler arası paylaşılabilir

---

## Projede Kullanılan Crate'ler

[[Cargo.toml]] dosyasından dependency'ler:

| Crate | Kullanım Amacı |
|-------|----------------|
| `tokio` | Async runtime, channel, timer |
| `reqwest` | HTTP client |
| `serde` | Serialization/Deserialization |
| `serde_json` | JSON parsing |
| `chrono` | Tarih/saat işlemleri |
| `uuid` | Unique identifier üretimi |
| `tracing` | Structured logging |
| `rand` | Random number generation |

---

## Öğrenme Yolu

Rust'ı bu projede öğrenmek istiyorsan, şu sırayı takip et:

1. **Bu dosya** - Temel kavramları anla
2. [[tokio-runtime]] - Async programlamayı öğren
3. [[mpsc-channels]] - Channel pattern'ini kavra
4. [[buffer-rs-analiz]] - Gerçek kod analizi
5. [[config-rs-analiz]] - Error handling pratiği
6. [[client-rs-analiz]] - HTTP client pattern'i
7. [[main-rs-analiz]] - Her şeyin birleşimi
8. [[error-handling-rust]] - İleri seviye hata yönetimi

---

## Kaynaklar

- [The Rust Book](https://doc.rust-lang.org/book/) - Resmi Rust kitabı
- [Tokio Tutorial](https://tokio.rs/tokio/tutorial) - Async Rust öğrenmek için
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/) - Örneklerle öğrenme

---

## Bağlantılar

- [[why-rust-why-python]] - Dil seçimi gerekçesi
- [[edge-cloud-hybrid]] - Mimari genel bakış
- [[tokio-runtime]] - Async runtime detayları
- [[mpsc-channels]] - Channel pattern açıklaması
- [[buffer-rs-analiz]] - Buffer modülü analizi
- [[error-handling-rust]] - Hata yönetimi detayları
- [[07-glossary]] - Teknik terimler sözlüğü
