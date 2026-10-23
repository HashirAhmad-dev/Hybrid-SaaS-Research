# REFERENCES_VERIFIED.md

Save as `docs/REFERENCES_VERIFIED.md`. Claude Code keeps this file up to date.
Rule: nothing goes into the paper unless it is in section A or B with a check recorded. Section C is "leads", not citations.
Status words: CONFIRMED (record found in Crossref, arXiv, or the publisher page during this research, 2026-10-23), CHECK (looks right, re-confirm the exact field named), UNVERIFIED (do not cite yet).

---

## A. The nine references in the agreed draft, with corrections

| # | In the draft | Finding | Corrected entry |
|---|---|---|---|
| 1 | Markande et al., IEEE Access, vol. 14, pp. 59706-59720, 2026, doi 10.1109/ACCESS.2026.3683585 | CONFIRMED to exist. Author list is truncated. | Keep "S. Markande et al." (acceptable for IEEE style) or pull the full list from the IEEE Xplore page. |
| 2 | Goel et al., CE2CT 2025, doi 10.1109/ce2ct64011.2025.10939846 | CONFIRMED to exist. | Keep. Re-check page numbers on Xplore. |
| 3 | Mishra, Pagare, Sharma, Scientific Reports 15(1), 2025, doi 10.1038/s41598-025-04971-9 | CONFIRMED to exist. | Keep. |
| 4 | "S. Zhao et al.", WebPII, arXiv 2603.17357 | arXiv record CONFIRMED (title "WebPII: Benchmarking Visual PII Detection for Computer-Use Agents"). First author is **Nathan Zhao**, not "S. Zhao". | N. Zhao et al., "WebPII: Benchmarking visual PII detection for computer-use agents," arXiv:2603.17357, 2026. Re-read the author list on arXiv before finalising. |
| 5 | Shahariar, "PII-VisBench ... Online Presence", arXiv 2601.05739 | Title ending was wrong. The actual title ends "...Online Visibility". | Copy the exact title and author list from arxiv.org/abs/2601.05739. CHECK. |
| 6 | Anonymous title, "J. Electrical Systems"-type DOI 10.52783/jes.1505 | **Wrong DOI** (it resolves to a different paper on log-file anomaly detection). Wrong title. No authors. The real paper is a JISIS article. | R. M. Hernandez, D. Fuster-Guillen, L. G. P. Maluquish, M. L. C. Caycho, and M. N. A. Rivera, "Adaptive security model for e-learning platforms using multi-layered anomaly detection and context-aware risk assessment," J. Internet Serv. Inf. Secur., vol. 16, no. 1, pp. 747-759, Feb. 2026, doi: 10.58346/jisis.2026.i1.043. CONFIRMED from the paper itself. **Important:** its engine is Random Forest + LSTM + Isolation Forest (not LSTM + IF only). Its numbers (accuracy 96.8 percent, AUC 0.979) come from a blend of UNSW-NB15 and simulated logs; treat it as related work, not as validation. |
| 7 | Wang, Liu, Long, Yao, "...in Proc. IEEE FNWF, 2025, doi 10.1109/FNWF.2025.11199539" | **Wrong venue and DOI.** Real record found on Crossref. | Y. Wang, H. Liu, N. Long, and G. Yao, "Federated anomaly detection for multi-tenant cloud platforms with personalized modeling," in Proc. 5th Int. Conf. Intelligent Communications and Computing (ICICC), Nanjing, China, Aug. 2025, pp. 555-559, doi: 10.1109/ICICC66840.2025.11199539. CONFIRMED. |
| 8 | Lu, Yang, Shen, Awadallah, OmniParser, arXiv 2408.00203 | CONFIRMED earlier. Low relevance to this paper (GUI agents). | Keep only if the text really uses it. Otherwise drop it. |
| 9 | Saraswathi, ICIRCA 2025, doi 10.1109/ICIRCA.2025.394181169 | **Malformed DOI** (the number is a ResearchGate id). Real record found on Crossref. | S. Saraswathi, "Hybrid anomaly detection model integrating LSTM and Isolation Forest for enhanced performance in wireless sensor networks," in Proc. 6th Int. Conf. Inventive Research in Computing Applications (ICIRCA), Jun. 2025, pp. 509-514, doi: 10.1109/ICIRCA65293.2025.11089518. CONFIRMED. |

---

## B. Confirmed additions (usable now)

