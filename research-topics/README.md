# Choosing the Research Topic

*Data fidelity and agentic AI in logistics and supply chains: three candidate topics, compared*

| Field | Detail |
|---|---|
| Prepared | 7 October 2026 |
| Theme | How the quality of the data an AI agent sees changes what it does in logistics and supply chains, and how to make agents safe to act on imperfect data |
| Constraints | Open-source only, no budget, one 128 GB DGX Spark available, must lead to a Q1 publication, a reusable benchmark and a production-grade product |
| Inputs reviewed | Your ChatGPT dossier (`data_fidelity_agentic_supply_chain_research_dossier_full.md`), your Google-search ideas A–D, the Recursive Language Models paper, and fresh web research on 2025–2026 work |
| Documents | [Topic 1](topic1_fidelity_gated_autonomy.md) · [Topic 2](topic2_spoof_resilient_logistics.md) · [Topic 3](topic3_verified_traceability.md) (each also as `.html`) |

---

> **Decision (8 October 2026):** the final topic combines Topic 2 with Topic 1's decision gate and adds carrier-commitment fidelity, which covers carriers leaving cargo at non-destination ports. The full write-up is in [final_topic_when_the_data_lies.md](final_topic_when_the_data_lies.md) (also as `.html`). This page keeps the original three-topic comparison for reference.
>
> **Corrections (9 October 2026).** Some statements on this page and in the three topic documents were later downgraded or corrected in the final topic document (Section 23). Where they differ, the final document is the one to follow:
> - The "61% of Hormuz transits were jamming artifacts" figure comes from one unaudited column with no second source. Do not use it as a headline.
> - The USD 725M figure is Verisk CargoNet's estimate of *all* US and Canada cargo-theft losses in 2025, which the FBI quotes. It is not a measure of cyber-enabled theft only.
> - The Qwen3.5 weight licence has not been verified. Apache-2.0 is confirmed for gpt-oss and Qwen3, which are the defaults until it is.
> - Jev's 70–500 ms latency comes from one third-party article and is unverified. We found no official latency figure or independent benchmark.
> - RLM-Qwen3-8B is described in several summaries of the paper's revised version, but we have not read the arXiv page itself.

## 1. The three topics in one paragraph each

**Topic 1 · Know When Not to Act** ([md](topic1_fidelity_gated_autonomy.md) · [html](topic1_fidelity_gated_autonomy.html)).
Supply-chain agents now act on their own: rebooking, rerouting, expediting, reordering. They trust whatever feed they get, and feeds are often stale, duplicated or contradictory. One bad data point can set off a chain of actions across connected agents. The topic builds a **gate** that decides, for each proposed action, whether the evidence is good enough *for that action*, with thresholds that tighten when an error would spread further through the network, and with a statistical guarantee on the rate of harmful actions. Product: **FidelityGate**, a trust layer between data feeds and any agent.

**Topic 2 · When the Data Lies** ([md](topic2_spoof_resilient_logistics.md) · [html](topic2_spoof_resilient_logistics.html)).
Location and identity data in freight are being faked at scale: GPS jamming made 61% of logged Strait of Hormuz transits in August 2026 false, and cyber-enabled cargo theft cost about $725 million in North America in 2025. Brokers now let AI agents vet and book carriers automatically, so the agent becomes the target. The topic builds agents that check physics, neighbouring vessels and identity-history graphs, and that act only when the **cost to deceive** them exceeds the value of the load. Product: **TrackTrust**, a real-time position-trust and counterparty-trust API.

**Topic 3 · Prove It Before It Ships** ([md](topic3_verified_traceability.md) · [html](topic3_verified_traceability.html)).
From December 2026 (EUDR), January 2026 (CBAM costs) and February 2027 (battery passports), goods need verified multi-tier data to enter the EU. Supplier data is messy and sometimes false, suppliers will not share raw data, and AI agents that fill in declarations can launder errors into legal filings. The topic builds an **evidence auditor** that turns supplier documents into a claim graph, checks mass balance, plot capacity, forest maps and emissions physics, and lets suppliers prove compliance without revealing secrets. Product: **ProofTrail**, a compliance-evidence copilot for exporters and importers.

## 2. Scorecard

Scores are 1 (weak) to 5 (strong). For scoop risk, 5 means *low* risk.

