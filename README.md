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
  "nodes": [
    {"id": "A", "host": "127.0.0.1", "port": 8001, "folder": "nodes/Node_A"},
    {"id": "B", "host": "127.0.0.1", "port": 8002, "folder": "nodes/Node_B"},
    {"id": "C", "host": "127.0.0.1", "port": 8003, "folder": "nodes/Node_C"}
  ]
}
```

`chunk_size` varsayılan olarak 64 MB'dir. Test veya demo için daha küçük bir değer kullanılabilir.

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

Farklı bir config dosyası kullanmak için:

```bash
python main.py --config custom-config.json encrypt --input test.bin --output workspace
```

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

## Bilinen Sınırlamalar

- Bu proje localhost tabanlı bir MVP'dir.
- Gerçek production P2P sistemi değildir.
- P2P discovery, peer identity, authentication, authorization veya TLS yoktur.
- NAT traversal yoktur.
- `node` komutu basit TCP servis gösterimidir; ana reconstruct akışı node klasörlerinden okur.
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
