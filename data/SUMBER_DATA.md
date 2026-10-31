# Sumber data

Semua file di folder ini dibuat otomatis oleh skrip di `src/` dari API publik, gratis, tanpa API key.
File yang ada di repo adalah **snapshot** supaya dashboard tetap jalan tanpa internet. Perbarui dengan
`python -m src.ambil_blok --jam 24` lalu `python -m src.ambil_harga`, atau tombol di sidebar app.

## 1. `transaksi_paus.csv` — transaksi dengan total output ≥ 50 BTC

| Kolom | Arti |
|---|---|
| `txid` | Hash transaksi. Buka di `https://mempool.space/tx/<txid>` |
| `waktu` | Waktu blok tempat transaksi ditambang (UTC, naive) |
| `tinggi_blok` | Nomor blok |
| `jumlah_input` | Jumlah input yang punya nilai (input coinbase tidak dihitung) |
| `jumlah_output` | Jumlah output |
| `total_btc` | Jumlah semua output, dalam BTC. Ini ukuran "seberapa besar" transaksinya |
| `input_btc` | Jumlah semua input, dalam BTC |
| `fee_btc` | Biaya transaksi (`input_btc − total_btc`, dari field `fee` API) |
| `output_terbesar_btc` | Output tunggal terbesar |
| `alamat_terbesar` | Alamat tujuan output terbesar (kosong untuk output tanpa alamat, misalnya OP_RETURN) |
| `pola` | `konsolidasi` (input ≥ 3, output ≤ 2), `distribusi` (input ≤ 2, output ≥ 3), `transfer` (sisanya) |
| `bulat` | `True` kalau `output_terbesar_btc` bilangan bulat BTC |

- **Sumber:** daftar blok dari `https://mempool.space/api/v1/blocks[/{tinggi}]`, isi blok dari
  `https://blockchain.info/rawblock/{hash}`. Nilai API dalam satoshi; dibagi 100.000.000.
- **Ambang simpan 50 BTC** diatur oleh `AMBANG_SIMPAN_BTC` di `src/ambil_blok.py`. Slider di app mulai
  dari angka ini.
- Transaksi diurutkan menurut `waktu`, duplikat `txid` dibuang.

## 2. `blok.csv` — ringkasan tiap blok yang sudah diproses

| Kolom | Arti |
|---|---|
| `tinggi`, `hash`, `waktu` | Identitas blok (waktu UTC) |
| `jumlah_tx` | Jumlah transaksi dalam blok |
| `jumlah_paus` | Berapa transaksi yang lolos ambang simpan |
| `btc_paus` | Total BTC yang dipindahkan transaksi-transaksi itu |

File ini juga berfungsi sebagai "daftar yang sudah dikerjakan": `perbarui_data` melewati blok yang
tingginya sudah ada di sini, sehingga blok tanpa satu pun paus tidak diunduh berulang.

## 3. `btc_harga_5menit.csv` — candle BTC-USD per 5 menit

| Kolom | Arti |
|---|---|
| `waktu` | Awal candle (UTC) |
| `open`, `high`, `low`, `close` | Harga dalam USD |
| `volume` | Volume dalam BTC |

- **Sumber:** Coinbase Exchange, `https://api.exchange.coinbase.com/products/BTC-USD/candles`
  dengan `granularity=300`, maksimal 300 candle per request (skrip memecah per 24 jam).
- **Kenapa bukan Binance?** Request dari beberapa negara ditolak (HTTP 403). Kenapa bukan Yahoo? Hanya
  harian. Kraken dan CoinGecko juga bisa dipakai; lihat komentar di `src/ambil_harga.py`.
- Rentang harga dibuat menutupi `blok.csv` ditambah 4 jam setelah blok terakhir, supaya return 4 jam
  bisa dihitung untuk semua transaksi. Transaksi yang terlalu dekat dengan ujung data mendapat `NaN`.

## Keterbatasan data

- Waktu transaksi = waktu blok. Transaksi sudah bisa terlihat di mempool beberapa menit sebelumnya.
- Timestamp blok diisi penambang dan boleh meleset sampai sekitar 2 jam dari waktu sebenarnya
  (aturan protokol); dalam praktik biasanya meleset kurang dari semenit.
- Tidak ada label alamat (bursa, kustodian, penambang). `pola` hanya dari bentuk transaksi.
- Harga dari satu bursa. Perbedaan antar bursa biasanya beberapa dolar, tidak mengubah kesimpulan.
- Satu transaksi bisa berisi banyak pihak (CoinJoin, batch bursa). "Satu paus" tidak selalu satu orang.