| Criterion | Topic 1 Gate | Topic 2 Spoofing | Topic 3 Traceability |
|---|---|---|---|
| Business pain today (money lost or deadline) | 4 | 5 | 5 |
| Fit with "data fidelity → agentic AI" theme | 5 | 4 | 4 |
| Novelty headroom against 2026 literature | 3 | 5 | 4 |
| Open data with exact ground truth | 4 | 5 | 3 |
| Feasible on one DGX Spark with no budget | 5 | 5 | 4 |
| Real-time fit | 4 | 5 | 3 |
| Product path with paying users | 3 | 5 | 5 |
| Fit with Q1 operations / transport journals | 5 | 4 | 4 |
| Scoop risk (5 = low) | 2 | 4 | 4 |
| Relevance to UAE / India | 3 | 5 | 5 |
| **Total (out of 50)** | **38** | **47** | **41** |

## 3. Recommendation

**First choice: Topic 2 (When the Data Lies), with Topic 1's gate built in as its decision layer.**

- The problem has hard numbers attached (FBI, Verisk CargoNet, Windward and the Hormuz analysis), so reviewers and industry will accept it as real.
- The open data is excellent: AIS archives and a free live AIS stream for location, and free FMCSA registry files for identity. Synthetic attacks injected on real data give exact labels.
- The core idea, Cost-to-Deceive, is new, graph-based and easy to explain, and the adaptive red-team evaluation lifts it above "another anomaly detector".
- It is genuinely real-time, which matches your production goal.
- It is close to home: Gulf logistics firms made decisions on jammed AIS data all through 2026.

**Choose Topic 1 instead** if your supervisor wants a general decision-science contribution for IJPR or EJOR and is comfortable positioning against the 2026 agent-bullwhip and agent-provenance papers.

**Choose Topic 3 instead** if you want the strongest SME market pull with a hard regulatory deadline, and you are comfortable with more synthetic data and some cryptography.

The three topics share one engine (provenance graph + fidelity estimate + typed gate + RLM investigator + BullMQ workflows), so the topic you do not pick now can be your second or third paper.

## 4. How your Google-search ideas A–D map onto the topics

| Your idea | Verdict after 2026 literature check | Where it went |
|---|---|---|
| **A. Cascading failures in multi-agent systems** | The cascade itself is now well studied: *agent bullwhip* (arXiv 2605.17036, May 2026), *From Spark to Fire* (arXiv 2603.04474), *Hallucination Cascade* (arXiv 2606.07937). Studying it alone is no longer new. | Topic 1 keeps the cascade as an **outcome** and adds what is missing: data-caused (not model-caused) instability, blast-radius thresholds and fidelity envelopes. |
| **B. Neurosymbolic data-fidelity testing** | Strong, but LLM + solver planning already exists (arXiv 2507.11352, OptiRepair). Novelty comes from applying symbolic checks to incoming evidence, not plans. | Core of Topic 1 (OR constraints in the gate) and Topic 3 (mass balance, emissions physics). |
| **C. Federated cross-border fidelity** | Federated supply-chain GNNs exist; full secure multiparty computation is heavy for a no-budget project. | Topic 3, with a staged privacy plan: verifiable credentials first, cryptographic aggregation and federated learning as extensions, and a measured "price of privacy". |
| **D. Adversarial telematics spoofing** | AIS spoof detection exists as single-track models; nobody links it to agent decisions or identity fraud. 2026 events make it urgent. | Topic 2, with Cost-to-Deceive gating and adaptive red-team evaluation. |

## 5. What I checked in your ChatGPT dossier

| Claim in the dossier | Status |
|---|---|
| RLM paper by Zhang, Kraska, Khattab (arXiv 2512.24601) and the open implementation | **Confirmed.** Also new since: RLM-Qwen3-8B (first natively recursive model) and `dspy.RLM` in DSPy ≥ 3.1.2. |
| Jev released by TypeSafe on 15 September 2026, proprietary | **Confirmed.** Typed outputs with calibrated probabilities; reported 70–500 ms latency. Keep it as an optional baseline, as the dossier says. |
| Agent-bullwhip paper (Long, Simchi-Levi et al., 2026) | **Confirmed** (arXiv 2605.17036, May 2026). |
| SupChain-Bench at Findings of ACL 2026 | **Confirmed.** |
| DHL Logistics Trend Radar 8.0 adds Agentic AI | **Confirmed** (24 September 2026). |
| FBI advisory: ~$725M cargo-theft losses in 2025, +60% | **Confirmed** (30 April 2026). |
| IJPR as the best venue, with its agentic special issue | **Needs updating.** IJPR remains a strong fit, but the special issue *The Agentic Supply Chain* closed on 30 September 2026 (extended deadline). Submit as a regular paper. |
| Figure assets in `research_assets/` | **Missing.** The dossier links nine PNG files that are not in the repository, so those images do not render. |

