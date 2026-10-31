# 🎓 Panduan Belajar: Membaca Blockchain seperti Detektif

Panduan ini untuk pembaca yang sudah bisa Python dasar (variabel, fungsi, list, dict) dan ingin tahu
*mengapa* kode di repo ini ditulis seperti itu. Bacalah sambil membuka file yang dibahas. Tidak ada yang
perlu dihafal; semua bisa dicoba langsung di terminal Python.

Yang akan kamu kuasai setelah selesai:

- membaca **transaksi Bitcoin mentah** dari API publik dan memahami input, output, fee,
- menebak "bentuk" transaksi hanya dari jumlah input dan outputnya,
- menyambungkan dua deret waktu yang **tidak sejajar** (waktu blok vs candle 5 menit),
- satu kebiasaan ilmuwan data yang paling sering dilupakan: **membandingkan dengan baseline**,
- dan kenapa korelasi peringkat (Spearman) lebih aman daripada Pearson saat ada data ekstrem.

---

## Peta besar

```
┌────────────────────────────────────────────────────────────────────┐
│  LAPISAN 4: TAMPILAN        app.py                                  │
│  sidebar → saring → hitung → Plotly → kartu detail saat diklik      │
├────────────────────────────────────────────────────────────────────┤
│  LAPISAN 3: LOGIKA          src/analisis.py                         │
│  harga saat blok → return 15m/1j/4j → baseline → per jam → Spearman │
├────────────────────────────────────────────────────────────────────┤
│  LAPISAN 2: PENGAMBIL DATA  src/ambil_blok.py, src/ambil_harga.py   │
│  mempool.space → blockchain.info → saring ≥ 50 BTC; Coinbase candle │
├────────────────────────────────────────────────────────────────────┤
│  LAPISAN 1: DATA            data/*.csv                              │
│  transaksi_paus.csv, blok.csv, btc_harga_5menit.csv                 │
└────────────────────────────────────────────────────────────────────┘
```

Lapisan 3 tidak tahu apa-apa soal file atau internet. Itu disengaja: fungsi yang hanya menerima
DataFrame dan mengembalikan DataFrame bisa diuji dengan data mini yang hasilnya bisa dihitung di kepala
(lihat `tests/test_analisis.py`).

---

## Langkah 1 — Satu transaksi Bitcoin itu bentuknya apa?

Buka `https://mempool.space/tx/<txid>` untuk salah satu baris di `data/transaksi_paus.csv`. Kamu akan
melihat dua kolom: **input** di kiri, **output** di kanan.

- Input = koin yang *dihabiskan*. Tiap input menunjuk ke output transaksi lama.
- Output = koin yang *dibuat*. Tiap output punya nilai (satoshi) dan alamat tujuan.
- Fee = total input − total output. Tidak tertulis di mana pun, selisihnya diambil penambang.

Satu hal yang mengejutkan pemula: **tidak ada "pengirim" dan "penerima"** di level protokol. Transaksi
dengan 1 input dan 2 output biasanya berarti "bayar ke alamat A, kembalian ke alamat saya sendiri", tetapi
blockchain tidak menandai mana yang kembalian. Itu sebabnya kolom `pola` di CSV hanya *tebakan*.

Coba di terminal Python (butuh internet):

```python
import requests
tx = requests.get("https://blockchain.info/rawtx/<txid>").json()
print(len(tx["inputs"]), len(tx["out"]))
print(sum(o["value"] for o in tx["out"]) / 1e8, "BTC")   # nilai dalam satoshi, 1 BTC = 100 juta satoshi
```

---

## Langkah 2 — Mengunduh satu blok utuh (`src/ambil_blok.py`)

Sebuah blok berisi 300 sampai 7.000 transaksi. Kalau kita mengambilnya 25 transaksi per request (cara
mempool.space), satu blok butuh ratusan request. `blockchain.info/rawblock/<hash>` memberi seluruh blok
dalam satu JSON (1–8 MB). Jadi alurnya:

1. Minta daftar blok terbaru ke mempool.space (`daftar_blok`). Ini murah: 15 blok per request.
2. Untuk tiap blok yang belum ada di `blok.csv`, unduh isinya (`ambil_isi_blok`).
3. Saring transaksi dengan total output ≥ 50 BTC (`saring_paus`), ubah jadi baris datar
   (`ringkas_transaksi`), simpan.

