# encrypted-p2p-file-splitter

`encrypted-p2p-file-splitter`, Python 3.11+ ile geliştirilmiş bir MVP dosya güvenliği projesidir. Bir dosyayı AES-256-GCM ile şifreler, şifreli çıktıyı 3 parçaya böler, AES anahtarını 3-of-3 Shamir Secret Sharing mantığıyla 3 ayrı share'e ayırır, bu parçaları localhost üzerinde temsil edilen node klasörlerine dağıtır ve daha sonra 3 node'dan parçaları toplayarak dosyayı geri oluşturur.

Bu proje production seviyesinde bir P2P sistemi değil; kriptografik dosya parçalama, bütünlük doğrulama ve node bazlı dağıtım akışını test edilebilir şekilde gösteren yerel bir MVP'dir.

## Projenin Amacı

Amaç, tek bir dosyayı belleğe komple almadan güvenli şekilde işleyebilen bir prototip oluşturmaktır:

- Dosya chunk bazlı okunur ve AES-256-GCM ile şifrelenir.
- Her chunk için benzersiz nonce kullanılır.
- Şifreli dosya 3 parçaya ayrılır.
- AES anahtarı 3-of-3 Shamir Secret Sharing ile 3 share'e bölünür.
- Her dosya parçası için SHA-256 hash hesaplanır ve manifest dosyasına yazılır.
- Reconstruct sırasında tüm parçalar, hash değerleri ve key share dosyaları doğrulanır.

## Mimari Özet

Proje modüler bir yapıya sahiptir. CLI katmanı yalnızca komutları yönlendirir; kriptografi, bütünlük, depolama, yapılandırma ve node sunucusu ayrı modüllerde tutulur.

- `main.py`: CLI giriş noktası.
- `src/config_module.py`: `config.json` okuma ve node yapılandırması.
- `src/crypto_module.py`: AES-256-GCM streaming encrypt/decrypt işlemleri.
- `src/shamir_module.py`: 3-of-3 Shamir Secret Sharing key split ve reconstruct işlemleri.
- `src/integrity_module.py`: SHA-256 hesaplama ve doğrulama.
- `src/storage_module.py`: Workspace oluşturma, dosya parçalama, dağıtım ve reconstruct akışı.
- `src/network_module.py`: Basit localhost asyncio TCP node server.
- `tests/`: Birim ve end-to-end pytest testleri.

## Kullanılan Teknolojiler

- Python 3.11+
- `cryptography`
- `pytest`
- `asyncio`
- `argparse`
- `hashlib`
- `json`
- `pathlib`

## Klasör Yapısı

```text
encrypted-p2p-file-splitter/
  README.md
  requirements.txt
  config.json
  main.py
  src/
    __init__.py
    crypto_module.py
    shamir_module.py
    integrity_module.py
    storage_module.py
    network_module.py
    config_module.py
  nodes/
    Node_A/
    Node_B/
    Node_C/
  tests/
    test_crypto.py
    test_shamir.py
    test_integrity.py
    test_end_to_end.py
```

## Kurulum

Projeyi çalıştırmak için Python 3.11 veya üzeri gerekir.