**Important 2026 work the dossier did not cover:** *Agentic AI Autonomy Assessment* (arXiv 2607.25405, July 2026), *From Spark to Fire* (arXiv 2603.04474), *AgentNoiseBench* (arXiv 2602.11348), *Helicase* (arXiv 2605.26835), the agent-provenance papers (arXiv 2606.04990, 2608.12761, 2609.20211), the Hormuz AIS findings (2026), Verisk CargoNet Q2 2026, Gartner's March 2026 autonomy prediction, BCG's 2026 logistics ROI survey, and the EUDR / CBAM / battery-passport deadlines. All of these are now cited in the topic documents.

The dossier's flagship idea (fidelity-aware autonomy with a risk-gated agent) survives as **Topic 1**, with a sharper formal model so it stands apart from the 2026 overlap.

## 6. Recent technologies and where each one fits

| Technology | Status (Oct 2026) | Topic 1 | Topic 2 | Topic 3 |
|---|---|---|---|---|
| **Recursive Language Models** | Open (paper Dec 2025; RLM-Qwen3-8B; `dspy.RLM`) | Investigate long shipment histories | Investigate months of AIS and identity history | Extract claims from huge supplier bundles |
| **Jev (TypeSafe System One)** | Proprietary API, released 15 Sept 2026 | Optional gate baseline | Optional gate baseline | Optional gate baseline |
| **Open "System One" gate** | Build it: small Qwen3.5 model + constrained decoding + calibration | Core | Core | Core |
| **BullMQ** | Open source (MIT); Redis 6.2+, Valkey or Dragonfly | Assess, acquire, review, execute, re-check queues | Verification and investigation flows | Per-declaration document flows, re-checks on new forest alerts |
| **Graphs** | Graphiti (bi-temporal, Apache-2.0), Postgres + Apache AGE, PyG, RelBench | Provenance graph, blast radius | Temporal heterogeneous GNN, spatial graph, Cost-to-Deceive cut | Multi-tier flow graph, plot overlap graph |
| **Conformal risk control** | Open libraries (MAPIE, crepes) | Guaranteed harmful-action rate | Calibrated alert thresholds | Calibrated claim confidence |
| **Time-series foundation models** | Chronos-2, TimesFM-2.5, Moirai-2 (open weights) | ETA and sensor plausibility | Expected track behaviour | Emissions trend checks |
| **Relational foundation models** | RelBench (open, MIT); KumoRFM-2 (proprietary); OpenRFM (open re-implementation) | Learn directly on ERP tables as graphs | Carrier tables as graphs | Supplier tables as graphs |
| **Open-weight LLMs** | Qwen3.5 family (Apache-2.0), gpt-oss-120b, Gemma 4 | Planner and agents | Investigator and red team | Extraction and regulation reasoning |
| **MCP / A2A** | Open protocols | Gate exposed as a tool; fidelity travels with messages | Pre-commit checks for booking agents | Supplier and buyer agents exchange credentials |
| **Verifiable Credentials 2.0 / UNTP** | W3C Recommendation; UNTP v1.0 targeted Sept 2026 | Optional | Carrier identity credentials | Supplier attestations |
| **OpenTelemetry GenAI + Langfuse** | Open | Audit trail | Audit trail | Audit trail for regulators |

*If by "Jev" you meant Meta's JEPA family (V-JEPA 2 world models) rather than TypeSafe's Jev, say so. JEPA would fit Topic 2 (gate cameras and seal photos) in a different way.*

## 7. Shared open-source stack on one DGX Spark

The DGX Spark has 128 GB unified memory and is rated for inference on models up to about 200B parameters and fine-tuning up to about 70B.

