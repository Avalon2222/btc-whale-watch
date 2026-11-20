"""
Tes untuk bagian logika murni src/ambil_blok.py (tanpa internet).
Jalankan:  python -m pytest tests/ -v

Blok palsu di bawah meniru format JSON blockchain.info, hanya field yang
dipakai. Nilai dalam satoshi (1 BTC = 100.000.000 satoshi).
"""

import pytest

from src import ambil_blok

SAT = 100_000_000


def buat_tx(hash_, nilai_input, nilai_output, fee=1000):
    """Transaksi palsu: daftar nilai input dan output dalam BTC."""
    return {
        "hash": hash_,
        "fee": fee,
        "inputs": [{"prev_out": {"value": int(v * SAT), "addr": f"in{i}"}} for i, v in enumerate(nilai_input)],
        "out": [{"value": int(v * SAT), "addr": f"out{i}"} for i, v in enumerate(nilai_output)],
    }


def buat_blok(txs, tinggi=900000, waktu=1_700_000_000):
    return {"hash": "abc", "height": tinggi, "time": waktu, "n_tx": len(txs), "tx": txs}


def test_klasifikasi_pola():
    assert ambil_blok.klasifikasi_pola(10, 1) == "konsolidasi"
    assert ambil_blok.klasifikasi_pola(1, 25) == "distribusi"
    assert ambil_blok.klasifikasi_pola(1, 2) == "transfer"
    assert ambil_blok.klasifikasi_pola(2, 2) == "transfer"
    # Banyak ke banyak tidak jelas arahnya, masuk "transfer".
    assert ambil_blok.klasifikasi_pola(5, 5) == "transfer"


def test_nilai_bulat():
    assert ambil_blok.nilai_bulat(1000.0)
    assert ambil_blok.nilai_bulat(250.00000000)
    assert not ambil_blok.nilai_bulat(999.99998)
    assert not ambil_blok.nilai_bulat(120.5)


def test_saring_paus_hanya_ambil_yang_besar():
    kecil = buat_tx("kecil", [0.5], [0.4, 0.09])
    besar = buat_tx("besar", [60, 50], [100, 9.9])
    hasil = ambil_blok.saring_paus(buat_blok([kecil, besar]), ambang_btc=50)
    assert [p["txid"] for p in hasil] == ["besar"]


def test_ringkas_transaksi_menghitung_dengan_benar():
    tx = buat_tx("x", [60, 50], [100, 9.9], fee=5000)
    baris = ambil_blok.ringkas_transaksi(tx, waktu_blok=1_700_000_000, tinggi=1)
    assert baris["jumlah_input"] == 2
    assert baris["jumlah_output"] == 2
    assert baris["total_btc"] == pytest.approx(109.9)
    assert baris["input_btc"] == pytest.approx(110.0)
    assert baris["fee_btc"] == pytest.approx(0.00005)
    assert baris["output_terbesar_btc"] == pytest.approx(100.0)
    assert baris["alamat_terbesar"] == "out0"
    assert baris["pola"] == "transfer"
    assert baris["bulat"] is True
    assert str(baris["waktu"]) == "2023-11-14 22:13:20"   # 1.700.000.000 detik UTC


def test_coinbase_tanpa_prev_out_tidak_membuat_error():
    coinbase = {"hash": "cb", "fee": 0, "inputs": [{"prev_out": {"value": 0, "n": 4294967295}}],
                "out": [{"value": int(3.2 * SAT), "addr": "miner"}]}
    hasil = ambil_blok.saring_paus(buat_blok([coinbase]), ambang_btc=1)
    assert hasil[0]["jumlah_input"] == 0
    assert hasil[0]["input_btc"] == 0


def test_ringkas_blok_menjumlahkan_paus():
    txs = [buat_tx("a", [100], [99.5]), buat_tx("b", [200], [150, 49.9]), buat_tx("c", [1], [0.9])]
    blok = buat_blok(txs, tinggi=123)
    paus = ambil_blok.saring_paus(blok, ambang_btc=50)
    ringkas = ambil_blok.ringkas_blok(blok, paus)
    assert ringkas["tinggi"] == 123
    assert ringkas["jumlah_tx"] == 3
    assert ringkas["jumlah_paus"] == 2
    assert ringkas["btc_paus"] == pytest.approx(99.5 + 199.9)


