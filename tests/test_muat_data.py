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