| Use in paper | Entry | Status |
|---|---|---|
| Unsupervised insider-threat detection with deep nets, CERT v6.2, compares to Isolation Forest | A. Tuor, S. Kaplan, B. Hutchinson, N. Nichols, S. Robinson, "Deep learning for unsupervised insider threat detection in structured cybersecurity data streams," arXiv:1710.00811, 2017 (AAAI-17 workshop). | CONFIRMED on arXiv |
| Closest related system: cloud API traffic, ML + NLP, risk level with endpoint type and data sensitivity | A. Abibulaiev, P. Pukach, M. Vovk, "Context-aware ML/NLP pipeline for real-time anomaly detection and risk assessment in cloud API traffic," Mach. Learn. Knowl. Extr., vol. 8, no. 1, art. 25, Jan. 2026, doi: 10.3390/make8010025. (Check the full author list on the MDPI page: mdpi.com/2504-4990/8/1/25.) | CONFIRMED to exist (MDPI page). Read it fully and position against it in related work. |
| CERT dataset | Insider Threat Test Dataset, Carnegie Mellon University KiltHub, doi: 10.1184/R1/12841247, licence CC BY 4.0. The page states it is a collection of synthetic insider-threat test datasets. | CONFIRMED (kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247). The full download is about 87 GB, so ask before downloading (gate H2). |
| Real scanned forms | G. Jaume, H. K. Ekenel, J.-P. Thiran, "FUNSD: A dataset for form understanding in noisy scanned documents," arXiv:1905.13538, 2019. 199 real scanned forms. | CONFIRMED on arXiv. CHECK licence and whether its entity labels contain PII-like fields before using. |
| Scanned receipts | Z. Huang et al., "ICDAR2019 competition on scanned receipt OCR and information extraction," arXiv:2103.10213, 2021 (1,000 receipt images). | CONFIRMED on arXiv. CHECK author list, licence, and relevance (receipts hold company, date, address, total; not people's PII). |
| Document-image PII benchmark | LeakageBench, arXiv:2609.02207 (500 document images, 11,954 PII annotations, evaluates OCR pipelines and OCR-free VLMs). | Found in the paper index only. CHECK on arxiv.org (authors, date) before citing. Very recent and directly on point. |
| Small VLM architecture (the paper's chosen model) | L. Beyer et al., "PaliGemma: A versatile 3B VLM for transfer," arXiv:2407.07726, 2024. | CONFIRMED on arXiv. CHECK author list. |
| VLM used as upper bound | S. Bai et al., "Qwen2.5-VL technical report," arXiv:2502.13923, 2025. | CONFIRMED on arXiv. CHECK author list. |
| VLM used as 4B proxy | Gemma Team, "Gemma 3 technical report," arXiv:2503.19786, 2025. | CONFIRMED on arXiv. |
| Federated averaging (future work section) | H. B. McMahan, E. Moore, D. Ramage, S. Hampson, B. A. y Arcas, "Communication-efficient learning of deep networks from decentralized data," arXiv:1602.05629, AISTATS 2017. | CONFIRMED on arXiv. |
| Log anomaly detection with LSTM | M. Du, F. Li, G. Zheng, V. Srikumar, "DeepLog: Anomaly detection and diagnosis from system logs through deep learning," in Proc. ACM CCS 2017, doi: 10.1145/3133956.3134015. | DOI CONFIRMED (it appears in the Crossref reference list of Wang et al.). CHECK title and authors on the ACM page. |
| Behaviour-aware DLP is already in a commercial product | Microsoft Learn, "Help dynamically mitigate risks with Adaptive Protection" (learn.microsoft.com/en-us/purview/insider-risk-management-adaptive-protection) and "Learn about Adaptive Protection in data loss prevention" (.../purview/dlp-adaptive-protection-learn). Content verified 2026-10-23: insider risk levels Elevated/Moderate/Minor feed DLP and Conditional Access; Elevated blocks in the quick-setup policies. | CONFIRMED. Cite as vendor documentation with an access date. |

---

## C. Leads (verify every one before use; none of these may be cited as is)

- Isolation Forest: F. T. Liu, K. M. Ting, Z.-H. Zhou, "Isolation forest," ICDM 2008, doi 10.1109/ICDM.2008.17. Well known; confirm on Crossref.
- LSTM: S. Hochreiter, J. Schmidhuber, "Long short-term memory," Neural Computation 9(8), 1997, doi 10.1162/neco.1997.9.8.1735. Confirm on Crossref.
- DP-SGD: M. Abadi et al., "Deep learning with differential privacy," ACM CCS 2016, doi 10.1145/2976749.2978318. **Not found in the paper index during this research. Confirm on Crossref before citing.**
- Pitfalls of ML in security evaluation: R. Sommer, V. Paxson, "Outside the closed world: On using machine learning for network intrusion detection," IEEE S&P 2010. Confirm.
- Insider-threat data generation: J. Glasser, B. Lindauer, "Bridging the gap: A pragmatic approach to generating insider threat data," IEEE S&P Workshops 2013. Confirm.
- Presidio: Microsoft Presidio project documentation / GitHub (cite as software with version and access date).
- EasyOCR and PaddleOCR: cite the project repositories or the PP-OCR paper after confirming the exact citation the project asks for.
- Statistical practice: cluster/block bootstrap and Wilson interval references. Choose standard textbook or paper citations and verify.
- Other hybrid LSTM + Isolation Forest papers that surfaced: Saraswathi, ICICI 2025, "Enhanced anomaly detection in wireless sensor networks using Isolation Forest, LSTM, and LSTM autoencoder," doi 10.1109/ICICI65870.2025.11069875 (seen on Crossref).

## D. Process for adding a reference

1. Look up the DOI or arXiv id. Open the record. Compare title, all authors, venue, year, pages with what you will write.
2. Add a row in section A or B with the date and the check you did.
3. If the check fails, mark UNVERIFIED and do not use it.
4. Never take a DOI from a ResearchGate URL, a model's memory, or another paper's reference list without resolving it.
