"""
ambil_blok.py - Mengunduh blok Bitcoin terbaru dan menyaring transaksi besar ("paus").

Dua API publik dipakai, keduanya gratis dan tanpa API key:
  - mempool.space   : daftar blok terbaru (tinggi, hash, waktu, jumlah transaksi).
  - blockchain.info : isi lengkap satu blok (semua transaksi beserta input dan
                      output) dalam SATU request. mempool.space juga bisa, tetapi
                      hanya 25 transaksi per halaman, sehingga satu blok butuh
                      ratusan request.

Hasilnya dua CSV di folder data/:
  - blok.csv            : satu baris per blok yang sudah diproses (ringkasan).
  - transaksi_paus.csv  : satu baris per transaksi dengan total output >= AMBANG_SIMPAN_BTC.

Cara pakai dari terminal:
    python -m src.ambil_blok                 # tambah blok yang belum ada, 6 jam ke belakang
    python -m src.ambil_blok --jam 48        # kira-kira 48 jam ke belakang

Cara pakai dari kode:
    from src.ambil_blok import perbarui_data
    blok, paus = perbarui_data(jam=1)
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

URL_MEMPOOL = "https://mempool.space/api/v1/blocks"
URL_BLOK = "https://blockchain.info/rawblock/{hash}"
HEADER = {"User-Agent": "Mozilla/5.0 (btc-whale-watch; belajar Python)"}

FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"
PATH_BLOK = FOLDER_DATA / "blok.csv"
PATH_PAUS = FOLDER_DATA / "transaksi_paus.csv"

SATOSHI = 100_000_000
# Transaksi di bawah angka ini tidak disimpan ke CSV supaya filenya tetap kecil.
# Slider di app tidak bisa turun lebih rendah dari ini.
AMBANG_SIMPAN_BTC = 50.0

KOLOM_BLOK = ["tinggi", "hash", "waktu", "jumlah_tx", "jumlah_paus", "btc_paus"]
KOLOM_PAUS = [
    "txid", "waktu", "tinggi_blok", "jumlah_input", "jumlah_output",
    "total_btc", "input_btc", "fee_btc", "output_terbesar_btc",
    "alamat_terbesar", "pola", "bulat",
]


# ---------------------------------------------------------------------------
# Bagian 1: logika murni (tanpa internet), mudah diuji
# ---------------------------------------------------------------------------

def klasifikasi_pola(jumlah_input: int, jumlah_output: int) -> str:
    """Tebak "bentuk" transaksi dari jumlah input dan output.

    - konsolidasi : banyak input menjadi sedikit output. Biasanya bursa atau
                    kustodian merapikan saldo, atau penambang mengumpulkan hasil.
    - distribusi  : sedikit input menjadi banyak output. Biasanya penarikan
                    massal dari bursa (satu dompet panas membayar banyak orang).
    - transfer    : sedikit ke sedikit. Pemindahan antar dompet, paling misterius.
    """
    if jumlah_input >= 3 and jumlah_output <= 2:
        return "konsolidasi"
    if jumlah_input <= 2 and jumlah_output >= 3:
        return "distribusi"
    return "transfer"


def nilai_bulat(btc: float) -> bool:
    """True kalau nilainya bilangan bulat BTC (misalnya tepat 1000 BTC).

    Transfer internal kustodian sering memakai angka bulat; transaksi orang
    biasa hampir tidak pernah, karena sisa kembalian membuat angkanya pecahan.
    """
    return abs(btc - round(btc)) < 1e-6


def ringkas_transaksi(tx: dict, waktu_blok: int, tinggi: int) -> dict:
    """Ubah satu transaksi mentah (format blockchain.info) menjadi satu baris datar."""
    outputs = tx.get("out", [])
    inputs = [i for i in tx.get("inputs", []) if i.get("prev_out") and i["prev_out"].get("value")]
    total_out = sum(o.get("value", 0) for o in outputs) / SATOSHI
    total_in = sum(i["prev_out"]["value"] for i in inputs) / SATOSHI
    terbesar = max(outputs, key=lambda o: o.get("value", 0)) if outputs else {}
    out_terbesar = terbesar.get("value", 0) / SATOSHI
    return {
        "txid": tx["hash"],
        "waktu": datetime.fromtimestamp(waktu_blok, tz=timezone.utc).replace(tzinfo=None),
        "tinggi_blok": tinggi,
        "jumlah_input": len(inputs),
        "jumlah_output": len(outputs),
        "total_btc": round(total_out, 8),
        "input_btc": round(total_in, 8),
        "fee_btc": round(tx.get("fee", 0) / SATOSHI, 8),
        "output_terbesar_btc": round(out_terbesar, 8),
        "alamat_terbesar": terbesar.get("addr", "") or "",
        "pola": klasifikasi_pola(len(inputs), len(outputs)),
        "bulat": nilai_bulat(out_terbesar),
    }


def saring_paus(blok: dict, ambang_btc: float = AMBANG_SIMPAN_BTC) -> list[dict]:
    """Dari satu blok mentah, ambil transaksi yang total outputnya >= ambang_btc.

    Transaksi coinbase (hadiah penambang, input tanpa prev_out) ikut dinilai
    seperti transaksi lain; hadiah blok saat ini jauh di bawah 50 BTC sehingga
    praktis tidak pernah lolos.
    """
    hasil = []
    for tx in blok.get("tx", []):
        total_out = sum(o.get("value", 0) for o in tx.get("out", [])) / SATOSHI
        if total_out >= ambang_btc:
            hasil.append(ringkas_transaksi(tx, blok["time"], blok["height"]))
    return hasil


def ringkas_blok(blok: dict, paus: list[dict]) -> dict:
    return {
        "tinggi": blok["height"],
        "hash": blok["hash"],
        "waktu": datetime.fromtimestamp(blok["time"], tz=timezone.utc).replace(tzinfo=None),
        "jumlah_tx": blok.get("n_tx", len(blok.get("tx", []))),
        "jumlah_paus": len(paus),
        "btc_paus": round(sum(p["total_btc"] for p in paus), 8),
    }


# ---------------------------------------------------------------------------
# Bagian 2: akses internet
# ---------------------------------------------------------------------------

def daftar_blok(sampai_waktu: int, mulai_tinggi: int | None = None) -> list[dict]:
    """Daftar blok dari yang terbaru mundur sampai timestamp < sampai_waktu.

    mempool.space memberi 15 blok per halaman; halaman berikutnya diminta
    dengan /blocks/{tinggi} (blok itu dan 14 di bawahnya).
    """
    hasil: list[dict] = []
    url = URL_MEMPOOL if mulai_tinggi is None else f"{URL_MEMPOOL}/{mulai_tinggi}"
    while True:
        r = requests.get(url, headers=HEADER, timeout=30)
        r.raise_for_status()
        halaman = r.json()
        if not halaman:
            return hasil
        for b in halaman:
            if b["timestamp"] < sampai_waktu:
                return hasil
            hasil.append({"tinggi": b["height"], "hash": b["id"], "waktu": b["timestamp"]})
        url = f"{URL_MEMPOOL}/{halaman[-1]['height'] - 1}"


def ambil_isi_blok(hash_blok: str, percobaan: int = 3) -> dict:
    """Unduh satu blok lengkap (bisa 1-8 MB). Coba ulang kalau servernya sibuk."""
    for ke in range(percobaan):
        try:
            r = requests.get(URL_BLOK.format(hash=hash_blok), headers=HEADER, timeout=90)
            if r.status_code == 429:
                time.sleep(10 * (ke + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if ke == percobaan - 1:
                raise
            time.sleep(3 * (ke + 1))
    raise RuntimeError(f"gagal mengunduh blok {hash_blok}")


# ---------------------------------------------------------------------------
# Bagian 3: simpan ke CSV
# ---------------------------------------------------------------------------

def _muat_atau_kosong(path: Path, kolom: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, parse_dates=["waktu"])
    return pd.DataFrame(columns=kolom)


def _gabung(lama: pd.DataFrame, baru: list[dict], kunci: str, kolom: list[str]) -> pd.DataFrame:
    if not baru:
        return lama
    df = pd.concat([lama, pd.DataFrame(baru)], ignore_index=True)
    df = df.drop_duplicates(kunci).sort_values("waktu").reset_index(drop=True)
    return df[kolom]


def perbarui_data(
    jam: float = 6,
    path_blok: Path = PATH_BLOK,
    path_paus: Path = PATH_PAUS,
    jeda_detik: float = 0.5,
    laporkan=print,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ambil blok dalam `jam` terakhir yang belum ada di CSV, lalu simpan.

    Aman dijalankan berulang: blok yang sudah diproses dilewati, jadi kalau
    koneksi putus di tengah jalan tinggal jalankan lagi.
    """
    df_blok = _muat_atau_kosong(path_blok, KOLOM_BLOK)
    df_paus = _muat_atau_kosong(path_paus, KOLOM_PAUS)
    sudah = set(df_blok["tinggi"].astype(int)) if len(df_blok) else set()

    batas = int(time.time() - jam * 3600)
    kandidat = [b for b in daftar_blok(batas) if b["tinggi"] not in sudah]
    laporkan(f"{len(kandidat)} blok baru dalam {jam} jam terakhir")

    baris_blok, baris_paus = [], []
    for i, b in enumerate(kandidat, 1):
        blok = ambil_isi_blok(b["hash"])
        paus = saring_paus(blok)
        baris_blok.append(ringkas_blok(blok, paus))
        baris_paus.extend(paus)
        laporkan(f"[{i}/{len(kandidat)}] blok {b['tinggi']}: {blok['n_tx']} tx, {len(paus)} paus")
        if jeda_detik:
            time.sleep(jeda_detik)
        # Simpan bertahap setiap 10 blok supaya progres tidak hilang.
        if i % 10 == 0 or i == len(kandidat):
            df_blok = _gabung(df_blok, baris_blok, "tinggi", KOLOM_BLOK)
            df_paus = _gabung(df_paus, baris_paus, "txid", KOLOM_PAUS)
            df_blok.to_csv(path_blok, index=False)
            df_paus.to_csv(path_paus, index=False)
            baris_blok, baris_paus = [], []
    return df_blok, df_paus


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unduh blok terbaru dan saring transaksi paus.")
    parser.add_argument("--jam", type=float, default=6, help="berapa jam ke belakang (default 6)")
    args = parser.parse_args()
    blok, paus = perbarui_data(jam=args.jam)
    print(f"OK: {len(blok)} blok, {len(paus)} transaksi paus tersimpan di {FOLDER_DATA}")