def test_input_nol_satoshi_tetap_dihitung_dan_value_none_aman():
    tx = buat_tx("nol", [0, 60], [59.9])
    tx["out"].append({"value": None, "addr": "kosong"})
    baris = ambil_blok.ringkas_transaksi(tx, 1_700_000_000, 900000)
    assert baris["jumlah_input"] == 2
    assert baris["input_btc"] == pytest.approx(60)
    assert baris["total_btc"] == pytest.approx(59.9)
    assert baris["alamat_terbesar"] == "out0"


def test_perbarui_data_tanpa_n_tx_dan_lewati_blok_lama(tmp_path, monkeypatch):
    blok_baru = buat_blok([buat_tx("t1", [80], [79.9])], tinggi=900001)
    del blok_baru["n_tx"]
    monkeypatch.setattr(
        ambil_blok, "daftar_blok",
        lambda batas: [{"tinggi": 900001, "hash": "abc", "waktu": 0}],
    )
    monkeypatch.setattr(ambil_blok, "ambil_isi_blok", lambda h: blok_baru)
    pesan = []
    blok, paus = ambil_blok.perbarui_data(
        jam=1, path_blok=tmp_path / "blok.csv", path_paus=tmp_path / "paus.csv",
        jeda_detik=0, laporkan=pesan.append,
    )
    assert list(blok["tinggi"]) == [900001]
    assert blok.iloc[0]["jumlah_tx"] == 1
    assert list(paus["txid"]) == ["t1"]
    assert "1 tx, 1 paus" in pesan[-1]

    # Dijalankan lagi: blok yang sudah ada di CSV tidak diunduh ulang.
    monkeypatch.setattr(ambil_blok, "ambil_isi_blok", lambda h: pytest.fail("tidak boleh unduh ulang"))
    blok2, _ = ambil_blok.perbarui_data(
        jam=1, path_blok=tmp_path / "blok.csv", path_paus=tmp_path / "paus.csv",
        jeda_detik=0, laporkan=pesan.append,
    )
    assert len(blok2) == 1


class _Respons:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_daftar_blok_berhenti_di_blok_genesis(monkeypatch):
    # Kalau semua blok lebih baru dari batas, loop harus berhenti di tinggi 0,
    # bukan meminta /blocks/-1 terus-menerus.
    halaman = {
        ambil_blok.URL_MEMPOOL: [{"height": 1, "id": "b1", "timestamp": 200},
                                 {"height": 0, "id": "b0", "timestamp": 100}],
    }
    dipanggil = []

    def palsu(url, headers=None, timeout=None):
        dipanggil.append(url)
        if url not in halaman:
            pytest.fail(f"permintaan tidak terduga: {url}")
        return _Respons(halaman[url])

    monkeypatch.setattr(ambil_blok.requests, "get", palsu)
    hasil = ambil_blok.daftar_blok(sampai_waktu=0)
    assert [b["tinggi"] for b in hasil] == [1, 0]
    assert dipanggil == [ambil_blok.URL_MEMPOOL]


def test_saring_paus_aman_untuk_value_none():
    tx = buat_tx("ada_none", [80], [79.9])
    tx["out"].append({"value": None, "addr": "kosong"})
    tanpa_out = {"hash": "tanpa_out", "fee": 0, "inputs": [], "out": None}
    hasil = ambil_blok.saring_paus(buat_blok([tx, tanpa_out]), ambang_btc=50)
    assert [p["txid"] for p in hasil] == ["ada_none"]
    assert hasil[0]["total_btc"] == pytest.approx(79.9)


def test_fee_none_dianggap_nol():
    tx = buat_tx("tanpa_fee", [80], [79.9])
    tx["fee"] = None
    baris = ambil_blok.ringkas_transaksi(tx, 1_700_000_000, 900000)
    assert baris["fee_btc"] == 0


@pytest.mark.parametrize("nilai", [float("nan"), float("inf"), None])
def test_nilai_bulat_bukan_angka(nilai):
    assert ambil_blok.nilai_bulat(nilai) is False


def test_ringkas_blok_n_tx_dan_tx_null():
    dasar = {"height": 900_000, "hash": "abc", "time": 1_700_000_000}
    assert ambil_blok.ringkas_blok({**dasar, "tx": None}, [])["jumlah_tx"] == 0
    assert ambil_blok.ringkas_blok({**dasar, "n_tx": None, "tx": [{}, {}]}, [])["jumlah_tx"] == 2
    assert ambil_blok.ringkas_blok({**dasar, "n_tx": 3000, "tx": None}, [])["jumlah_tx"] == 3000
