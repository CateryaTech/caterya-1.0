# CATERYA AI Assurance Infrastructure — ringkasan Bahasa Indonesia

**Measure. Verify. Assure.** (Ukur. Verifikasi. Jamin.)

Infrastruktur terbuka dan netral-vendor untuk **mengevaluasi sistem AI**, menghasilkan **bukti yang dapat diverifikasi**, menjaga
**provenance anti-manipulasi**, dan mendukung **asurans berkelanjutan**. Ditambah lapisan opsional: riset kuantum dan blockchain/DeFi.

**Mengapa ada.** Klaim tentang sistem AI — "adil", "tangguh", "patuh" — sering dibuat tanpa bukti yang bisa diperiksa orang lain. CATERYA menjadikan
*bukti* sebagai produk: setiap hasil menyatakan apa yang diukur, bagaimana, pada data apa, oleh siapa, dengan keterbatasan apa — dan yang sama pentingnya,
apa yang **tidak** diuji.

## Prinsip utama
- **Bukti (Evidence) adalah keluaran utama** — bertanda tangan, berantai-hash, terikat pada definisi metrik, hash sistem & dataset, seed, CI, dan keterbatasan.
- **Belum diuji ≠ lulus.** Input yang kurang, metrik yang error, backend yang tak tersedia, dan grup yang terlalu kecil menjadi *celah* yang terlihat.
- **Ambang batas adalah kebijakan Anda**, bukan kebenaran ilmiah. Nilai bawaan hanya ilustrasi.
- **Level asurans menilai *proses*** (integritas → direproduksi → diputuskan independen → diatestasi & di-anchor), bukan keamanan sistem.
- **Rekomendasi ≠ keputusan.** Keputusan dibuat manusia bernama dengan kunci sendiri; menyelisihi rekomendasi butuh alasan tertulis (override).
- **COS** (skor komposit) hanya ada sebagai *tampilan turunan*, bukan level asurans.

## Mulai cepat
```bash
pip install -e ".[dev,all]"
caterya demo --flaws pii,bias --lang id --out out/
caterya evidence verify out/bundle.json
```
```python
from caterya import AssuranceEngine, SystemConfig, CallableAdapter
engine = AssuranceEngine(SystemConfig("bot-cs", "1.0", owner="PT Contoh", intended_use="layanan pelanggan", description="asisten RAG"))
report = engine.evaluate(CallableAdapter(generate=lambda prompt, **kw: model_anda(prompt)))
print(report.summary("id"))
```

## Status kejujuran (penting)
| Komponen | Status |
|---|---|
| Inti, evidence, Merkle, DSSE, engine, guardrail, monitoring | teruji (alpha) |
| Kuantum | **riset**; simulator murni-Python + PennyLane (dicocokkan silang). **Tidak ada klaim keunggulan kuantum.** Jalur Qiskit belum diuji di CI |
| Kontrak Solidity (anchor, gate, bond) | teruji di **EVM in-process**; **belum diaudit**; belum dijalankan di jaringan publik |
| ZK | **hanya interface** — tidak ada prover |
| IPFS (Kubo) | belum diuji terhadap node nyata |
| Pemetaan regulasi | tematik & indikatif; cakupan ≠ kepatuhan; bukan nasihat hukum. `ID_AI_ETHICS_2026` berstatus **draf** — verifikasi ke teks resmi |

Tidak ada klaim performa. Jalankan `benchmarks/bench.py` di perangkat keras Anda sendiri.

Lisensi Apache-2.0 · © Caterya Tech · Ary H Haryanto (Ary HH).
