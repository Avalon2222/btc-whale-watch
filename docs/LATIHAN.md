# 🏋️ Latihan

Urut dari yang paling mudah. Bintang = tingkat kesulitan. Tiap latihan punya petunjuk dan cara mengecek
jawabanmu. Kerjakan di branch baru (`git checkout -b latihan-1`) supaya kalau ada yang rusak kamu bisa
kembali dengan mudah. Jalankan `python -m pytest tests/ -v` setelah tiap latihan.

---

### Latihan 1 — Buka transaksi terbesar ⭐

Di tab **Daftar paus**, urutkan berdasarkan BTC dan klik "buka ↗" pada baris teratas. Di mempool.space,
jawab tiga pertanyaan: berapa input, berapa output, dan berapa fee-nya dalam dolar? Bandingkan dengan
kolom `jumlah_input`, `jumlah_output`, `fee_btc` di CSV. Kalau ada yang beda, cari tahu kenapa
(petunjuk: baca `ringkas_transaksi` di `src/ambil_blok.py`, bagian input tanpa `prev_out`).

**Cek:** kamu bisa menjelaskan dengan kalimatmu sendiri kenapa fee tidak pernah tertulis di output.

---

### Latihan 2 — Ganti ambang simpan ⭐

`AMBANG_SIMPAN_BTC = 50.0` di `src/ambil_blok.py` menentukan transaksi mana yang masuk CSV. Ubah jadi
`25.0`, lalu jalankan `python -m src.ambil_blok --jam 1`. Berapa baris baru yang muncul? Berapa besar
file CSV sekarang?

Tulis di komentar atas konstanta itu: menurutmu ambang berapa yang pas untuk disebut "paus", dan kenapa.
Perhatikan slider di app punya batas bawah 50; ubah juga `min_value` di `app.py` supaya konsisten.

---

### Latihan 3 — Nilai dalam dolar ⭐⭐

Kolom `nilai_usd` dihitung dari `total_btc × harga_saat`. Tambahkan kolom **`fee_usd`** di
`hitung_reaksi` (`src/analisis.py`), lalu tampilkan di tab Daftar paus. Transaksi 20.000 BTC membayar
fee berapa dolar? Bandingkan dengan biaya transfer bank untuk jumlah yang sama.

**Cek:** tambahkan satu tes di `tests/test_analisis.py` dengan harga palsu 1.000 dolar dan fee 0,001 BTC;
`fee_usd` harus 1,0.

---

### Latihan 4 — Horizon baru: 24 jam ⭐⭐

`HORIZON_MENIT = (15, 60, 240)` di `src/analisis.py`. Tambahkan 1440 (24 jam). Dua hal akan terjadi:

1. Tab Dampak otomatis menampilkan batang keempat (perhatikan `for h in HORIZON` di `app.py`).
2. Banyak transaksi di hari terakhir mendapat `NaN`, karena harga 24 jam setelahnya belum ada.

Jalankan `python -m src.ambil_harga --jam 120` supaya harga lebih panjang. Lalu jawab: apakah rasio vs
baseline di horizon 24 jam lebih besar atau lebih kecil daripada di 1 jam? Kenapa menurutmu begitu?

---

### Latihan 5 — Pola keempat: "banyak ke banyak" ⭐⭐

`klasifikasi_pola` memasukkan transaksi 10 input → 10 output ke "transfer". Padahal bentuk itu khas
**CoinJoin** atau bursa yang menggabungkan setoran dan penarikan sekaligus. Tambahkan pola `campuran`
untuk input ≥ 3 dan output ≥ 3.

Yang perlu diubah: `klasifikasi_pola`, `POLA_VALID` di `src/muat_data.py`, `WARNA_POLA` dan `LABEL_POLA`
di `app.py`, dan tes di `tests/test_ambil_blok.py`. Pilih warna dari palet yang sudah ada
(`#eda100` kuning masih bebas). Setelah itu jalankan `python -m src.ambil_blok --jam 6` dan lihat berapa
persen transaksi yang masuk pola baru.