| Layer | Choice |
|---|---|
| Model serving | vLLM or SGLang with structured outputs (XGrammar) |
| Large model | gpt-oss-120b (MXFP4) or Qwen3.5-122B-A10B (4-bit): roughly 45–70 tokens/s single-stream reported by the community for gpt-oss-120b |
| Fast model | Qwen3.5-35B-A3B or Qwen3.5-9B |
| Recursive investigator | RLM-Qwen3-8B with the `rlms` package or `dspy.RLM` |
| Typed gate | Qwen3.5-4B, LoRA-tuned, constrained decoding, calibrated |
| Agent framework | LangGraph or DSPy; MCP for tools |
| Job workflows | BullMQ on Valkey |
| High-volume streams | Apache Kafka (KRaft) or NATS JetStream |
| Graph and geo store | PostgreSQL + Apache AGE + PostGIS + pgvector, or Neo4j Community / FalkorDB; Graphiti for bi-temporal memory |
| Graph learning | PyTorch Geometric, PyGOD |
| Optimisation and rules | OR-Tools CP-SAT, HiGHS, Pydantic schemas |
| Observability | OpenTelemetry, Langfuse (self-hosted), Prometheus, Grafana |
| Testing | pytest, Hypothesis, k6 or Locust, chaos tests |

## 8. What "will not break in production" means in practice

No system can promise it will never fail. What reviewers and customers accept is a system that **fails safely and can prove what it did**. Every topic document has a production-hardening table; the shared rules are:

1. **Fail safe.** When a model, data source or verification step is unavailable, the default is HOLD or REVIEW, never "act anyway".
2. **Idempotent side effects.** Every tender, reroute, order or filing carries an idempotency key and goes through prepare → validate → commit.
3. **Bounded autonomy.** Each action class has its own threshold and harmful-action budget, rolled out through shadow mode, then canary, then graduated autonomy.
4. **Replayable decisions.** Every decision stores the graph snapshot, model, prompt, rule and policy versions so it can be replayed exactly.
5. **Contracts at every boundary.** Typed schemas in and out; text from documents never becomes instructions.
6. **Back-pressure and limits.** Queues with rate limits, retries with jitter and dead-letter queues prevent runaway agent loops.
7. **Measured, not claimed.** Latency, throughput, recovery time and harmful-action rate are reported from load, chaos and drift tests.

## 9. Venues and open calls

"Q1" depends on the ranking and subject category, so re-check quartiles at submission time.

| Venue | Best for | Note |
|---|---|---|
| International Journal of Production Research | Topics 1, 3 | Agentic special issue closed 30 Sept 2026; regular submission still a strong fit |
| European Journal of Operational Research | Topic 1 | Needs the formal model and proofs |
| Transportation Research Part C | Topic 2 | Real-time transport technology |
| Transportation Research Part E | Topics 1, 2, 3 | Has special issues on data-driven industrial engineering (deadline 31 Dec 2026) and ML for logistics systems (30 Oct 2026); probably too soon for this project |
| IEEE Transactions on Intelligent Transportation Systems | Topic 2 | Spoofing and tracking |
| Decision Support Systems | Topics 1, 3 | Decision quality and trust |
| International Journal of Production Economics | Topic 3 | Supply-chain economics and compliance |
| Journal of Cleaner Production / Resources, Conservation & Recycling | Topic 3 | Sustainability data |
| MIS Quarterly Executive special issue on delegating work to AI agents | Product and pilot paper | Full paper due 1 March 2027 |
| NeurIPS Datasets & Benchmarks / KDD Applied Data Science | Benchmark papers for any topic | Annual cycles |

## 10. Next steps

1. Read the three topic documents and tell me which one you choose, or which parts to combine.
2. I then write the full research proposal for that topic: literature review with every paper opened and summarised, formal model with proofs, benchmark specification and a repository skeleton.
3. In parallel, ask for DGX Spark access. Months 1–4 can run on smaller models, and the Spark is needed from month 5.

## 11. Verification log

- All web research was done on 7 October 2026.
- arXiv, Gartner, BCG, Inside GNSS and several news sites could not be opened directly from the research environment because of its network policy. Their details come from search-engine extracts, which agreed across multiple searches.
- Before you cite any number in a manuscript, open the original source and check it. This applies especially to the Hormuz transit analysis, the CargoNet figures and the regulatory dates.
