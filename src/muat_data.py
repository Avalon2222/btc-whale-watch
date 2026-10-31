"""
muat_data.py - Membaca CSV di folder data/ dan memastikan bentuknya benar.

Semua fungsi di sini hanya membaca file lokal, tidak menyentuh internet.
Kalau kolom yang diharapkan tidak ada, fungsi langsung berhenti dengan pesan
yang jelas. Lebih baik gagal di awal daripada menghasilkan chart yang salah.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"
PATH_PAUS = FOLDER_DATA / "transaksi_paus.csv"
PATH_BLOK = FOLDER_DATA / "blok.csv"
PATH_HARGA = FOLDER_DATA / "btc_harga_5menit.csv"

POLA_VALID = ("konsolidasi", "distribusi", "transfer")

KOLOM_PAUS = [
    "txid", "waktu", "tinggi_blok", "jumlah_input", "jumlah_output",
    "total_btc", "input_btc", "fee_btc", "output_terbesar_btc",
    "alamat_terbesar", "pola", "bulat",
]
KOLOM_HARGA = ["waktu", "open", "high", "low", "close", "volume"]
KOLOM_BLOK = ["tinggi", "hash", "waktu", "jumlah_tx", "jumlah_paus", "btc_paus"]


def _periksa_kolom(df: pd.DataFrame, kolom: list[str], nama: str) -> None:
    hilang = [k for k in kolom if k not in df.columns]
    if hilang:
        raise ValueError(f"{nama}: kolom {hilang} tidak ditemukan. Kolom yang ada: {list(df.columns)}")


def muat_paus(path: Path = PATH_PAUS, ambang_btc: float = 0.0) -> pd.DataFrame:
    """Baca transaksi paus, urut berdasarkan waktu, saring >= ambang_btc."""
    df = pd.read_csv(path, parse_dates=["waktu"])
    _periksa_kolom(df, KOLOM_PAUS, path.name)
    salah = set(df["pola"].unique()) - set(POLA_VALID)
    if salah:
        raise ValueError(f"{path.name}: pola tidak dikenal {sorted(salah)}; yang boleh {POLA_VALID}")
    df["alamat_terbesar"] = df["alamat_terbesar"].fillna("")
    df["bulat"] = df["bulat"].astype(bool)
    df = df[df["total_btc"] >= ambang_btc]
    return df.sort_values("waktu").reset_index(drop=True)


def muat_harga(path: Path = PATH_HARGA) -> pd.DataFrame:
    """Baca candle 5 menit, urut, buang duplikat."""
    df = pd.read_csv(path, parse_dates=["waktu"])
    _periksa_kolom(df, KOLOM_HARGA, path.name)
    df = df.drop_duplicates("waktu").sort_values("waktu").reset_index(drop=True)
    if (df["close"] <= 0).any():
        raise ValueError(f"{path.name}: ada harga close <= 0")
    return df


def muat_blok(path: Path = PATH_BLOK) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["waktu"])
    _periksa_kolom(df, KOLOM_BLOK, path.name)
    return df.sort_values("tinggi").reset_index(drop=True)
