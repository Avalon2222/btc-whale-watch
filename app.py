"""
app.py - Dashboard Whale Watch (Streamlit).

Jalankan:  streamlit run app.py

File ini hanya mengurus TAMPILAN. Semua perhitungan ada di src/analisis.py,
pengambilan data ada di src/ambil_blok.py dan src/ambil_harga.py.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import ambil_blok, ambil_harga, analisis, muat_data

st.set_page_config(page_title="Whale Watch", page_icon="🐋", layout="wide")

WARNA_POLA = {"konsolidasi": "#2a78d6", "distribusi": "#eb6834", "transfer": "#1baf7a"}
LABEL_POLA = {
    "konsolidasi": "Konsolidasi (banyak → sedikit)",
    "distribusi": "Distribusi (sedikit → banyak)",
    "transfer": "Transfer (sedikit → sedikit)",
}
WARNA_HARGA = "#6b6a66"
WARNA_BASELINE = "#b8b7b1"
HORIZON = analisis.HORIZON_MENIT
URL_TX = "https://mempool.space/tx/{}"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def muat_semua():
    return muat_data.muat_paus(), muat_data.muat_harga(), muat_data.muat_blok()


def perbarui_dari_internet() -> str:
    """Ambil blok ~1 jam terakhir + lengkapi harga. Mengembalikan pesan status."""
    try:
        blok, paus = ambil_blok.perbarui_data(jam=1, laporkan=lambda *_: None)
        ambil_harga.perbarui_csv()
    except Exception as e:  # internet mati, API berubah, dsb.
        return f"Gagal mengambil data baru ({type(e).__name__}). Dashboard tetap memakai data tersimpan."
    muat_semua.clear()
    return f"Data diperbarui: {len(blok)} blok, {len(paus)} transaksi paus tersimpan."


def fmt_btc(x: float) -> str:
    return f"{x:,.0f} BTC"


def fmt_usd(x: float) -> str:
    if pd.isna(x):
        return "-"
    if x >= 1e9:
        return f"${x / 1e9:,.2f} miliar"
    if x >= 1e6:
        return f"${x / 1e6:,.1f} juta"
    return f"${x:,.0f}"


paus_semua, harga, blok = muat_semua()
harga_terakhir = float(harga["close"].iloc[-1])

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🐋 Whale Watch")
    st.caption("*Someone always moves first.*")

    ambang = st.slider(
        "Ambang paus (BTC)", min_value=50, max_value=2000, value=500, step=50,
        help="Transaksi dengan total output di bawah angka ini diabaikan. "
             f"Data tersimpan hanya memuat transaksi ≥ {ambil_blok.AMBANG_SIMPAN_BTC:.0f} BTC.",
    )
    st.caption(f"≈ {fmt_usd(ambang * harga_terakhir).replace('$', r'\$')} pada harga terakhir")

    total_jam = max(6, int((blok["waktu"].max() - blok["waktu"].min()).total_seconds() // 3600) + 1)
    jam_terakhir = st.slider("Rentang (jam terakhir dari data)", 6, total_jam, total_jam, step=1)

    pola_dipilih = st.multiselect(
        "Pola transaksi", list(LABEL_POLA), default=list(LABEL_POLA), format_func=LABEL_POLA.get,
    )
    hanya_bulat = st.checkbox("Hanya nilai bulat (misalnya tepat 1.000 BTC)", value=False)
    mode_belajar = st.toggle("🎓 Mode belajar", value=False, help="Tampilkan rumus dan potongan kode di tiap bagian")

    st.divider()
    if st.button("🔄 Ambil blok terbaru (±1 jam)", use_container_width=True):
        with st.spinner("Mengunduh blok dari mempool.space dan blockchain.info…"):
            st.session_state["pesan_update"] = perbarui_dari_internet()
        st.rerun()
    if "pesan_update" in st.session_state:
        st.info(st.session_state.pop("pesan_update"))
    st.caption(
        f"Data: {len(blok):,} blok ({blok['tinggi'].min():,}–{blok['tinggi'].max():,}), "
        f"{blok['waktu'].min():%d %b %Y %H:%M} – {blok['waktu'].max():%d %b %Y %H:%M} UTC. "
        "Tanpa internet, dashboard memakai data tersimpan ini."
    )

# ---------------------------------------------------------------------------
# Saring + hitung
# ---------------------------------------------------------------------------

batas_waktu = blok["waktu"].max() - pd.Timedelta(hours=jam_terakhir)
paus = paus_semua[
    (paus_semua["total_btc"] >= ambang)
    & (paus_semua["waktu"] >= batas_waktu)
    & (paus_semua["pola"].isin(pola_dipilih))
]
if hanya_bulat:
    paus = paus[paus["bulat"]]
harga_rentang = harga[harga["waktu"] >= batas_waktu - pd.Timedelta(hours=1)]

reaksi = analisis.hitung_reaksi(paus, harga)
pembanding = analisis.baseline(harga_rentang)
ringkas = analisis.ringkasan_reaksi(reaksi, pembanding)
agg_jam = analisis.agregasi_per_jam(paus, harga_rentang)
banding = analisis.bandingkan_jam(agg_jam)

# ---------------------------------------------------------------------------
# Header + KPI
# ---------------------------------------------------------------------------

st.title("🐋 Whale Watch: siapa yang bergerak duluan?")
st.markdown(
    "Transaksi Bitcoin raksasa dari blockchain publik, disandingkan dengan harga per 5 menit. "
    "Pertanyaannya sederhana: **setelah paus bergerak, apakah harga ikut bergerak?**"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Transaksi paus", f"{len(paus):,}", help=f"≥ {ambang} BTC dalam {jam_terakhir} jam terakhir")
k2.metric("Total dipindahkan", fmt_btc(paus["total_btc"].sum()))
k3.metric("Nilai saat itu", fmt_usd(reaksi["nilai_usd"].sum()))
if len(paus):
    terbesar = paus.loc[paus["total_btc"].idxmax()]
    k4.metric("Paus terbesar", fmt_btc(terbesar["total_btc"]), help=f"{terbesar['waktu']:%d %b %H:%M} UTC, {terbesar['pola']}")
else:
    k4.metric("Paus terbesar", "-")

if paus.empty:
    st.warning("Tidak ada transaksi yang lolos filter. Turunkan ambang atau perlebar rentang.")
    st.stop()

tab_linimasa, tab_daftar, tab_dampak, tab_cara = st.tabs(["📈 Linimasa", "📋 Daftar paus", "📊 Dampak ke harga", "🧭 Cara kerja"])

# ---------------------------------------------------------------------------
# Tab 1: Linimasa
# ---------------------------------------------------------------------------

with tab_linimasa:
    st.caption("Garis = harga BTC-USD per 5 menit (Coinbase). Gelembung = transaksi paus; makin besar makin banyak BTC. "
               "Arahkan kursor untuk detail, klik untuk kartu lengkap.")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(
        x=harga_rentang["waktu"], y=harga_rentang["close"], mode="lines", name="Harga BTC-USD",
        line=dict(color=WARNA_HARGA, width=1.5), hovertemplate="%{x|%d %b %H:%M} UTC<br>$%{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    skala = 60 / max(reaksi["total_btc"].max() ** 0.5, 1)
    for pola, warna in WARNA_POLA.items():
        sub = reaksi[reaksi["pola"] == pola]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["waktu"], y=sub["harga_saat"], mode="markers", name=LABEL_POLA[pola],
            marker=dict(size=(sub["total_btc"] ** 0.5 * skala).clip(lower=8), color=warna, opacity=0.75,
                        line=dict(width=1.5, color="#fcfcfb")),
            customdata=sub[["txid", "total_btc", "nilai_usd", "jumlah_input", "jumlah_output", "r_60m_pct"]].values,
            hovertemplate=(
                "<b>%{customdata[1]:,.1f} BTC</b> (%{customdata[2]:$,.0f})<br>"
                "%{x|%d %b %H:%M} UTC · %{customdata[3]} input → %{customdata[4]} output<br>"
                "harga 1 jam kemudian: %{customdata[5]:+.2f}%<extra>" + pola + "</extra>"
            ),
        ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=agg_jam["jam"], y=agg_jam["btc_paus"], name="BTC paus per jam", marker_color="#9ec5f4", showlegend=False,
        hovertemplate="%{x|%d %b %H:00} UTC<br>%{y:,.0f} BTC<extra></extra>",
    ), row=2, col=1)

    fig.update_layout(
        height=620, hovermode="closest", margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.02, x=0), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
        bargap=0.2,
    )
    fig.update_yaxes(title_text="USD", row=1, col=1, gridcolor="#eeede9", tickformat="$,.0f")
    fig.update_yaxes(title_text="BTC / jam", row=2, col=1, gridcolor="#eeede9")
    fig.update_xaxes(gridcolor="#eeede9")

    pilihan = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", key="linimasa")

    titik = pilihan.get("selection", {}).get("points", []) if pilihan else []
    titik = [p for p in titik if p.get("customdata")]
    if titik:
        txid = titik[0]["customdata"][0]
        baris = reaksi[reaksi["txid"] == txid].iloc[0]
        with st.container(border=True):
            c1, c2 = st.columns([2, 3])
            with c1:
                st.markdown(f"### {baris['total_btc']:,.2f} BTC")
                # Tanda $ harus di-escape, kalau tidak Streamlit mengira itu rumus LaTeX.
                st.markdown(f"**{fmt_usd(baris['nilai_usd']).replace('$', r'\$')}** pada harga \\${baris['harga_saat']:,.0f}")
                st.markdown(f"{baris['waktu']:%d %B %Y %H:%M:%S} UTC · blok {baris['tinggi_blok']:,}")
                st.markdown(f"Pola: **{LABEL_POLA[baris['pola']]}**" + (" · nilai bulat" if baris["bulat"] else ""))
                st.markdown(f"[Lihat di mempool.space ↗]({URL_TX.format(txid)})")
            with c2:
                m = st.columns(4)
                m[0].metric("1 jam sebelum", f"{baris['r_sebelum_pct']:+.2f}%")
                for i, h in enumerate(HORIZON, start=1):
                    nilai = baris[f"r_{h}m_pct"]
                    m[i].metric(f"{h} menit sesudah", "-" if pd.isna(nilai) else f"{nilai:+.2f}%")
                st.caption(
                    f"{baris['jumlah_input']} input ({baris['input_btc']:,.2f} BTC) → {baris['jumlah_output']} output. "
                    f"Output terbesar {baris['output_terbesar_btc']:,.2f} BTC ke `{baris['alamat_terbesar'] or '?'}`. "
                    f"Fee {baris['fee_btc']:.8f} BTC."
                )
    else:
        st.caption("Klik salah satu gelembung untuk melihat kartu detail transaksi.")

    if mode_belajar:
        with st.expander("🎓 Bagaimana gelembung ini dibuat?"):
            st.markdown(
                "Tiap transaksi punya waktu blok, tetapi harga hanya ada per 5 menit. Untuk mencari harga "
                "*saat* transaksi, dipakai `pd.merge_asof` arah `backward`: candle terakhir yang waktunya "
                "≤ waktu blok. Ukuran gelembung memakai **akar kuadrat** dari jumlah BTC, karena mata membaca "
                "luas lingkaran, bukan jari-jarinya; kalau jari-jari dibuat sebanding dengan BTC, transaksi "
                "20.000 BTC akan tampak 400 kali lebih besar dari 1.000 BTC, bukan 20 kali."
            )
            st.code(
                'harga_saat = pd.merge_asof(paus.sort_values("waktu"), harga[["waktu", "close"]],\n'
                '                           on="waktu", direction="backward")["close"]\n'
                'ukuran = (paus["total_btc"] ** 0.5) * skala', language="python",
            )

# ---------------------------------------------------------------------------
# Tab 2: Daftar paus
# ---------------------------------------------------------------------------

with tab_daftar:
    tabel = reaksi.sort_values("total_btc", ascending=False).copy()
    tabel["tautan"] = tabel["txid"].map(URL_TX.format)
    kolom_tampil = ["waktu", "total_btc", "nilai_usd", "pola", "jumlah_input", "jumlah_output",
                    "bulat", "r_sebelum_pct", "r_15m_pct", "r_60m_pct", "r_240m_pct", "tautan"]
    st.dataframe(
        tabel[kolom_tampil], use_container_width=True, hide_index=True, height=520,
        column_config={
            "waktu": st.column_config.DatetimeColumn("Waktu (UTC)", format="DD MMM HH:mm"),
            "total_btc": st.column_config.NumberColumn("BTC", format="%.2f"),
            "nilai_usd": st.column_config.NumberColumn("USD saat itu", format="$%.0f"),
            "pola": "Pola",
            "jumlah_input": "Input",
            "jumlah_output": "Output",
            "bulat": st.column_config.CheckboxColumn("Bulat"),
            "r_sebelum_pct": st.column_config.NumberColumn("1j sebelum", format="%+.2f%%"),
            "r_15m_pct": st.column_config.NumberColumn("+15m", format="%+.2f%%"),
            "r_60m_pct": st.column_config.NumberColumn("+1j", format="%+.2f%%"),
            "r_240m_pct": st.column_config.NumberColumn("+4j", format="%+.2f%%"),
            "tautan": st.column_config.LinkColumn("mempool.space", display_text="buka ↗"),
        },
    )
    st.download_button(
        "⬇️ Unduh CSV (sesuai filter)", tabel.drop(columns=["tautan"]).to_csv(index=False).encode(),
        file_name="transaksi_paus_terfilter.csv", mime="text/csv",
    )

# ---------------------------------------------------------------------------
# Tab 3: Dampak ke harga
# ---------------------------------------------------------------------------

with tab_dampak:
    st.subheader("1. Setelah paus bergerak, seberapa jauh harga bergerak?")
    st.caption(
        "Batang biru: rata-rata |perubahan harga| setelah transaksi paus. Batang abu-abu: rata-rata |perubahan| "
        "setelah **sembarang** candle 5 menit di rentang yang sama (baseline). Kalau keduanya mirip, paus tidak "
        "membawa informasi tambahan."
    )
    c_grafik, c_tabel = st.columns([3, 2])
    with c_grafik:
        fig_r = go.Figure()
        label_h = [f"{h} menit" for h in ringkas["horizon_menit"]]
        fig_r.add_trace(go.Bar(name="Setelah paus", x=label_h, y=ringkas["rata_abs_pct"], marker_color="#2a78d6",
                               text=ringkas["rata_abs_pct"].map("{:.2f}%".format), textposition="outside"))
        fig_r.add_trace(go.Bar(name="Baseline (semua candle)", x=label_h, y=ringkas["baseline_abs_pct"],
                               marker_color=WARNA_BASELINE, text=ringkas["baseline_abs_pct"].map("{:.2f}%".format),
                               textposition="outside"))
        fig_r.update_layout(barmode="group", height=360, margin=dict(l=10, r=10, t=30, b=10),
                            yaxis_title="rata-rata |perubahan harga| (%)", plot_bgcolor="#fcfcfb",
                            paper_bgcolor="#fcfcfb", legend=dict(orientation="h", y=1.1, x=0), bargap=0.3)
        fig_r.update_yaxes(gridcolor="#eeede9", rangemode="tozero")
        st.plotly_chart(fig_r, use_container_width=True)
    with c_tabel:
        tampil = ringkas.rename(columns={
            "horizon_menit": "Menit", "jumlah": "n", "rata_rata_pct": "Rata-rata",
            "persen_naik": "% naik", "rasio_vs_baseline": "vs baseline",
        })[["Menit", "n", "Rata-rata", "% naik", "vs baseline"]]
        st.dataframe(tampil.style.format({"Rata-rata": "{:+.3f}%", "% naik": "{:.0f}%", "vs baseline": "{:.2f}×"}),
                     hide_index=True, use_container_width=True)
        st.caption("Rata-rata = perubahan harga bertanda (naik positif). % naik = porsi transaksi yang diikuti harga naik.")
        rasio_1j = ringkas.set_index("horizon_menit").loc[60, "rasio_vs_baseline"]
        if pd.notna(rasio_1j):
            if rasio_1j > 1.3:
                pesan = f"Satu jam setelah paus, harga bergerak **{rasio_1j:.2f}×** lebih jauh dari biasanya. Ada sesuatu di sini, tetapi ingat: korelasi bukan sebab-akibat."
            elif rasio_1j > 1.1:
                pesan = f"Satu jam setelah paus, harga bergerak **{rasio_1j:.2f}×** baseline: sedikit lebih bergejolak, tetapi selisihnya kecil dan bisa hilang kalau rentang atau ambang diubah."
            elif rasio_1j < 0.9:
                pesan = f"Satu jam setelah paus, harga justru bergerak **lebih tenang** ({rasio_1j:.2f}× baseline). Paus bergerak saat pasar sepi?"
            else:
                pesan = f"Satu jam setelah paus, harga bergerak **{rasio_1j:.2f}×** baseline: praktis sama dengan waktu-waktu biasa. Paus bukan sinyal yang berguna di rentang ini."
            st.info(pesan)

    if mode_belajar:
        with st.expander("🎓 Apa itu baseline, dan kenapa penting?"):
            st.markdown(
                "Angka \"harga bergerak 0,3% setelah paus\" tidak berarti apa-apa sendirian. Bitcoin memang bergerak "
                "0,3% setiap jam, dengan atau tanpa paus. Baseline menjawab: *kalau saya memilih waktu secara acak, "
                "seberapa jauh harga bergerak satu jam kemudian?* Hanya kalau angka setelah paus jauh lebih besar "
                "dari baseline, kita boleh curiga ada hubungan. Nilai mutlak (|r|) dipakai karena arah geraknya "
                "bisa naik atau turun; yang kita ukur adalah *gejolaknya*."
            )
            st.code(
                'r_sesudah = harga_pada(harga, paus["waktu"] + pd.Timedelta(minutes=60)) / harga_saat - 1\n'
                'baseline  = harga["close"].shift(-12) / harga["close"] - 1   # 12 candle = 60 menit\n'
                'rasio     = r_sesudah.abs().mean() / baseline.abs().mean()', language="python",
            )

    st.divider()
    st.subheader("2. Siapa yang bergerak duluan: paus atau harga?")
    abs_sebelum = reaksi["r_sebelum_pct"].abs().mean()
    abs_sesudah = reaksi["r_60m_pct"].abs().mean()
    base_1j = ringkas.set_index("horizon_menit").loc[60, "baseline_abs_pct"]
    c1, c2, c3 = st.columns(3)
    c1.metric("|Δ harga| 1 jam SEBELUM paus", f"{abs_sebelum:.2f}%")
    c2.metric("|Δ harga| 1 jam SESUDAH paus", f"{abs_sesudah:.2f}%")
    c3.metric("Baseline 1 jam", f"{base_1j:.2f}%")
    if pd.notna(abs_sebelum) and pd.notna(abs_sesudah):
        if abs_sebelum > abs_sesudah * 1.15:
            st.markdown("Gejolak **sebelum** transaksi lebih besar daripada sesudahnya: paus tampak **bereaksi** terhadap harga, bukan menggerakkannya.")
        elif abs_sesudah > abs_sebelum * 1.15:
            st.markdown("Gejolak **sesudah** transaksi lebih besar daripada sebelumnya: harga tampak bergerak **setelah** paus. Menarik, tetapi belum membuktikan sebab-akibat.")
        else:
            st.markdown("Gejolak sebelum dan sesudah transaksi kurang lebih sama. Tidak ada tanda jelas siapa yang bergerak duluan.")

    st.divider()
    st.subheader("3. Pola mana yang diikuti harga naik atau turun?")
    horizon_pola = st.radio("Horizon", HORIZON, index=1, horizontal=True, format_func=lambda h: f"{h} menit")
    per_pola = analisis.ringkasan_per_pola(reaksi, horizon_pola)
    c_pola, c_ket = st.columns([3, 2])
    with c_pola:
        fig_p = go.Figure(go.Bar(
            x=per_pola["pola"].map(LABEL_POLA), y=per_pola["rata_rata_pct"],
            marker_color=[WARNA_POLA[p] for p in per_pola["pola"]],
            text=[f"{r:+.3f}%  (n={n}, {u:.0f}% naik)" for r, n, u in zip(per_pola["rata_rata_pct"], per_pola["jumlah"], per_pola["persen_naik"])],
            textposition="outside",
        ))
        fig_p.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=f"rata-rata perubahan {horizon_pola} menit (%)",
                            plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", bargap=0.4)
        fig_p.update_yaxes(gridcolor="#eeede9", zeroline=True, zerolinecolor="#6b6a66")
        st.plotly_chart(fig_p, use_container_width=True)
    with c_ket:
        st.markdown(
            "- **Distribusi** (1 dompet membayar banyak alamat) biasanya penarikan massal dari bursa: koin keluar dari bursa.\n"
            "- **Konsolidasi** (banyak input jadi 1-2 output) biasanya bursa/kustodian merapikan saldo, atau setoran besar.\n"
            "- **Transfer** sedikit-ke-sedikit paling sulit ditebak: bisa OTC, bisa pindah dompet dingin.\n\n"
            "Narasi populer: koin *keluar* bursa = bullish, *masuk* bursa = bearish. Angka di kiri adalah cara "
            "mengecek narasi itu dengan data, bukan dengan cuitan."
        )

    st.divider()
    st.subheader("4. Jam ramai paus vs jam sepi")
    c1, c2, c3 = st.columns(3)
    c1.metric("Jam dengan paus", f"{banding['jam_ada_paus']}", help="jumlah jam yang memuat ≥ 1 transaksi paus")
    c2.metric("|Δ| jam berikutnya (ada paus)", "-" if pd.isna(banding["abs_ret_ada_paus"]) else f"{banding['abs_ret_ada_paus']:.2f}%")
    c3.metric("|Δ| jam berikutnya (tanpa paus)", "-" if pd.isna(banding["abs_ret_tanpa_paus"]) else f"{banding['abs_ret_tanpa_paus']:.2f}%",
              help=f"{banding['jam_tanpa_paus']} jam tanpa paus")
    fig_j = go.Figure(go.Scatter(
        x=agg_jam["btc_paus"], y=agg_jam["abs_ret_berikut_pct"], mode="markers",
        marker=dict(size=9, color="#2a78d6", opacity=0.7, line=dict(width=1, color="#fcfcfb")),
        customdata=agg_jam[["jam", "jumlah_paus"]].values,
        hovertemplate="%{customdata[0]|%d %b %H:00} UTC<br>%{x:,.0f} BTC dalam %{customdata[1]} transaksi<br>|Δ| jam berikutnya %{y:.2f}%<extra></extra>",
    ))
    fig_j.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="BTC yang dipindahkan paus dalam satu jam",
                        yaxis_title="|perubahan harga| jam berikutnya (%)", plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb")
    fig_j.update_xaxes(gridcolor="#eeede9")
    fig_j.update_yaxes(gridcolor="#eeede9")
    st.plotly_chart(fig_j, use_container_width=True)
    kor = banding["korelasi_spearman"]
    if pd.notna(kor):
        kuat = "lemah" if abs(kor) < 0.2 else ("sedang" if abs(kor) < 0.5 else "kuat")
        st.markdown(f"Korelasi Spearman antara BTC paus per jam dan gejolak jam berikutnya: **{kor:+.2f}** ({kuat}). "
                    "Nilai mendekati 0 berarti ramai-sepinya paus tidak memberi petunjuk tentang gejolak satu jam ke depan.")

    if mode_belajar:
        with st.expander("🎓 Kenapa Spearman, bukan Pearson?"):
            st.markdown(
                "Satu transaksi 20.000 BTC bisa 100× lebih besar dari transaksi paus biasa. Korelasi Pearson memakai "
                "nilai asli, sehingga satu titik ekstrem bisa \"menyeret\" hasilnya. Spearman mengganti nilai dengan "
                "**peringkat** (ke-1, ke-2, ...), jadi 20.000 BTC hanya \"yang paling besar\", bukan 100× lebih berat. "
                "Di pandas: `x.rank().corr(y.rank())`."
            )
            st.code(
                'per_jam = harga.set_index("waktu")["close"].resample("h").last()\n'
                'ret_berikut = per_jam.shift(-1) / per_jam - 1\n'
                'btc_paus = paus.groupby(paus["waktu"].dt.floor("h"))["total_btc"].sum()\n'
                'spearman = btc_paus.rank().corr(ret_berikut.abs().rank())', language="python",
            )

# ---------------------------------------------------------------------------
# Tab 4: Cara kerja
# ---------------------------------------------------------------------------

with tab_cara:
    st.markdown("""
