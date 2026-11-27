"""
Tes untuk src/muat_data.py: file contoh di data/ harus bisa dibaca, dan file
yang bentuknya salah harus ditolak dengan pesan jelas.
"""

import pandas as pd
import pytest

from src import muat_data


def test_data_contoh_bisa_dibaca():
    paus = muat_data.muat_paus()
    harga = muat_data.muat_harga()
    blok = muat_data.muat_blok()
    assert len(paus) > 0 and len(harga) > 0 and len(blok) > 0
    assert paus["waktu"].is_monotonic_increasing
    assert harga["waktu"].is_monotonic_increasing
    # Harga harus menutupi seluruh rentang blok, kalau tidak reaksi tidak bisa dihitung.
    # (candle terakhir boleh tertinggal < 5 menit dari blok terakhir, karena candle dibuat per 5 menit)
    assert harga["waktu"].min() <= blok["waktu"].min()
    assert harga["waktu"].max() >= blok["waktu"].max() - pd.Timedelta(minutes=5)


def test_ambang_menyaring():
    semua = muat_data.muat_paus(ambang_btc=0)
    besar = muat_data.muat_paus(ambang_btc=500)
    assert len(besar) <= len(semua)
    assert (besar["total_btc"] >= 500).all()


def test_pola_tidak_dikenal_ditolak(tmp_path):
    df = pd.DataFrame([{k: 0 for k in muat_data.KOLOM_PAUS}])
    df["txid"] = "a"
    df["waktu"] = "2026-01-01 00:00:00"
    df["pola"] = "misterius"
    path = tmp_path / "paus.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="misterius"):
        muat_data.muat_paus(path)