Perhatikan `perbarui_data` menyimpan ke CSV setiap 10 blok. Kalau internet putus di blok ke-200, kamu
tidak kehilangan 190 blok sebelumnya; jalankan ulang dan skrip melanjutkan dari yang belum ada. Pola
"aman dijalankan berulang" ini namanya **idempoten**, dan hampir semua skrip pengambil data yang baik
memilikinya.

### Kenapa ada `ringkas_transaksi` terpisah dari `saring_paus`?

Supaya bisa diuji. `tests/test_ambil_blok.py` membuat transaksi palsu dengan dua input (60 dan 50 BTC)
dan dua output (100 dan 9,9 BTC), lalu memeriksa bahwa fee, output terbesar, dan polanya benar. Tes itu
berjalan tanpa internet dalam sepersekian detik. Kalau semua logika ditaruh di dalam loop yang memanggil
`requests.get`, tes seperti itu mustahil.

---

## Langkah 3 — Menebak pola dari bentuk

```python
def klasifikasi_pola(jumlah_input, jumlah_output):
    if jumlah_input >= 3 and jumlah_output <= 2:
        return "konsolidasi"
    if jumlah_input <= 2 and jumlah_output >= 3:
        return "distribusi"
    return "transfer"
```

Tiga baris `if`, tetapi ada cerita di baliknya:

- **Konsolidasi** (banyak → sedikit). Bursa menerima ribuan setoran kecil ke banyak alamat. Sesekali
  mereka menyapu semuanya ke satu dompet besar. Penambang juga melakukan ini dengan hadiah blok.
- **Distribusi** (sedikit → banyak). Satu dompet panas bursa membayar puluhan penarikan nasabah dalam
  satu transaksi (lebih hemat fee daripada satu per satu). Ini yang sering disebut "koin keluar bursa".
- **Transfer** (sedikit → sedikit). Pindah dompet, transaksi OTC, atau kustodian menggeser dana. Paling
  sulit ditafsirkan, dan justru yang paling sering jadi bahan cuitan "paus bergerak!".

Kolom `bulat` menandai output yang tepat bilangan bulat BTC. Orang biasa jarang mengirim tepat 1.000 BTC;
sistem internal kustodian sering. Ini heuristik, bukan bukti.

---

## Langkah 4 — Menyambungkan waktu blok dengan harga (`merge_asof`)

Masalah: blok ditambang pada 07:19:43, tetapi candle harga ada di 07:15 dan 07:20. Harga "saat" transaksi
itu berapa? `pd.merge` biasa butuh kunci yang persis sama, jadi tidak bisa.

```python
pd.merge_asof(paus.sort_values("waktu"), harga[["waktu", "close"]], on="waktu", direction="backward")
```

`direction="backward"` berarti "ambil candle terakhir yang waktunya ≤ waktu blok", jadi 07:15. Kenapa
bukan 07:20? Karena candle 07:20 ditutup *setelah* transaksi; memakainya berarti mengintip masa depan.
Kesalahan ini (look-ahead bias) adalah penyebab paling umum "strategi" yang terlihat hebat di backtest
dan hancur di dunia nyata.

Fungsi `harga_pada` di `src/analisis.py` membungkus `merge_asof` supaya bisa dipanggil berulang: harga
saat blok, harga 15 menit setelahnya, 1 jam setelahnya, 4 jam setelahnya, dan 1 jam sebelumnya.

---

## Langkah 5 — Return dan kenapa kita pakai nilai mutlak

```python
r_60m = harga_pada(harga, waktu + 60 menit) / harga_saat - 1
```

Itu "berapa persen harga berubah satu jam setelah paus". Tetapi kalau kita rata-ratakan r_60m dari 500
transaksi, yang naik dan yang turun saling menghapus dan hasilnya mendekati nol, walau tiap gerakan
besar. Untuk mengukur *gejolak*, pakai |r_60m| (nilai mutlak). Untuk mengukur *arah*, pakai r_60m biasa
dan "% naik". Dashboard menampilkan keduanya karena menjawab pertanyaan yang berbeda:

- "Apakah harga bergerak setelah paus?" → |r|
- "Ke arah mana?" → r dan % naik

---

## Langkah 6 — Baseline: angka tanpa pembanding tidak berarti

Ini bagian terpenting di seluruh panduan.