### Alur data

```
mempool.space /api/v1/blocks ──► daftar blok terbaru (tinggi, hash, waktu)
                                        │
blockchain.info /rawblock/{hash} ──────► semua transaksi dalam satu blok
                                        │  src/ambil_blok.py: total output ≥ 50 BTC?
                                        ▼
                              data/transaksi_paus.csv  +  data/blok.csv
                                        │
Coinbase /products/BTC-USD/candles ───► data/btc_harga_5menit.csv
                                        │
                                        ▼
                      src/analisis.py: harga saat blok, return 15m / 1j / 4j,
                      baseline, agregasi per jam, korelasi Spearman
                                        │
                                        ▼
                                 app.py (Streamlit + Plotly)
```

### Definisi

- **Paus**: transaksi yang *total output*-nya ≥ ambang (slider, default 100 BTC). Yang diukur adalah jumlah BTC yang
  berpindah dalam satu transaksi, bukan saldo pemiliknya.
- **Waktu transaksi** = waktu blok tempat transaksi itu ditambang. Transaksi mungkin sudah disiarkan ke jaringan
  beberapa menit sebelumnya dan terlihat di mempool; data ini tidak menangkap jeda itu.
- **Harga saat transaksi** = candle 5 menit terakhir yang ≤ waktu blok (Coinbase BTC-USD).
- **Return h menit** = harga pada (waktu blok + h menit) dibagi harga saat blok, dikurangi 1.
- **Baseline** = return yang sama dihitung dari *setiap* candle 5 menit di rentang yang dipilih.