```bash
cd encrypted-p2p-file-splitter
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Linux/macOS için sanal ortam aktivasyonu:

```bash
source .venv/bin/activate
```

Testleri çalıştırmak için:

```bash
python -m pytest -q
```

## Yapılandırma

Varsayılan yapılandırma `config.json` içindedir:

```json
{
  "chunk_size": 67108864,
  "timeout_seconds": 30,
  "threshold": 3,
  "nodes": [
    {"id": "A", "host": "127.0.0.1", "port": 8001, "folder": "nodes/Node_A"},
    {"id": "B", "host": "127.0.0.1", "port": 8002, "folder": "nodes/Node_B"},
    {"id": "C", "host": "127.0.0.1", "port": 8003, "folder": "nodes/Node_C"}
  ]
}
```

`chunk_size` varsayılan olarak 64 MB'dir. Test veya demo için daha küçük bir değer kullanılabilir. `threshold` bu MVP'de sabit olarak `3` beklenir.

## CLI Kullanım Örnekleri

Dosyayı şifrele, şifreli çıktıyı 3 parçaya böl ve key share dosyalarını üret:

```bash
python main.py encrypt --input test.bin --output workspace
```

Workspace içindeki parçaları node klasörlerine dağıt:

```bash
python main.py distribute --workspace workspace
```

Node klasörlerinden parçaları ve key share dosyalarını oku, doğrula ve dosyayı geri oluştur:

```bash
python main.py reconstruct --workspace workspace --output restored.bin
```

Belirli bir node için basit TCP server başlat:

```bash
python main.py node --id A
```

CLI işlemleri okunabilir progress çıktıları verir:

```text
[1/4] Encrypting file...
[2/4] Splitting encrypted file...
[3/4] Creating key shares...
[4/4] Writing manifest...
Done.
```

Farklı bir config dosyası kullanmak için:

```bash
python main.py --config custom-config.json encrypt --input test.bin --output workspace
```

## Streamlit UI

CLI sistemi korunur; Streamlit arayüzü ayrı bir katman olarak `ui/` altında bulunur ve backend işlemleri için `src/` modüllerini çağırır.

UI'ı başlatmak için:

```bash
streamlit run ui/app.py
```

Arayüz sayfaları:

- Ana sayfa: demo dashboard, son işlem sonucu, son 5 operation history kaydı, node health ve manifest durumu.
- Encrypt: dosya yükleme, workspace seçimi, progress bar, step-by-step status ve manifest/part bilgileri.
- Distribute: workspace seçimi, manifest doğrulama progress'i, part ve key share dosyalarını node klasörlerine dağıtma.
- Reconstruct: restore progress'i, hash karşılaştırması ve restored dosya konumu.
- Node Status: config içindeki node bilgileri, status badge, node klasör dosya listesi ve eksik part/share uyarıları.

UI işlem akışı:

1. Encrypt sayfasında dosya yüklenir ve workspace seçilir.
2. Arayüz `Preparing workspace`, `Encrypting file`, `Splitting file`, `Writing manifest` adımlarını progress olarak gösterir.
3. Distribute sayfasında workspace seçilir; manifest doğrulanır ve parçalar node klasörlerine dağıtılır.
4. Reconstruct sayfasında workspace ve output dosyası seçilir; dosya geri oluşturulur ve hash karşılaştırması gösterilir.
5. Ana sayfa `workspace/operation_history.json` içindeki son 5 işlemi listeler.

Her UI işlemi sonrasında `workspace/operation_history.json` dosyasına şu alanlarla kayıt eklenir: `operation_type`, `status`, `timestamp`, `input_file`, `output_file`, `duration_seconds`, `error_message`.

## Örnek Demo Akışı

Küçük bir demo dosyası oluştur:

```bash
python -c "from pathlib import Path; Path('test.bin').write_bytes(b'demo-data-' * 1000)"
```

Şifreleme ve parçalama işlemini çalıştır:

```bash
python main.py encrypt --input test.bin --output workspace
```

Parçaları node klasörlerine dağıt:

```bash
python main.py distribute --workspace workspace
```

Dosyayı geri oluştur:

```bash
python main.py reconstruct --workspace workspace --output restored.bin
```

Orijinal ve restored dosyanın SHA-256 hash değerlerini karşılaştır:

```bash
python -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('test.bin').read_bytes()).hexdigest()); print(hashlib.sha256(Path('restored.bin').read_bytes()).hexdigest())"
```

Hash değerleri aynıysa encrypt -> distribute -> reconstruct akışı başarıyla tamamlanmıştır.

## Güvenlik Yaklaşımı

### AES-256-GCM

Dosya içeriği AES-256-GCM ile şifrelenir. AES anahtarı 32 byte uzunluğundadır. GCM modu hem gizlilik hem de authentication tag üzerinden şifreli veri doğrulaması sağlar.

Her chunk için 96-bit nonce kullanılır. Nonce değeri rastgele bir prefix ve chunk index değerinden türetilir; böylece aynı dosya içinde nonce tekrarının önüne geçilir.

### Shamir Secret Sharing

AES anahtarı 3-of-3 Shamir Secret Sharing mantığıyla 3 parçaya ayrılır. Bu MVP'de anahtarın geri üretilebilmesi için 3 share'in tamamı gerekir.

Bu yaklaşım tek bir node'un anahtarı tek başına taşımasını engeller. Ancak 3-of-3 eşik yapısı kullanılabilirlik açısından kırılgandır; herhangi bir share kaybolursa reconstruct yapılamaz.

### SHA-256 Bütünlük Doğrulama

Şifreli dosyanın her parçası için SHA-256 hash hesaplanır ve `parts_manifest.json` içine yazılır. Reconstruct sırasında node klasörlerinden okunan parçalar manifestteki hash değerleriyle karşılaştırılır.

Hash uyuşmazlığı varsa reconstruct işlemi reddedilir.

Manifest ayrıca `original_filename`, `original_size`, `original_sha256`, `encrypted_size`, `created_at`, `chunk_size` ve `threshold` alanlarını içerir. Reconstruct işlemi parça okumaya başlamadan önce manifest yapısını doğrular.

### Manifest Authentication

Manifest bütünlüğü için AES anahtarından HKDF-SHA256 ile ayrı bir manifest authentication key türetilir. `parts_manifest.json` içeriği deterministic JSON formatına çevrilir ve `manifest_hmac` alanı hariç tutularak HMAC-SHA256 hesaplanır.

Reconstruct sırasında önce 3 key share ile AES anahtarı yeniden oluşturulur, ardından aynı HKDF key derivation ile manifest authentication key türetilir ve `manifest_hmac` doğrulanır. Manifest elle değiştirilmişse, `manifest_hmac` eksikse veya eski unsigned manifest kullanılıyorsa işlem decrypt aşamasına geçmeden durdurulur.

### Streaming Dosya İşleme

Dosyalar RAM'e komple alınmaz. Şifreleme, parçalama, hash hesaplama ve reconstruct işlemleri chunk-based / streaming mantığıyla yapılır. Varsayılan chunk boyutu `config.json` içindeki `chunk_size` alanıyla yönetilir.

## Testler

Test paketi küçük ve deterministic dosyalarla çalışır. Gerçek `nodes/` klasörlerini kirletmez; node klasörleri test sırasında `tmp_path` altında oluşturulur.

```bash
python -m pytest -q
```

Test kapsamı:

- AES-GCM streaming encrypt/decrypt round-trip.
- Shamir 3-of-3 key reconstruct.
- SHA-256 doğrulama.
- End-to-end encrypt -> distribute -> reconstruct akışı.
- Eksik parça hatası.
- Bozuk hash hatası.
- Eksik veya yanlış key share hatası.

## Docker Usage

Docker desteği CLI, test, node server ve Streamlit UI akışlarını container içinde çalıştırmak için eklenmiştir. Docker imajı `python:3.11-slim` tabanlıdır ve çalışma dizini `/app` olarak ayarlanır.

### Kurulum ve Build

```bash
docker compose build
```

Makefile kullanıyorsanız:

```bash
make docker-build
```

### Docker İçinde Test Çalıştırma

```bash
docker compose run --rm app pytest
```

Ek Docker E2E akışı için:

```bash
docker compose run --rm app python scripts/docker_e2e.py --config config.docker.json
```

Makefile ile ikisini birlikte çalıştırmak için:

```bash
make docker-test
```

### Shared P2P Network Modu

Varsayılan `docker-compose.yml` dosyası `app`, `node-a`, `node-b`, `node-c` ve `ui` servislerini aynı `p2p-shared` Docker network içine koyar. Bu modda node servisleri birbirini Docker service name üzerinden görebilir.

Üç node'u başlat:

```bash
docker compose up -d node-a node-b node-c
```

Demo dosyası oluştur ve CLI akışını Docker içinde çalıştır:

```bash
docker compose run --rm app python -c "from pathlib import Path; Path('workspace/test.bin').write_bytes(b'docker-demo-' * 1000)"
docker compose run --rm app python main.py encrypt --input workspace/test.bin --output workspace --config config.docker.json
docker compose run --rm app python main.py distribute --workspace workspace --config config.docker.json
docker compose run --rm app python main.py reconstruct --workspace workspace --output workspace/restored.bin --config config.docker.json
```

Node TCP iletişimini dağıtım sonrası test etmek için:

```bash
docker compose run --rm app python scripts/docker_network_probe.py --config config.docker.json --node A
```

Makefile ile node'ları başlatmak için:

```bash
make docker-up
```

Kapatmak için:

```bash
make docker-down
```

### Streamlit UI'ı Docker'da Açma

```bash
docker compose up ui
```

Tarayıcıdan aç:

```text
http://localhost:8501
```

Makefile ile:

```bash
make docker-ui
```

UI container içinde `APP_CONFIG=config.docker.json` kullanılır. Local kullanım komutu değişmedi:

```bash
streamlit run ui/app.py
```

### Isolated Network Test Modu

`docker-compose.isolated.yml` dosyası `node-a`, `node-b`, `node-c` ve `app` servislerini ayrı Docker networklere koyar. Bu modda node servislerinin birbirini veya app container'ını görememesi beklenir.

Bu bir uygulama hatası değildir; network izolasyonunda timeout/error mekanizmasının düzgün çalıştığını gösteren negatif testtir.

```bash
make docker-isolated-test
```

Manuel komutlar:

```bash
docker compose -f docker-compose.isolated.yml up -d node-a node-b node-c
docker compose -f docker-compose.isolated.yml run --rm app python scripts/docker_network_probe.py --config config.docker.json --node A --expect-failure
docker compose -f docker-compose.isolated.yml down
```

### Docker Runtime Dosyaları

`workspace` ve `nodes` dizinleri Docker named volume olarak bağlanır. `.dockerignore` dosyası `.git`, venv, cache, `.env`, runtime workspace dosyaları, test çıktıları ve node runtime dosyalarının image içine alınmasını engeller.

## Network Control Center

Streamlit UI içinde `Network Control Center` sayfası node gözlemi ve demo yönetimi için eklenmiştir. Sayfa `src/monitoring_module.py` içindeki helper fonksiyonları kullanır; ağır monitoring mantığı UI içinde tutulmaz.

Özellikler:

- Network Topology: `config.json` veya Docker modunda `config.docker.json` içindeki node'ları Graphviz ile gösterir.
- Node Health Panel: Node ID, host, port, folder path, folder existence, part/share dosyaları, last modified time, TCP durumu ve genel status gösterir.
- Connection Matrix: Node kaynak/hedef matrisinde `Self`, `OK`, `Timeout`, `Offline` gibi durumları gösterir.
- File Distribution Map: Manifest varsa node part hash doğrulaması yapar; manifest yoksa `No manifest found` uyarısı verir.
- Live Event Log: `workspace/network_events.jsonl` içindeki son 50 network/distribute/reconstruct event kaydını filtrelenebilir tablo olarak gösterir.
- Transfer Flow Viewer: Son distribute/reconstruct akışını adım adım yeşil/kırmızı durumlarla gösterir.
- Docker Awareness: `Dockerfile`, `docker-compose.yml`, `config.docker.json` varlığını ve beklenen servisleri gösterir. Docker runtime yoksa sayfa çökmez, `Docker runtime not available in this environment` mesajı gösterir.

Demo akışı:

1. UI'ı başlat:

```bash
streamlit run ui/app.py
```

2. Encrypt sayfasından dosya şifrele.
3. Distribute sayfasından parçaları node klasörlerine dağıt.
4. Network Control Center'dan parçaların hangi node'da olduğunu ve hash durumlarını kontrol et.
5. Reconstruct sayfasından dosyayı geri üret.
6. Network Control Center'dan event log ve transfer flow adımlarını kontrol et.

## Bilinen Sınırlamalar

- Bu proje localhost tabanlı bir MVP'dir.
- Gerçek production P2P sistemi değildir.
- P2P discovery, peer identity, authentication, authorization veya TLS yoktur.
- NAT traversal yoktur.
- `node` komutu basit TCP servis gösterimidir; ana reconstruct akışı node klasörlerinden okur.
- Node protokolü MVP seviyesinde `REQUEST_PART`, `SEND_PART`, `ERROR` ve `ACK` mesajlarını kullanır.
- 3-of-3 eşik modeli kırılgandır: tek bir parça veya key share eksikse dosya geri oluşturulamaz.
- Manifest bütünlüğü için ayrı dijital imza veya MAC katmanı yoktur.
- Kalıcı secret management, audit log ve secure deletion mekanizmaları yoktur.

## Gelecek Geliştirmeler

- Gerçek network tabanlı reconstruct akışı.
- Peer discovery ve node identity doğrulama.
- TLS veya Noise Protocol benzeri güvenli kanal desteği.
- NAT traversal için STUN/TURN veya relay yaklaşımı.
- Configurable threshold desteği, örneğin 2-of-3 veya 3-of-5.
- Manifest imzalama ve replay/tamper koruması.
- Dosya parçası metadata versiyonlama.
- Büyük dosyalar için resume edilebilir transfer.
- CLI için progress bar ve daha detaylı loglama.
- Secure deletion ve secret lifecycle yönetimi.
