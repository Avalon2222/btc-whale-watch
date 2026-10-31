"""
ambil_harga.py - Mengunduh harga Bitcoin per 5 menit dari Coinbase.

Kenapa Coinbase, bukan Binance atau Yahoo?
  - Binance memblokir request dari beberapa negara (dari sini jawabannya 403).
  - Yahoo Finance hanya memberi harga harian. Untuk mengukur reaksi 15 menit
    setelah sebuah transaksi, kita butuh candle yang jauh lebih rapat.
  - Coinbase Exchange punya endpoint candle publik, gratis, tanpa API key,
    maksimal 300 candle per request. Jadi satu hari (288 candle) = satu request.

Cara pakai dari terminal:
    python -m src.ambil_harga                # lengkapi data/btc_harga_5menit.csv
                                             # sampai menutupi semua blok di blok.csv
    python -m src.ambil_harga --jam 72       # 72 jam ke belakang dari sekarang
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

URL_COINBASE = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
HEADER = {"User-Agent": "Mozilla/5.0 (btc-whale-watch; belajar Python)"}
FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"
PATH_HARGA = FOLDER_DATA / "btc_harga_5menit.csv"
PATH_BLOK = FOLDER_DATA / "blok.csv"

MENIT = 5
KOLOM = ["waktu", "open", "high", "low", "close", "volume"]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ambil_candle(mulai: datetime, sampai: datetime) -> pd.DataFrame:
    """Unduh candle 5 menit antara dua waktu UTC (naive). Dipecah per 24 jam."""
    potongan = []
    kursor = mulai
    while kursor < sampai:
        akhir = min(kursor + timedelta(hours=24), sampai)
        params = {"granularity": MENIT * 60, "start": _iso(kursor), "end": _iso(akhir)}
        r = requests.get(URL_COINBASE, params=params, headers=HEADER, timeout=30)
        r.raise_for_status()
        # Format Coinbase: [waktu_unix, low, high, open, close, volume], terbaru dulu.
        df = pd.DataFrame(r.json(), columns=["waktu", "low", "high", "open", "close", "volume"])
        potongan.append(df)
        kursor = akhir
        time.sleep(0.3)  # sopan ke server
    if not potongan:
        return pd.DataFrame(columns=KOLOM)
    df = pd.concat(potongan, ignore_index=True)
    df["waktu"] = pd.to_datetime(df["waktu"], unit="s")
    df = df.drop_duplicates("waktu").sort_values("waktu").reset_index(drop=True)
    return df[KOLOM]


def perbarui_csv(jam: float | None = None, path: Path = PATH_HARGA) -> pd.DataFrame:
    """Lengkapi CSV harga supaya menutupi rentang blok (plus 4 jam setelahnya).

    Kalau `jam` diisi, rentangnya dihitung dari sekarang ke belakang.
    """
    sekarang = datetime.now(tz=timezone.utc).replace(tzinfo=None, second=0, microsecond=0)
    if jam is not None:
        mulai, sampai = sekarang - timedelta(hours=jam), sekarang
    elif PATH_BLOK.exists():
        blok = pd.read_csv(PATH_BLOK, parse_dates=["waktu"])
        mulai = blok["waktu"].min() - timedelta(hours=2)
        sampai = min(blok["waktu"].max() + timedelta(hours=4, minutes=10), sekarang)
    else:
        mulai, sampai = sekarang - timedelta(hours=24), sekarang

    lama = pd.read_csv(path, parse_dates=["waktu"]) if path.exists() else pd.DataFrame(columns=KOLOM)
    if len(lama):
        # Hanya unduh bagian yang belum ada: sebelum candle pertama dan sesudah candle terakhir.
        potongan = []
        if mulai < lama["waktu"].min():
            potongan.append(ambil_candle(mulai, lama["waktu"].min()))
        if sampai > lama["waktu"].max():
            potongan.append(ambil_candle(lama["waktu"].max(), sampai))
        baru = pd.concat(potongan, ignore_index=True) if potongan else pd.DataFrame(columns=KOLOM)
    else:
        baru = ambil_candle(mulai, sampai)

    df = pd.concat([lama, baru], ignore_index=True)
    df = df.drop_duplicates("waktu").sort_values("waktu").reset_index(drop=True)
    df.to_csv(path, index=False)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unduh harga BTC-USD per 5 menit dari Coinbase.")
    parser.add_argument("--jam", type=float, default=None, help="jam ke belakang dari sekarang")
    args = parser.parse_args()
    data = perbarui_csv(jam=args.jam)
    print(f"OK: {len(data)} candle, {data['waktu'].min()} s.d. {data['waktu'].max()}, disimpan ke {PATH_HARGA}")