### Keterbatasan (penting)

1. **Sebab-akibat tidak bisa disimpulkan dari data ini.** Paus bisa bergerak *karena* harga, harga bisa bergerak
   *karena* paus, atau keduanya bereaksi pada berita yang sama.
2. **Tidak ada label alamat.** Dashboard tidak tahu mana alamat bursa, mana dompet dingin. Pola konsolidasi/distribusi
   hanya tebakan dari bentuk transaksi.
3. **Satu transaksi ≠ satu pelaku.** Bursa merapikan saldo internal dalam transaksi besar setiap hari; itu bukan
   "paus membeli" atau "paus menjual".
4. **Rentang data pendek** (beberapa hari). Hasil bisa berubah total di minggu yang berbeda. Tombol di sidebar
   menambah blok terbaru; untuk rentang panjang jalankan `python -m src.ambil_blok --jam 168`.
5. Harga dari satu bursa (Coinbase). Bursa lain bisa berbeda beberapa dolar.

### Bukan saran investasi

Dashboard ini alat belajar untuk membaca data blockchain dan menguji narasi dengan angka. Tidak ada di sini yang
merupakan rekomendasi membeli, menjual, atau menahan aset apa pun.
""")

st.caption("Data: mempool.space, blockchain.info, Coinbase Exchange. Bukan saran investasi.")
