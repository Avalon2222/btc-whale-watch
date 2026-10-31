"""
Tes untuk src/analisis.py. Jalankan:  python -m pytest tests/ -v

Pola tiap tes: SIAPKAN data kecil yang bisa dihitung di kepala -> PANGGIL fungsi
-> PERIKSA hasilnya. Harga palsu di bawah naik 1 dolar tiap 5 menit, jadi
return untuk horizon apa pun mudah dihitung tangan.
"""

import pandas as pd
import pytest

from src import analisis


def buat_harga(jumlah=300, mulai="2026-01-01 00:00", harga_awal=1000.0, langkah=1.0):
    """Candle 5 menit: close = harga_awal, harga_awal+langkah, ... (naik terus)."""
    waktu = pd.date_range(mulai, periods=jumlah, freq="5min")
    close = [harga_awal + i * langkah for i in range(jumlah)]
    return pd.DataFrame({"waktu": waktu, "open": close, "high": close, "low": close, "close": close, "volume": 1.0})


def buat_paus(waktu, total_btc=None, pola=None):
    waktu = pd.to_datetime(waktu)
    n = len(waktu)
    return pd.DataFrame({
        "txid": [f"tx{i}" for i in range(n)],
        "waktu": waktu,
        "tinggi_blok": range(n),
        "jumlah_input": 1,
        "jumlah_output": 2,
        "total_btc": total_btc if total_btc is not None else [100.0] * n,
        "input_btc": 100.0,
        "fee_btc": 0.0001,
        "output_terbesar_btc": 90.0,
        "alamat_terbesar": "bc1q",
        "pola": pola if pola is not None else ["transfer"] * n,
        "bulat": False,
    })


def test_harga_pada_mengambil_candle_terakhir_sebelum_waktu():
    harga = buat_harga()
    # 00:07 berada di antara candle 00:05 (1001) dan 00:10 (1002) -> ambil 00:05.
    hasil = analisis.harga_pada(harga, pd.Series(pd.to_datetime(["2026-01-01 00:07", "2026-01-01 00:00"])))
    assert hasil.iloc[0] == pytest.approx(1001.0)
    assert hasil.iloc[1] == pytest.approx(1000.0)


def test_harga_pada_di_luar_rentang_jadi_nan():
    harga = buat_harga(jumlah=10)
    hasil = analisis.harga_pada(harga, pd.Series(pd.to_datetime(["2025-12-31 23:00", "2026-01-02 00:00"])))
    assert hasil.isna().all()


def test_hitung_reaksi_horizon_sederhana():
    harga = buat_harga()                       # +1 dolar tiap 5 menit, mulai 1000
    paus = buat_paus(["2026-01-01 02:00"])     # candle ke-24 -> harga 1024
    r = analisis.hitung_reaksi(paus, harga, horizon=(15, 60))
    assert r["harga_saat"].iloc[0] == pytest.approx(1024.0)
    assert r["nilai_usd"].iloc[0] == pytest.approx(102400.0)
    assert r["r_15m_pct"].iloc[0] == pytest.approx(3 / 1024 * 100)    # 3 candle ke depan
    assert r["r_60m_pct"].iloc[0] == pytest.approx(12 / 1024 * 100)   # 12 candle ke depan
    assert r["r_sebelum_pct"].iloc[0] == pytest.approx((1024 / 1012 - 1) * 100)


def test_hitung_reaksi_paus_kosong_tetap_punya_kolom():
    r = analisis.hitung_reaksi(buat_paus([]), buat_harga(), horizon=(15,))
    assert list(r.columns)[-4:] == ["harga_saat", "nilai_usd", "r_sebelum_pct", "r_15m_pct"]
    assert r.empty


def test_ringkasan_reaksi_membandingkan_dengan_baseline():
    harga = buat_harga()
    paus = buat_paus(["2026-01-01 01:00", "2026-01-01 03:00"])
    reaksi = analisis.hitung_reaksi(paus, harga, horizon=(60,))
    pembanding = analisis.baseline(harga, horizon=(60,))
    ringkas = analisis.ringkasan_reaksi(reaksi, pembanding, horizon=(60,))
    assert len(ringkas) == 1
    baris = ringkas.iloc[0]
    assert baris["jumlah"] == 2
    assert baris["persen_naik"] == pytest.approx(100.0)        # harga selalu naik
    assert baris["rasio_vs_baseline"] > 0
    assert baris["rata_abs_pct"] == pytest.approx(baris["rata_rata_pct"])


def test_ringkasan_per_pola():
    harga = buat_harga()
    paus = buat_paus(["2026-01-01 01:00", "2026-01-01 02:00", "2026-01-01 03:00"],
                     total_btc=[100, 300, 50], pola=["transfer", "distribusi", "transfer"])
    reaksi = analisis.hitung_reaksi(paus, harga, horizon=(60,))
    per_pola = analisis.ringkasan_per_pola(reaksi, horizon_menit=60)
    assert per_pola["pola"].tolist() == ["distribusi", "transfer"]    # urut total_btc turun
    assert per_pola.set_index("pola").loc["transfer", "jumlah"] == 2
    assert per_pola.set_index("pola").loc["transfer", "total_btc"] == pytest.approx(150)


def test_agregasi_per_jam_memakai_return_jam_berikutnya():
    harga = buat_harga(jumlah=12 * 5)         # 5 jam penuh
    paus = buat_paus(["2026-01-01 01:10", "2026-01-01 01:50"], total_btc=[100, 200])
    agg = analisis.agregasi_per_jam(paus, harga)
    baris = agg.set_index("jam").loc[pd.Timestamp("2026-01-01 01:00")]
    assert baris["jumlah_paus"] == 2
    assert baris["btc_paus"] == pytest.approx(300)
    # close jam 01 = candle 01:55 = 1023; close jam 02 = 1035 -> +12/1023
    assert baris["ret_jam_berikut_pct"] == pytest.approx(12 / 1023 * 100)
    # Jam tanpa paus harus tetap ada dengan 0, bukan hilang.
    assert (agg["jumlah_paus"] == 0).sum() >= 2


def test_bandingkan_jam_memberi_nan_kalau_tidak_ada_variasi():
    harga = buat_harga(jumlah=12 * 5)
    agg = analisis.agregasi_per_jam(buat_paus([]), harga)
    hasil = analisis.bandingkan_jam(agg)
    assert hasil["jam_ada_paus"] == 0
    assert pd.isna(hasil["abs_ret_ada_paus"])
    assert pd.isna(hasil["korelasi_spearman"])


def test_bandingkan_jam_korelasi_sempurna():
    # Buat jam dengan paus makin besar dan gejolak makin besar -> Spearman = 1.
    jam = pd.date_range("2026-01-01", periods=5, freq="h")
    agg = pd.DataFrame({"jam": jam, "jumlah_paus": [0, 1, 2, 3, 4], "btc_paus": [0, 10, 20, 30, 40],
                        "abs_ret_berikut_pct": [0.1, 0.2, 0.3, 0.4, 0.5]})
    hasil = analisis.bandingkan_jam(agg)
    assert hasil["korelasi_spearman"] == pytest.approx(1.0)
    assert hasil["jam_ada_paus"] == 4 and hasil["jam_tanpa_paus"] == 1


def test_singkat_txid():
    assert analisis.singkat_txid("abcdefghijklmnopqrstuvwxyz") == "abcdefgh…wxyz"
    assert analisis.singkat_txid("pendek") == "pendek"
