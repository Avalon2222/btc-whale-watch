"""
analisis.py - Logika inti: menyandingkan transaksi paus dengan harga dan mengukur reaksinya.

Tidak ada akses file atau internet di sini. Semua fungsi menerima DataFrame
dan mengembalikan DataFrame/dict, sehingga mudah diuji dengan data mini.

Pertanyaan yang dijawab modul ini:
  1. Berapa harga saat paus bergerak, dan berapa persen harga berubah
     15 menit, 1 jam, 4 jam SETELAHNYA?                      -> hitung_reaksi
  2. Apakah gerakan setelah paus lebih besar daripada gerakan
     di waktu-waktu biasa (baseline)?                        -> ringkasan_reaksi
  3. Apakah jam-jam dengan banyak paus lebih bergejolak
     daripada jam tanpa paus?                                -> agregasi_per_jam, bandingkan_jam
"""

from __future__ import annotations

import pandas as pd

HORIZON_MENIT = (15, 60, 240)
SEBELUM_MENIT = 60


# ---------------------------------------------------------------------------
# 1. Harga pada waktu tertentu dan reaksi setelahnya
# ---------------------------------------------------------------------------

def harga_pada(harga: pd.DataFrame, waktu: pd.Series) -> pd.Series:
    """Harga close dari candle terakhir yang <= tiap waktu (merge_asof).

    Kalau sebuah waktu berada sebelum candle pertama atau setelah candle
    terakhir, hasilnya NaN. Index hasil mengikuti index `waktu`.
    """
    kiri = pd.DataFrame({"waktu": pd.to_datetime(waktu.values)}, index=waktu.index)
    kiri["_urut"] = range(len(kiri))
    kiri = kiri.sort_values("waktu")
    kanan = harga[["waktu", "close"]].sort_values("waktu")
    hasil = pd.merge_asof(kiri, kanan, on="waktu", direction="backward")
    # Waktu yang melewati candle terakhir dianggap tidak diketahui.
    hasil.loc[hasil["waktu"] > kanan["waktu"].max(), "close"] = float("nan")
    hasil = hasil.sort_values("_urut")
    return pd.Series(hasil["close"].values, index=waktu.index)


def hitung_reaksi(
    paus: pd.DataFrame,
    harga: pd.DataFrame,
    horizon: tuple[int, ...] = HORIZON_MENIT,
    sebelum_menit: int = SEBELUM_MENIT,
) -> pd.DataFrame:
    """Tambahkan kolom harga dan return (persen) di sekitar tiap transaksi.

    Kolom baru:
      harga_saat       : harga close saat blok ditambang
      nilai_usd        : total_btc x harga_saat
      r_sebelum_pct    : perubahan harga dari `sebelum_menit` sebelum sampai saat blok
      r_{h}m_pct       : perubahan harga dari saat blok ke h menit setelahnya
    """
    df = paus.copy()
    if df.empty:
        for kolom in ["harga_saat", "nilai_usd", "r_sebelum_pct"] + [f"r_{h}m_pct" for h in horizon]:
            df[kolom] = pd.Series(dtype=float)
        return df
    df["harga_saat"] = harga_pada(harga, df["waktu"])
    df["nilai_usd"] = df["total_btc"] * df["harga_saat"]
    sebelum = harga_pada(harga, df["waktu"] - pd.Timedelta(minutes=sebelum_menit))
    df["r_sebelum_pct"] = (df["harga_saat"] / sebelum - 1) * 100
    for h in horizon:
        sesudah = harga_pada(harga, df["waktu"] + pd.Timedelta(minutes=h))
        df[f"r_{h}m_pct"] = (sesudah / df["harga_saat"] - 1) * 100
    return df


def baseline(harga: pd.DataFrame, horizon: tuple[int, ...] = HORIZON_MENIT) -> pd.DataFrame:
    """Return h menit ke depan dari SETIAP candle: pembanding untuk reaksi paus.

    Kalau return setelah paus tidak berbeda dari return setelah candle acak,
    paus itu tidak "menggerakkan" apa-apa.
    """
    df = harga[["waktu", "close"]].copy()
    for h in horizon:
        sesudah = harga_pada(harga, df["waktu"] + pd.Timedelta(minutes=h))
        df[f"r_{h}m_pct"] = (sesudah / df["close"] - 1) * 100
    return df