Misalkan hasilnya "harga bergerak rata-rata 0,09% satu jam setelah paus". Bagus? Buruk? Tidak tahu,
sebelum kita tahu berapa harga bergerak satu jam setelah *sembarang* waktu. `baseline()` menghitung
return yang sama untuk **setiap** candle 5 menit di rentang yang dipilih. Kalau baseline-nya 0,10%,
maka paus sama sekali bukan sinyal: harga memang bergerak segitu, dengan atau tanpa paus.

Rasio `rata_abs_pct / baseline_abs_pct` di tabel dashboard merangkum ini dalam satu angka. Sekitar 1,0
berarti "tidak ada apa-apa". Jauh di atas 1 baru layak diselidiki (dan tetap bukan bukti sebab-akibat).

Kebiasaan "selalu tanya: dibandingkan dengan apa?" berlaku jauh di luar Bitcoin. Obat baru vs plasebo,
desain tombol baru vs tombol lama, semuanya pertanyaan yang sama.

---

## Langkah 7 — Agregasi per jam dan Spearman

`agregasi_per_jam` membuat tabel: satu baris per jam, berisi jumlah paus, total BTC, dan return jam
**berikutnya**. Kenapa jam berikutnya, bukan jam yang sama? Supaya urutannya jelas: aktivitas dulu, baru
harga. Kalau dipakai jam yang sama, kita tidak tahu mana yang lebih dulu.

Lalu korelasi. Satu transaksi 20.000 BTC bisa 100× lebih besar daripada paus biasa. Korelasi Pearson
memakai nilai asli, jadi satu titik ekstrem bisa menyeret hasilnya ke mana-mana. Spearman mengganti
nilai dengan **peringkat**, jadi 20.000 BTC hanya "peringkat 1", bukan 100× lebih berat.

```python
spearman = agg["btc_paus"].rank().corr(agg["abs_ret_berikut_pct"].rank())
```

Satu baris, tetapi hasilnya jauh lebih bisa dipercaya untuk data yang ekornya panjang (heavy-tailed),
dan hampir semua data keuangan seperti itu.

---

## Langkah 8 — Streamlit: klik titik, muncul kartu

```python
pilihan = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key="linimasa")
titik = pilihan["selection"]["points"]
```

Saat pengguna mengklik gelembung, Streamlit menjalankan ulang seluruh skrip dan `pilihan` berisi titik
yang diklik. Kita menitipkan `txid` di `customdata` tiap titik, jadi dari klik bisa ditemukan baris
transaksinya dan ditampilkan sebagai kartu. Tidak ada callback, tidak ada state rumit: Streamlit memang
mengulang skrip dari atas setiap ada interaksi, dan `@st.cache_data` menjaga supaya CSV tidak dibaca
ulang tiap kali.

---

## Langkah 9 — Tes: kontrak yang bisa dijalankan

Lihat `tests/test_analisis.py::test_hitung_reaksi_horizon_sederhana`. Harga palsu naik 1 dolar tiap
5 menit mulai dari 1.000. Paus bergerak di menit ke-120 (harga 1.024). Lima belas menit kemudian harga
1.027, jadi return-nya 3/1024. Angka itu bisa dihitung di kepala, dan tes memeriksa bahwa kodenya setuju.

Kalau suatu hari kamu mengganti `direction="backward"` menjadi `"nearest"` (kesalahan look-ahead dari
Langkah 4), tes ini langsung merah. Itulah gunanya tes: bukan membuktikan kode benar, tetapi membuat
kesalahan *terlihat*.

---

## Langkah 10 — Jujur soal keterbatasan

Dashboard ini sengaja menulis daftar keterbatasan di tab "Cara kerja". Tiga yang paling penting:

1. Korelasi bukan sebab-akibat. Paus dan harga bisa sama-sama bereaksi pada berita.
2. Tidak ada label alamat bursa. "Keluar bursa" vs "masuk bursa" hanya tebakan dari bentuk.
3. Data hanya beberapa hari. Minggu yang berbeda bisa memberi cerita yang berbeda.

Menulis keterbatasan bukan tanda proyeknya lemah. Justru sebaliknya: pembaca jadi tahu persis apa yang
bisa dan tidak bisa disimpulkan, dan itu membuat angka yang kamu sajikan lebih bisa dipercaya.

Selesai? Lanjut ke [LATIHAN.md](LATIHAN.md).