def test_kolom_hilang_ditolak(tmp_path):
    path = tmp_path / "harga.csv"
    pd.DataFrame({"waktu": ["2026-01-01"], "close": [1.0]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="tidak ditemukan"):
        muat_data.muat_harga(path)


def test_bulat_kosong_dianggap_false(tmp_path):
    df = pd.DataFrame([{k: 0 for k in muat_data.KOLOM_PAUS} for _ in range(2)])
    df["txid"] = ["a", "b"]
    df["waktu"] = "2026-01-01 00:00:00"
    df["pola"] = "transfer"
    df["bulat"] = [True, None]
    path = tmp_path / "paus.csv"
    df.to_csv(path, index=False)
    hasil = muat_data.muat_paus(path)
    assert hasil.set_index("txid")["bulat"].to_dict() == {"a": True, "b": False}


def test_candle_tanpa_waktu_atau_harga_dibuang(tmp_path):
    path = tmp_path / "harga.csv"
    pd.DataFrame({
        "waktu": ["2026-01-01 00:00", "", "2026-01-01 00:10"],
        "open": [1.0, 1.0, 1.0], "high": [1.0, 1.0, 1.0], "low": [1.0, 1.0, 1.0],
        "close": [100.0, 101.0, None], "volume": [1, 1, 1],
    }).to_csv(path, index=False)
    hasil = muat_data.muat_harga(path)
    assert len(hasil) == 1
    assert hasil["close"].iloc[0] == 100.0


def _tulis_paus(tmp_path, pola):
    df = pd.DataFrame([{k: 0 for k in muat_data.KOLOM_PAUS} for _ in pola])
    df["txid"] = [f"t{i}" for i in range(len(pola))]
    df["waktu"] = "2026-01-01 00:00:00"
    df["pola"] = pola
    path = tmp_path / "paus.csv"
    df.to_csv(path, index=False)
    return path


def test_pola_dirapikan_dari_spasi_dan_huruf_besar(tmp_path):
    path = _tulis_paus(tmp_path, [" Transfer", "KONSOLIDASI"])
    assert list(muat_data.muat_paus(path)["pola"]) == ["transfer", "konsolidasi"]


def test_pola_kosong_ditolak_dengan_pesan_jelas(tmp_path):
    path = _tulis_paus(tmp_path, ["transfer", None, "aneh"])
    with pytest.raises(ValueError, match="kosong"):
        muat_data.muat_paus(path)


def test_txid_ganda_hanya_dihitung_sekali(tmp_path):
    df = pd.DataFrame([{k: 0 for k in muat_data.KOLOM_PAUS} for _ in range(3)])
    df["txid"] = ["a", "a", "b"]
    df["waktu"] = "2026-01-01 00:00:00"
    df["pola"] = "transfer"
    df["total_btc"] = 100.0
    path = tmp_path / "paus.csv"
    df.to_csv(path, index=False)
    hasil = muat_data.muat_paus(path)
    assert sorted(hasil["txid"]) == ["a", "b"]


def test_paus_waktu_sama_urutan_csv_tetap(tmp_path):
    baris = []
    for i in range(120):
        r = {k: 0 for k in muat_data.KOLOM_PAUS}
        r.update(txid=f"t{i:03d}", waktu=f"2026-01-01 00:{10 * (i % 3):02d}:00", pola="transfer", total_btc=100)
        baris.append(r)
    path = tmp_path / "paus.csv"
    pd.DataFrame(baris).to_csv(path, index=False)
    hasil = muat_data.muat_paus(path)
    harapan = [r["txid"] for r in sorted(baris, key=lambda r: r["waktu"])]
    assert hasil["txid"].tolist() == harapan


def test_candle_harga_inf_dibuang(tmp_path):
    path = tmp_path / "harga.csv"
    pd.DataFrame({
        "waktu": ["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 00:10"],
        "open": [1.0, 1.0, 1.0], "high": [1.0, 1.0, 1.0], "low": [1.0, 1.0, 1.0],
        "close": [100.0, float("inf"), 102.0], "volume": [1, 1, 1],
    }).to_csv(path, index=False)
    hasil = muat_data.muat_harga(path)
    assert hasil["close"].tolist() == [100.0, 102.0]


def test_candle_waktu_ganda_pakai_yang_terbaru(tmp_path):
    path = tmp_path / "harga.csv"
    pd.DataFrame({
        "waktu": ["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 00:00"],
        "open": 1.0, "high": 1.0, "low": 1.0, "close": [100.0, 101.0, 105.0], "volume": 1.0,
    }).to_csv(path, index=False)
    hasil = muat_data.muat_harga(path)
    assert hasil["close"].tolist() == [105.0, 101.0]


def test_blok_ganda_dan_tanpa_tinggi_dibuang(tmp_path):
    path = tmp_path / "blok.csv"
    pd.DataFrame({
        "tinggi": [900001, 900000, 900001, None],
        "hash": ["b", "a", "b", "x"],
        "waktu": ["2026-01-01 00:10", "2026-01-01 00:00", "2026-01-01 00:10", "2026-01-01 00:20"],
        "jumlah_tx": [10, 20, 10, 5],
        "jumlah_paus": [1, 2, 1, 0],
        "btc_paus": [60.0, 120.0, 60.0, 0.0],
    }).to_csv(path, index=False)
    hasil = muat_data.muat_blok(path)
    assert hasil["tinggi"].tolist() == [900000, 900001]
    assert hasil["jumlah_paus"].sum() == 3


def test_bulat_teks_false_atau_nol_tetap_false(tmp_path):
    df = pd.DataFrame([{k: 0 for k in muat_data.KOLOM_PAUS} for _ in range(4)])
    df["txid"] = ["a", "b", "c", "d"]
    df["waktu"] = "2026-01-01 00:00:00"
    df["pola"] = "transfer"
    df["bulat"] = ["True", "0", "false", None]
    path = tmp_path / "paus.csv"
    df.to_csv(path, index=False)
    hasil = muat_data.muat_paus(path)
    assert hasil.set_index("txid")["bulat"].to_dict() == {"a": True, "b": False, "c": False, "d": False}


def test_total_btc_inf_atau_teks_dibuang(tmp_path):
    df = pd.DataFrame([{k: 0 for k in muat_data.KOLOM_PAUS} for _ in range(3)])
    df["txid"] = ["a", "b", "c"]
    df["waktu"] = "2026-01-01 00:00:00"
    df["pola"] = "transfer"
    df["total_btc"] = ["150", "inf", "rusak"]
    path = tmp_path / "paus.csv"
    df.to_csv(path, index=False)
    hasil = muat_data.muat_paus(path, ambang_btc=100)
    assert hasil["txid"].tolist() == ["a"]
    assert hasil["total_btc"].tolist() == [150.0]


def test_candle_harga_teks_rusak_dibuang(tmp_path):
    path = tmp_path / "harga.csv"
    pd.DataFrame({
        "waktu": ["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 00:10"],
        "open": [1.0, 1.0, 1.0], "high": [1.0, 1.0, 1.0], "low": [1.0, 1.0, 1.0],
        "close": ["100.0", "-", "102.5"], "volume": [1, 1, 1],
    }).to_csv(path, index=False)
    hasil = muat_data.muat_harga(path)
    assert hasil["close"].tolist() == [100.0, 102.5]
