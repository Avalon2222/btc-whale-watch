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


def _bendera(nilai: object) -> bool:
    """Bendera CSV jadi bool: True/"true"/"1"/"ya" -> True, selain itu (termasuk kosong) -> False."""
    if isinstance(nilai, str):
        return nilai.strip().lower() in {"true", "1", "1.0", "ya", "yes"}
    return bool(nilai) if pd.notna(nilai) else False


def muat_paus(path: Path = PATH_PAUS, ambang_btc: float = 0.0) -> pd.DataFrame:
    """Baca transaksi paus, urut berdasarkan waktu, saring >= ambang_btc."""
    df = pd.read_csv(path, parse_dates=["waktu"])
    _periksa_kolom(df, KOLOM_PAUS, path.name)
    # Waktu yang rusak membuat kolomnya tersimpan sebagai teks dan hitung_reaksi gagal;
    # transaksi tanpa waktu tidak bisa disandingkan dengan harga, jadi dibuang.
    df = df.assign(waktu=pd.to_datetime(df["waktu"], errors="coerce")).dropna(subset=["waktu"])
    # Pola dirapikan dulu (spasi, huruf besar) supaya " Transfer" tidak dianggap pola baru.
    df["pola"] = df["pola"].astype("string").str.strip().str.lower()
    salah = set(df["pola"].dropna().unique()) - set(POLA_VALID)
    if df["pola"].isna().any():
        salah.add("<kosong>")
    if salah:
        raise ValueError(f"{path.name}: pola tidak dikenal {sorted(salah)}; yang boleh {POLA_VALID}")
    df["pola"] = df["pola"].astype(str)
    df["alamat_terbesar"] = df["alamat_terbesar"].fillna("")
    # NaN.astype(bool) jadi True, dan teks "False"/"0" juga jadi True; baca maknanya, bukan isinya ada atau tidak.
    df["bulat"] = df["bulat"].map(_bendera)
    # total_btc berupa teks rusak atau inf dibuang; inf membuat nilai USD dan peringkat paus kacau.
    total = pd.to_numeric(df["total_btc"], errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
    df = df.assign(total_btc=total)
    df = df[df["total_btc"] >= ambang_btc]
    # txid yang sama tercatat dua kali (misalnya hasil gabung CSV manual) tidak boleh dihitung ganda.
    df = df.drop_duplicates("txid")
    # Transaksi dari blok yang sama berbagi waktu; mergesort menjaga urutan di CSV.
    return df.sort_values("waktu", kind="mergesort").reset_index(drop=True)


def muat_harga(path: Path = PATH_HARGA) -> pd.DataFrame:
    """Baca candle 5 menit, urut, buang duplikat."""
    df = pd.read_csv(path, parse_dates=["waktu"])
    _periksa_kolom(df, KOLOM_HARGA, path.name)
    # Candle tanpa waktu atau tanpa harga tidak bisa dipakai merge_asof.
    # Harga inf juga dianggap kosong; kalau lolos, nilai USD dan return ikut jadi inf.
    # Teks rusak ("-", "n.a.") juga dianggap kosong; kalau tidak, cek close <= 0 di bawah gagal dengan TypeError.
    close = pd.to_numeric(df["close"], errors="coerce")
    # Satu waktu yang rusak membuat read_csv menyerah dan menyimpan seluruh kolom sebagai teks,
    # sehingga merge_asof di analisis gagal; ubah per nilai dan buang yang tidak terbaca.
    waktu = pd.to_datetime(df["waktu"], errors="coerce")
    df = df.assign(waktu=waktu, close=close.replace([float("inf"), float("-inf")], float("nan")))
    df = df.dropna(subset=["waktu", "close"])
    # Sama seperti ambil_harga.perbarui_csv: candle yang muncul belakangan (unduhan terbaru) yang dipakai.
    df = df.drop_duplicates("waktu", keep="last").sort_values("waktu").reset_index(drop=True)
    if (df["close"] <= 0).any():
        raise ValueError(f"{path.name}: ada harga close <= 0")
    return df


def muat_blok(path: Path = PATH_BLOK) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["waktu"])
    _periksa_kolom(df, KOLOM_BLOK, path.name)
    # Blok yang tercatat dua kali (CSV digabung manual) membuat jumlah blok & rentang jam ikut dobel.
    df = df.dropna(subset=["tinggi"]).drop_duplicates("tinggi", keep="last")
    return df.sort_values("tinggi").reset_index(drop=True)
