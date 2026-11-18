"""Tes untuk src/ambil_harga.py tanpa internet: ambil_candle diganti data palsu."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from src import ambil_harga


def _candle(waktu, close):
    return pd.DataFrame({"waktu": pd.to_datetime(waktu), "open": close, "high": close,
                         "low": close, "close": close, "volume": 1.0})


def test_perbarui_csv_tidak_menyimpan_candle_yang_belum_selesai(tmp_path, monkeypatch):
    sekarang = datetime.now(tz=timezone.utc).replace(tzinfo=None, second=0, microsecond=0)
    selesai = sekarang - timedelta(minutes=10)
    berjalan = sekarang - timedelta(minutes=2)
    monkeypatch.setattr(ambil_harga, "ambil_candle",
                        lambda a, b: _candle([selesai, berjalan], [100.0, 101.0]))
    path = tmp_path / "harga.csv"
    df = ambil_harga.perbarui_csv(jam=1, path=path)
    assert list(df["waktu"]) == [pd.Timestamp(selesai)]


def test_perbarui_csv_unduhan_baru_menimpa_candle_lama(tmp_path, monkeypatch):
    sekarang = datetime.now(tz=timezone.utc).replace(tzinfo=None, second=0, microsecond=0)
    t = sekarang - timedelta(hours=1)
    path = tmp_path / "harga.csv"
    _candle([t], [50.0]).to_csv(path, index=False)
    monkeypatch.setattr(ambil_harga, "ambil_candle", lambda a, b: _candle([t], [55.0]))
    df = ambil_harga.perbarui_csv(jam=2, path=path)
    assert df.loc[df["waktu"] == pd.Timestamp(t), "close"].item() == 55.0