**Cek:** `muat_paus()` pada CSV lama (yang belum punya pola `campuran`) harus tetap jalan.

---

### Latihan 6 — Distribusi, bukan rata-rata ⭐⭐⭐

Rata-rata |return| bisa menyesatkan kalau satu dua transaksi kebetulan terjadi saat harga melonjak.
Tambahkan di tab Dampak sebuah **histogram** `r_60m_pct` untuk transaksi paus, ditumpuk dengan histogram
`r_60m_pct` dari baseline (keduanya dinormalisasi jadi persentase, `histnorm="percent"` di Plotly).
Kalau dua bentuknya menumpuk rapi, paus tidak memberi informasi apa pun.

Petunjuk: `go.Histogram(x=..., histnorm="percent", opacity=0.6)` dua kali, `barmode="overlay"`.

---

### Latihan 7 — Uji beda yang sesungguhnya ⭐⭐⭐

Rasio 1,1× itu "beda" atau cuma kebetulan? Tambahkan fungsi `uji_permutasi(reaksi, pembanding, n=2000)`
di `src/analisis.py`:

1. Hitung selisih rata-rata |r_60m| paus dikurangi baseline (nilai asli).
2. Gabungkan kedua kumpulan nilai, acak urutannya, bagi dua dengan ukuran yang sama seperti semula,
   hitung selisihnya. Ulangi n kali.
3. p-value = porsi pengulangan yang selisihnya ≥ selisih asli.

Tampilkan p-value di bawah tabel. Tulis tes dengan dua kumpulan yang jelas berbeda (p harus kecil) dan
dua kumpulan yang identik (p harus besar). Tidak perlu scipy; `numpy.random.default_rng` cukup.

---

### Latihan 8 — Label alamat bursa ⭐⭐⭐

Keterbatasan terbesar dashboard: tidak tahu alamat mana milik bursa. Buat `data/alamat_dikenal.csv`
dengan kolom `alamat, nama, jenis` dan isi 10–20 alamat dompet dingin bursa besar yang dipublikasikan
(cari "proof of reserves addresses"; verifikasi di explorer bahwa saldonya memang besar). Lalu:

1. Di `ringkas_transaksi`, tambahkan kolom `alamat_input_pertama`.
2. Di `src/analisis.py`, buat `label_arah(paus, alamat_dikenal)` yang mengisi kolom `arah` dengan
   `masuk_bursa`, `keluar_bursa`, atau `tidak_diketahui`.
3. Di tab Dampak, bandingkan % naik untuk `masuk_bursa` vs `keluar_bursa`.

Ini yang dijual banyak layanan "on-chain analytics" berbayar. Versi kecilnya bisa kamu buat sendiri.

---

### Latihan 9 — Mempool, bukan blok ⭐⭐⭐⭐

Transaksi terlihat di mempool beberapa menit *sebelum* masuk blok. Kalau paus benar-benar menggerakkan
harga, reaksinya mungkin sudah terjadi sebelum waktu blok, dan dashboard ini melewatkannya.

Buat `src/pantau_mempool.py` yang setiap 30 detik memanggil `https://mempool.space/api/mempool/txids`
(atau WebSocket `wss://mempool.space/api/v1/ws`), mengambil detail transaksi baru dengan
`https://mempool.space/api/tx/<txid>`, dan mencatat transaksi ≥ 50 BTC beserta **waktu pertama kali
terlihat**. Jalankan beberapa jam, lalu bandingkan `waktu_terlihat` dengan `waktu` blok di CSV. Berapa
menit rata-rata jedanya? Apakah reaksi harga yang dihitung dari `waktu_terlihat` berbeda?

Ini latihan paling panjang, tetapi hasilnya proyek yang benar-benar baru: dashboard waktu nyata.