def ringkasan_reaksi(
    reaksi: pd.DataFrame,
    pembanding: pd.DataFrame,
    horizon: tuple[int, ...] = HORIZON_MENIT,
) -> pd.DataFrame:
    """Satu baris per horizon: rata-rata, median, persen naik, dan |return| vs baseline."""
    baris = []
    for h in horizon:
        kol = f"r_{h}m_pct"
        r = reaksi[kol].dropna()
        b = pembanding[kol].dropna()
        rata_abs = r.abs().mean() if len(r) else float("nan")
        base_abs = b.abs().mean() if len(b) else float("nan")
        baris.append({
            "horizon_menit": h,
            "jumlah": int(len(r)),
            "rata_rata_pct": r.mean() if len(r) else float("nan"),
            "median_pct": r.median() if len(r) else float("nan"),
            "persen_naik": (r > 0).mean() * 100 if len(r) else float("nan"),
            "rata_abs_pct": rata_abs,
            "baseline_abs_pct": base_abs,
            "rasio_vs_baseline": rata_abs / base_abs if base_abs else float("nan"),
        })
    return pd.DataFrame(baris)


def ringkasan_per_pola(reaksi: pd.DataFrame, horizon_menit: int = 60) -> pd.DataFrame:
    """Per pola transaksi: jumlah, total BTC, rata-rata return dan persen naik."""
    kol = f"r_{horizon_menit}m_pct"
    if reaksi.empty:
        return pd.DataFrame(columns=["pola", "jumlah", "total_btc", "rata_rata_pct", "persen_naik"])
    g = reaksi.groupby("pola")
    hasil = pd.DataFrame({
        "jumlah": g.size(),
        "total_btc": g["total_btc"].sum(),
        "rata_rata_pct": g[kol].mean(),
        "persen_naik": g[kol].apply(lambda s: (s.dropna() > 0).mean() * 100 if s.notna().any() else float("nan")),
    })
    return hasil.reset_index().sort_values("total_btc", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Agregasi per jam: jam ramai paus vs jam sepi
# ---------------------------------------------------------------------------

def agregasi_per_jam(paus: pd.DataFrame, harga: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per jam: aktivitas paus di jam itu dan return di jam BERIKUTNYA.

    Return jam berikutnya dipakai (bukan jam yang sama) supaya urutan sebabnya
    jelas: paus bergerak dulu, baru harga dilihat.
    """
    per_jam = harga.set_index("waktu")["close"].resample("h").last().dropna()
    df = pd.DataFrame({"jam": per_jam.index, "close": per_jam.values})
    df["ret_jam_ini_pct"] = (df["close"] / df["close"].shift(1) - 1) * 100
    df["ret_jam_berikut_pct"] = (df["close"].shift(-1) / df["close"] - 1) * 100
    df["abs_ret_berikut_pct"] = df["ret_jam_berikut_pct"].abs()

    if len(paus):
        p = paus.assign(jam=paus["waktu"].dt.floor("h"))
        agg = p.groupby("jam").agg(jumlah_paus=("txid", "size"), btc_paus=("total_btc", "sum"))
        df = df.merge(agg, left_on="jam", right_index=True, how="left")
    else:
        df["jumlah_paus"] = 0
        df["btc_paus"] = 0.0
    df["jumlah_paus"] = df["jumlah_paus"].fillna(0).astype(int)
    df["btc_paus"] = df["btc_paus"].fillna(0.0)
    # Jam pertama dan terakhir tidak punya return lengkap; buang supaya adil.
    df = df.dropna(subset=["ret_jam_berikut_pct"])
    return df.reset_index(drop=True)


def bandingkan_jam(agg: pd.DataFrame) -> dict:
    """Bandingkan gejolak jam berikutnya: ada paus vs tidak ada paus.

    Korelasi memakai Spearman (korelasi peringkat) supaya satu transaksi
    raksasa tidak mendominasi hasil.
    """
    ada = agg[agg["jumlah_paus"] > 0]
    tidak = agg[agg["jumlah_paus"] == 0]
    if len(agg) >= 3 and agg["btc_paus"].nunique() > 1:
        korelasi = agg["btc_paus"].rank().corr(agg["abs_ret_berikut_pct"].rank())
    else:
        korelasi = float("nan")
    return {
        "jam_ada_paus": int(len(ada)),
        "jam_tanpa_paus": int(len(tidak)),
        "abs_ret_ada_paus": ada["abs_ret_berikut_pct"].mean() if len(ada) else float("nan"),
        "abs_ret_tanpa_paus": tidak["abs_ret_berikut_pct"].mean() if len(tidak) else float("nan"),
        "korelasi_spearman": korelasi,
    }


# ---------------------------------------------------------------------------
# 3. Pembantu kecil
# ---------------------------------------------------------------------------

def paus_teratas(reaksi: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return reaksi.sort_values("total_btc", ascending=False).head(n).reset_index(drop=True)


def singkat_txid(txid: str, panjang: int = 8) -> str:
    return f"{txid[:panjang]}…{txid[-4:]}" if len(txid) > panjang + 5 else txid
