# Final Topic · When the Data Lies

*Fidelity-gated, spoof-resilient AI agents that check location, identity and carrier-commitment evidence before they act in maritime and freight logistics*

| Field | Detail |
|---|---|
| Paper title (working) | When the Data Lies: Decision-Weighted Fidelity and Cost-to-Deceive Gating for AI Agents Acting on Spoofed, Stolen and Broken Logistics Evidence |
| Problem in one line | Logistics AI agents now book, reroute and release cargo automatically, but the location, identity and carrier-promise data they act on is increasingly faked, hijacked or quietly broken. |
| Solution in one line | A decision gate that scores how trustworthy the evidence is for each specific action, how expensive it would be to fake, and how far a mistake would spread, then lets the agent act, verify, escalate or wait. |
| What it combines | Topic 2 (spoofing and identity) + Topic 1 (the decision gate) + your question on carriers leaving cargo at non-destination ports, which becomes a third evidence type, "commitment fidelity" |
| First paper scope | Maritime: location fidelity (AIS/GNSS) + commitment fidelity (declared voyage vs observed execution), with the 2026 Gulf/Hormuz disruption as the real-world case |
| Later papers | Identity fidelity (carrier and vessel identity fraud); the open benchmark; a practice/policy paper |
| Recent tech used | Recursive Language Models, typed "System One" decisions (TypeSafe Jev as an optional baseline, open DSPy/vLLM equivalent as the core), two-tower retrieval, BullMQ, temporal graph learning, conformal risk control, CaMeL-style control/data separation, MCP and A2A |
| Data | Open AIS archives (US, Denmark, Norway, Finland), a free live AIS stream, IMF PortWatch, Global Fishing Watch (research use), DCSA open standards, public carrier advisories, FMCSA public registry files; attacks and deviations injected synthetically with exact labels |
| Compute | One DGX Spark (128 GB) is enough for research and the prototype |
| Product | **TrackTrust**: Commitment Watch, Position Trust, Counterparty Trust and a FidelityGate decision API for agents |
| Honest verdict | Feasible with no budget for the research, an open benchmark and a working prototype. A Q1 paper is realistic but not guaranteed. A Gulf production service will eventually need better live AIS coverage and partner shipment data. |

---

## 0. The topic in short

**Heading:** *When the Data Lies: fidelity-gated AI agents for spoofed, stolen and broken logistics evidence.*

**Summary.** Shipping and freight companies are handing decisions to AI agents. Those agents trust three kinds of evidence. **Location** comes from AIS and GPS. In 2026, jamming made about 61% of logged Strait of Hormuz transits in one month false. **Identity** is who is carrying the cargo. Cyber-enabled cargo theft through hijacked carrier identities cost about $725M in the US and Canada in 2025. **Commitment** is what the carrier promised. In March 2026 several carriers declared "End of Voyage" and left Gulf-bound cargo at substitute ports, at the cargo owner's cost.

Today's agent-security tools stop attackers from changing *what an agent is told to do*. Nothing checks *whether the facts it is given are true*. This research builds and tests that missing layer. For every action it estimates how reliable the evidence is for that action, how cheaply an attacker could fake it, and how far a mistake would spread. It then lets the agent act, verify, escalate or wait, with a measured error guarantee. It is shipped as an open benchmark and a real-time product.

**Honesty note.** Every factual claim below carries a numbered source. Numbers from vendors (Windward, Kpler, Highway, Verisk CargoNet and others) are unaudited. Several 2026 papers are preprints. Regulatory and conflict-related facts can change quickly. The sources were collected on 7–8 October 2026, and many publisher sites could not be opened directly from the research environment, so check each number against the original before citing it in a manuscript. Section 22 explains how every source was checked.

## 1. Honest verdict: can this be done with no budget, and can it be published?

| Question | Answer | Why, and what could go wrong |
|---|---|---|
| Can the research be done with open-source tools and no money? | **Yes** | Open AIS archives exist for US, Danish, Norwegian and Finnish waters [[1]](#ref-1), [[2]](#ref-2), [[3]](#ref-3), [[4]](#ref-4). The model stack (vLLM, Qwen3.5, gpt-oss, DSPy, PyTorch Geometric, BullMQ, Valkey, Kafka/NATS, PostgreSQL) is OSI-licensed [[5]](#ref-5), [[6]](#ref-6), [[7]](#ref-7). One DGX Spark runs every model needed [[8]](#ref-8), [[9]](#ref-9). |
| Is there real ground truth? | **Partly** | Our searches found no public labelled AIS-spoofing, carrier-fraud or cargo-diversion benchmark (Section 5.9). Labels come from synthetic injection on real data (exact labels) plus documented real events for case studies, such as the 2026 Gulf End of Voyage notices [[10]](#ref-10), [[11]](#ref-11), [[12]](#ref-12). Reviewers will check the synthetic-vs-real gap closely. |
| Can it run in real time? | **Yes, with the right design** | Rules, graph features and small models give sub-second decisions. A 120B model on one Spark decodes about 59 tokens/s, so large models are kept off the real-time path and used only for asynchronous investigation [[8]](#ref-8). |
| Can the commercial product be fully free? | **Not for every component** | Some data and models are non-commercial: Global Fishing Watch APIs (CC BY-NC) [[13]](#ref-13), TimesFM 3.0 and TabPFN-2.5+ [[14]](#ref-14), [[15]](#ref-15), and Jev is a paid API [[16]](#ref-16). The product must use only commercially usable parts. These remain fine as research baselines. |
| Is Gulf live coverage free? | **Uncertain** | The free real-time stream (aisstream.io) publishes no coverage or terms statement [[17]](#ref-17), [[18]](#ref-18). A product for Gulf customers may need paid AIS or a low-cost receiver feeding AISHub [[19]](#ref-19). |
| Can it be published in a Q1 journal? | **Realistic, not guaranteed** | The gaps are real and current (Section 6), and the target journals are Q1 in JCR 2025 [[20]](#ref-20). Acceptance depends on a formal contribution, leakage-aware evaluation [[21]](#ref-21), strong baselines [[22]](#ref-22) and a real-data case study. Expect 12–15 months to submission and several months of review. |
| Can it be done alone? | **Yes, if scope is controlled** | Paper 1 covers only maritime location and commitment fidelity. Identity fraud and the full product come later. Doing everything at once is the main risk. |

## 2. The problem in plain words

AI agents in logistics now act on their own. Brokers let AI agents answer inbound carrier calls and run carrier vetting [[23]](#ref-23), [[24]](#ref-24). Visibility platforms ship agents for exception handling and carrier communication [[25]](#ref-25), [[26]](#ref-26). Gartner predicts 60% of supply-chain disruptions will be resolved without human intervention by 2031 [[27]](#ref-27). These agents act on three kinds of evidence, and each can lie.

| Evidence type | The question it answers | How it lies in 2026 |
|---|---|---|
| **Location** | Where is the ship, truck or container? | GNSS jamming and spoofing move reported positions onto land or into circles and create port calls that never happened [[28]](#ref-28), [[29]](#ref-29). |
| **Identity** | Who is really carrying or calling about the cargo? | Criminals take over carrier and broker accounts, change registry records, and send a truck for a fictitious pickup [[30]](#ref-30), [[31]](#ref-31). Ships reuse the identities of scrapped vessels [[32]](#ref-32), [[33]](#ref-33). |
| **Commitment** | Will the cargo go where the carrier promised? | Carriers roll booked cargo or end the voyage at a substitute port. Shippers often learn late, through a notice or a container event [[10]](#ref-10), [[34]](#ref-34), [[35]](#ref-35). |

**Story 1: location.** In March 2026, a forwarder's ETA agent reads AIS positions for a ship approaching Jebel Ali. Jamming in the Gulf has displaced hundreds of ships' reported positions [[36]](#ref-36), [[37]](#ref-37). The agent sees the ship "stopped" 40 nm off course and books expensive alternative trucking from Sohar. The ship was on schedule. Nothing in the pipeline asked whether the position data was physically plausible, or whether every ship nearby showed the same jump.

**Story 2: identity.** A carrier with a five-year-old USDOT number calls a broker's AI agent about a high-value load. The registry record looks clean, but its contact details were changed days ago. Highway reported that about half of Q1 2026 theft incidents involved carriers with legitimate numbers and clean histories [[31]](#ref-31). Static credentials are cheap to borrow, and the agent tenders the load.

**Story 3: commitment.** A Dubai importer's container is booked to Jebel Ali. On 3 March 2026 the carrier declares End of Voyage for all Gulf-bound cargo, discharges it at the "next safe port", charges USD 800 per container and transfers custody and onward costs to the cargo owner [[10]](#ref-10), [[38]](#ref-38). The importer's planning agent still shows the original ETA, because nothing compared the carrier's commitment with what the ship was actually doing.

**What is missing.** Agent-security research defends *instruction integrity*: it stops injected text from hijacking an agent's control flow [[39]](#ref-39), [[40]](#ref-40). A well-formed but false value still passes those defences: a spoofed position, a borrowed identity, or a promise the carrier is no longer keeping. No published system estimates whether such a value is true, how costly it would be to fake, or what a wrong action would cost downstream, and then gates the agent's action on that. That is the research gap (Section 6).

## 3. Your question: carriers leaving cargo at a non-destination port

You described ships that, mid-voyage, unload contracted cargo at a port that is not its destination so they can load a higher bidder's cargo. Here is what the evidence actually shows.

### 3.1 What is documented

| Pattern | Documented? | Stated reason | Key evidence |
|---|---|---|---|
| Carrier discharges cargo at a substitute port and ends the contract there ("End of Voyage", liberty clause) | **Yes, widely in 2026** | War risk, safety, port closure | MSC declared End of Voyage for all Arabian Gulf-bound cargo on 3 March 2026, discharging at the "next safe port" with a USD 800/container surcharge and moving custody and onward cost to the cargo owner [[10]](#ref-10), [[38]](#ref-38). RCL ended voyages at Sohar, Khor Fakkan and Nhava Sheva [[11]](#ref-11). Emirates Line invoked its Clause 8 liberties at Khor Fakkan and Sohar [[12]](#ref-12). Hapag-Lloyd omitted Jebel Ali and discharged at Sohar and Fujairah [[41]](#ref-41). Maersk placed India-discharged containers at the customer's disposal at an Indian port [[34]](#ref-34). Geodis estimated 15,000–18,000 containers affected in India [[42]](#ref-42). |
| Same pattern before 2026 | **Yes** | Port closure, strikes | After the Baltimore bridge collapse (March 2024), MSC declared carriage terminated at alternate ports [[43]](#ref-43). Around the October 2024 US port strike, Vizion estimated about 2,000 shipments may have been dropped at non-destination ports [[44]](#ref-44). |
| Carrier leaves booked cargo behind (rolls it) while loading better-paying cargo | **Yes, especially 2020–2022** | Commercial (spot rates far above contract rates) | Trade press documented contract cargo bumped for spot and premium cargo [[45]](#ref-45), [[46]](#ref-46). Ocean Insights data showed 22–39% of transhipment cargo rolled at hubs in 2019–2021 [[35]](#ref-35). An FMC judge's initial decision (24 April 2026) awarded about USD 45.6M against OOCL, finding it effectively refused to deal and steered space to higher-paying alternatives. The decision is still under Commission review and challenge [[47]](#ref-47), [[48]](#ref-48). In 2024 the FMC found Hamburg Süd liable for refusal to deal and retaliation [[49]](#ref-49). |
| Carrier offloads cargo **mid-voyage at an intermediate port** specifically to load a higher bidder's cargo | **Only one trade-press report found** | Commercial | A January 2020 Loadstar report says some Asia–North Europe carriers left China-loaded boxes at transhipment hubs (Singapore, Port Klang) to make room for better-paid cargo [[50]](#ref-50). It rests on forwarder testimony, not a regulatory finding. No 2024–2026 case of this exact behaviour was found, and absence in search results is not proof that it never happens. |

**Legal context, in brief.** End of Voyage is not a doctrine of law. It comes from the carrier's own bill-of-lading clauses ("liberty", "special circumstances"), and whether cargo owners can successfully challenge it is largely untested [[51]](#ref-51), [[52]](#ref-52), [[53]](#ref-53). In the US, the FMC's 2024 rule on unreasonable refusal to deal lists insufficient notice of schedule changes and *providing inaccurate or unreliable vessel information* as examples of potentially unreasonable conduct. The D.C. Circuit upheld the rule on 31 March 2026 [[54]](#ref-54), [[55]](#ref-55). This ties data fidelity directly to a legal standard. The UAE's 2023 maritime law reportedly limits clauses that reduce carrier liability, but this comes from law-firm commentary, not the official text [[56]](#ref-56).

### 3.2 Does it fit the topic?

**Yes, as a third evidence type: commitment fidelity.** A booking, a bill of lading and a published schedule are claims about the future: this cargo, on this vessel, will be discharged at this port. AIS port calls [[57]](#ref-57), [[58]](#ref-58), DCSA container events and schedule exceptions [[59]](#ref-59), [[60]](#ref-60), and carrier advisories are independent observations of what is actually happening. The gap between the two can be measured, scored for reliability and acted on, which is exactly the job of the fidelity gate.

**What AI can and cannot do here, honestly:**

- **Can:** detect early that execution is diverging from the commitment (an omitted port call, an unscheduled call, a container discharged at a port other than its destination with no onward loading), estimate the cost exposure (storage, demurrage and detention, onward carriage), attach the clause the carrier invoked, and recommend an action (rebook, arrange onward trucking, file a dispute, notify insurer).
- **Cannot:** prove *why* a carrier did it. Opportunism, force majeure and congestion look the same in the data. The product must report "divergence and exposure", never "the carrier cheated". Accusing carriers without evidence would be wrong and legally risky.
- **Needs care:** AIS port calls can themselves be spoofed [[29]](#ref-29), and the self-reported AIS destination field is wrong very often: about 40% for large bulk ships in one study [[61]](#ref-61). Commitment checking therefore needs the location-fidelity layer underneath it, which is why the two belong in one topic.

**Research opening.** Published work detects port skipping at vessel or service level from AIS [[57]](#ref-57), [[58]](#ref-58). None found works at shipment level, attributes cause, gives calibrated uncertainty, or is robust to AIS spoofing. None encodes liberty clauses, End of Voyage notices or the FMC examples as machine-checkable rules either. Both are new contributions this project can make.

## 4. Why this matters now (evidence)

| Signal | What it says | Source |
|---|---|---|
| Location data is corrupted at scale | A measurement study of more than 367,000 vessels found 31 persistent GNSS-spoofing hotspots and 17,936 anomalous episodes. It is a preprint reported as accepted at IEEE S&P 2027. | [[28]](#ref-28), [[62]](#ref-62) |
| Gulf 2026 | Windward reported more than 1,100 vessels with GPS/AIS interference within about 24 hours after hostilities began in early March 2026. Lloyd's List counted 1,735 events across 655 vessels by 3 March. | [[36]](#ref-36), [[37]](#ref-37), [[63]](#ref-63) |
| Records can be mostly false | An August 2026 analysis found 393 of 642 logged Hormuz transits (61%) were jamming artifacts (independent analysis; re-check before citing). | [[64]](#ref-64), [[65]](#ref-65) |
| Interference continued | JMIC advisories describe interference continuing at varying intensity through at least July 2026. | [[66]](#ref-66), [[67]](#ref-67) |
| Spoofed port calls | Lloyd's List data showed ships calling at Polish ports with AIS tracks jumping to the Kaliningrad area. Analysts advised rebuilding port calls from position history. | [[29]](#ref-29) |
| Identity theft is the theft method | The FBI described an attack chain of account takeover, registry changes and freight diversion (30 April 2026). Verisk CargoNet reported about USD 725M in 2025 losses (+60%) and USD 304.6M in Q2 2026 alone, more than double Q2 2025. | [[30]](#ref-30), [[68]](#ref-68), [[69]](#ref-69) |
| Clean credentials are not enough | About 50% of Q1 2026 theft incidents involved carriers with legitimate numbers and clean histories. Communication-based attacks were 50% of fraud vectors in Q2 2026 (vendor data). | [[31]](#ref-31), [[70]](#ref-70) |
| Registry hardening moved the attack | FMCSA launched Motus with identity proofing in May 2026. Phishing that impersonates Motus followed within months. | [[71]](#ref-71), [[72]](#ref-72) |
| Maritime identity fraud | The IMO Legal Committee recorded 529 falsely flagged ships in a year (April 2026). Vortexa found more than 60 scrapped IMO numbers in active use. | [[73]](#ref-73), [[33]](#ref-33) |
| Commitment breaks | End of Voyage notices from MSC, RCL and Emirates Line; more than 270,000 TEU estimated stranded; Gulf export bookings collapsed (Vizion data). | [[10]](#ref-10), [[11]](#ref-11), [[12]](#ref-12), [[74]](#ref-74) |
| Schedules are unreliable | Sea-Intelligence reported global schedule reliability of 62.6% in June 2026. | [[75]](#ref-75) |
| AI ROI is blocked by data | BCG's 2026 survey: 97% of logistics executives call AI a priority, 13% see measurable financial impact; fragmented data is a named cause. | [[76]](#ref-76) |
| Agents are the new target | OWASP's 2026 lists put Excessive Agency at #3 and name Cascading Failures and Memory & Context Poisoning among top agentic risks. | [[77]](#ref-77), [[78]](#ref-78) |

## 5. What already exists: literature review

This section maps the published work you will build on and cite. Each stream ends with what is still missing for this project. "Preprint" marks work not yet peer-reviewed.

### 5.1 AIS and GNSS spoofing and jamming detection

| Work | What it does | Status |
|---|---|---|
| *She Spoofed Sea Ships by the Sea Shore* [[28]](#ref-28), [[62]](#ref-62) | Measures GNSS spoofing across more than 367,000 vessels by finding groups of independent ships reporting physically impossible movement at the same place and time. Finds 31 persistent hotspots and 17,936 anomalous episodes. | Preprint; reported accepted at IEEE S&P 2027 |
| SeaSpoofFinder [[79]](#ref-79) | Two stages: physically impossible jumps, then clustering across vessels. Events found in the Baltic, Black Sea and eastern Mediterranean. | Preprint, 2026 |
| Multi-vessel coherence with communication-integrity filtering [[80]](#ref-80) | Removes AIS transmission artifacts (duplicate MMSIs, stale retransmissions), then applies IMM filtering and space-time DBSCAN. Reports a 98.6% false-alarm reduction on about 966M Korean AIS messages. | Preprint, 2026 (title differs between versions) |
| Track consistency with crowdsourced ADS-B [[81]](#ref-81) | Shows that aircraft navigation-integrity flags can stay high during position anomalies, so track checks are needed. A second sensor modality for coastal interference. | Preprint, 2026 |
| Low-cost receiver monitoring [[82]](#ref-82) | Calibrated commodity GNSS receivers separate nominal, jammed and spoofed signals. | Preprint, 2025 |
| Identity-layer AIS spoofing [[83]](#ref-83), [[84]](#ref-84), [[85]](#ref-85) | MMSI validity checks, MMSI-change detection, tutorials on AIS spoofing methods. | Peer-reviewed / tutorial |
| Gulf and Baltic field evidence [[36]](#ref-36), [[37]](#ref-37), [[66]](#ref-66), [[67]](#ref-67), [[86]](#ref-86), [[29]](#ref-29), [[87]](#ref-87) | 2025–2026 vendor, advisory and press documentation of interference and spoofed port calls, including the MSC Antonia grounding attributed to interference. | Unaudited vendor and press data |

**Missing:** these papers stop at a detection label or cluster. None gives a per-decision reliability score, a cost-to-deceive measure, or a link to the actions an automated agent takes. No public, labelled, real-world AIS spoofing benchmark exists. Labels are synthetic or inferred from coherence [[88]](#ref-88), [[89]](#ref-89).

**Important for novelty:** multi-vessel coherence detection now exists [[28]](#ref-28), [[79]](#ref-79), [[80]](#ref-80). This project must not claim it as new. It uses coherence as one input to the decision gate.

### 5.2 Trajectory modelling, port calls and destination prediction

| Work | What it does |
|---|---|
| GeoTrackNet [[90]](#ref-90) | Variational recurrent model of AIS tracks plus a contrario anomaly detection (IEEE T-ITS). |
| TrAISformer [[91]](#ref-91) | Transformer over discretised AIS tokens for trajectory prediction (IEEE Access 2024). |
| DiffuTraj [[92]](#ref-92); AISFlow [[93]](#ref-93) | Diffusion-based stochastic prediction; flow matching for long-gap imputation (ICML 2026). |
| Physics-informed models [[94]](#ref-94), [[95]](#ref-95), [[96]](#ref-96) | Diffusion with kinematic constraints; space-time-prism reasoning about gaps; finite-difference kinematic losses. |
| Synthetic anomaly benchmark OMAD [[88]](#ref-88), [[97]](#ref-97) | Equation-grounded synthetic anomalies with an LLM used only as a plausibility scorer; MIT-licensed code; KDD 2026 (per README). |
| Leakage audit [[21]](#ref-21) | Shows that letting the same vessels appear in training and test data cut reported errors by 23–25% for TrAISformer and AISFormer. Vessel- and time-disjoint splits are required. |
| Destination and port-sequence prediction [[98]](#ref-98), [[99]](#ref-99), [[100]](#ref-100) | WAY (IEEE TAES) and a retrieval-enhanced, topology-masked transformer for multi-step port-of-call prediction (preprint). |
| AIS destination reliability [[61]](#ref-61), [[101]](#ref-101) | About 40% of AIS destination reports for large bulk ships were wrong (TR-E 2021); at least 52% erroneous in a German Bight study. |
| Port-call extraction [[102]](#ref-102), [[103]](#ref-103), [[104]](#ref-104) | Geofences, berth clustering and official-statistics methods. |
| Dark vessels [[105]](#ref-105), [[106]](#ref-106), [[107]](#ref-107), [[108]](#ref-108) | About 75% of industrial fishing vessels are not publicly tracked (Nature 2024). Suspected intentional AIS disabling events. Self-supervised shutdown detection. xView3-SAR dataset. |
| AIS representation learning [[109]](#ref-109), [[110]](#ref-110), [[111]](#ref-111) | Early work on masked-autoencoder and GPT-style AIS pretraining; a 2025 survey says trajectory foundation models lack systematic study. |
| LLMs on AIS [[112]](#ref-112) | AIS-LLM aligns a time-series encoder with an LLM for prediction plus natural-language explanation (preprint). |

**Missing:** these models predict where a ship *will* go or flag abnormal tracks. None tests a ship's observed track against the *contracted* port sequence for specific shipments, with uncertainty and with spoofing robustness.

### 5.3 Carrier commitments, schedules and liner revenue management

| Work | What it does |
|---|---|
| Port-skipping from AIS [[57]](#ref-57) | Data-driven framework uncovering port-skipping behaviour on about 2,000 container ships, 2016–2020 (TR-E 2023). |
| Port-call cancellations from AIS [[58]](#ref-58) | Measures cancellations on Europe–Far East services (MEL 2024). |
| Vessel Schedule Recovery Problem [[113]](#ref-113) | MIP for recovery actions including port omission (EJOR 2013). |
| Contract vs spot slot allocation [[114]](#ref-114), [[115]](#ref-115) | Risk-averse contract selection and slot allocation (TR-E 2022); dynamic programming for spot containers with cancellations (TR-E 2025). |
| Overbooking with mutual deposits [[116]](#ref-116) | Attributes overbooking to shipper–carrier mistrust and unenforceable contracts; proposes deposits with a 0.819-competitive policy (Operations Research 2026). |
| Booking cancellation prediction [[117]](#ref-117), [[118]](#ref-118) | Survival models for slot-booking cancellation (TR-C 2019, 2020). |
| Schedule unreliability [[119]](#ref-119), [[120]](#ref-120), [[75]](#ref-75) | Origins and costs of unreliability (MEL 2007); arrival punctuality prediction (MPM 2024); 2026 reliability statistics. |
| Container delay prediction [[121]](#ref-121) | Machine learning for container shipment delays (HICSS 2020). |
| Data standards [[59]](#ref-59), [[60]](#ref-60), [[122]](#ref-122), [[123]](#ref-123), [[124]](#ref-124), [[125]](#ref-125), [[126]](#ref-126) | DCSA Operational Vessel Schedules (port omission and blank sailing events), Commercial Schedules, Track & Trace, Booking 2.0, eBL 3.0 with digital signatures, Port Call 2.0; several repositories Apache-2.0. |
| US regulation [[127]](#ref-127), [[54]](#ref-54), [[55]](#ref-55), [[128]](#ref-128) | FMC rule on unreasonable refusal to deal (2024; upheld 2026); FMC data-system recommendations. |

**Missing:** this research optimises the carrier's side or measures behaviour at fleet level. Our searches found no peer-reviewed system that gives shippers early, calibrated, spoof-robust warning that a specific booking's commitment is being broken. None encodes the relevant contract clauses or regulatory examples as checkable rules either.

### 5.4 Freight and maritime identity fraud and graph anomaly detection

| Work | What it does |
|---|---|
| GADBench [[22]](#ref-22) | Benchmarks supervised graph anomaly detection. Tree ensembles with neighbourhood aggregation often beat specialised GNNs. Any GNN claim must beat this baseline. |
| TGB and TGB 2.0 [[129]](#ref-129), [[130]](#ref-130) | Temporal graph benchmarks; simple heuristics often rival complex temporal models. |
| BWGNN [[131]](#ref-131); CARE-GNN [[132]](#ref-132) | Spectral band-pass filters for anomalies; camouflage-resistant fraud detection. |
| ARC [[133]](#ref-133); UniGAD [[134]](#ref-134) | Generalist and multi-level graph anomaly detection for cold-start graphs. |
| DyGLib [[135]](#ref-135) | Unified library for temporal graph models (TGAT, TGN, DyGFormer). |
| Customs fraud: DATE [[136]](#ref-136); GraphFC [[137]](#ref-137) | Deployed customs fraud ranking under an inspection budget; GNN under label scarcity. |
| Multigraph AML [[138]](#ref-138) | Directed multigraph GNNs and synthetic AML transaction data, a template for synthetic freight-fraud data. |
| Elliptic++ [[139]](#ref-139); Elliptic2 [[140]](#ref-140); DGraph [[141]](#ref-141) | Public fraud graph datasets, all from finance and crypto. |
| LLM + graph fraud detection [[142]](#ref-142) | 2025–2026 papers combining LLMs and GNNs (curated list; individual papers not opened). |
| Document tampering: DocTamper [[143]](#ref-143) | Tampered-text detection benchmark; excludes AI-generated tampering. |
| Maritime identity fraud [[73]](#ref-73), [[144]](#ref-144), [[32]](#ref-32), [[33]](#ref-33) | False flags, fraudulent registries, zombie vessels reusing scrapped IMO numbers (IMO and vendor reports). |

**Missing:** our searches found no public labelled dataset or detector for freight-brokerage fraud (double brokering, fictitious pickups, carrier identity takeover). Graph attacks by fraud gangs are themselves a known threat to GNN detectors [[145]](#ref-145).

### 5.5 Entity resolution and two-tower (dual-encoder) models

| Work | What it does |
|---|---|
| DSSM [[146]](#ref-146); YouTube two-tower [[147]](#ref-147); DPR [[148]](#ref-148); CLIP [[149]](#ref-149) | The two-tower lineage: separate encoders for each side of a match, dot-product scoring, pre-computed candidate vectors and approximate nearest-neighbour search. |
| Hard negatives: ANCE [[150]](#ref-150); RocketQA [[151]](#ref-151); GradCache [[152]](#ref-152) | Negatives matter more than architecture; large contrastive batches on limited memory. |
| Retrieve and re-rank [[153]](#ref-153); Augmented SBERT [[154]](#ref-154) | Bi-encoder for recall, cross-encoder for precision; silver-labelling for scarce labels. |
| Late interaction: ColBERT [[155]](#ref-155); IntTower [[156]](#ref-156) | Ways to recover the fine interactions a single dot product loses. |
| Open embedders: BGE-M3 [[157]](#ref-157); Qwen3-Embedding [[158]](#ref-158); MTEB [[159]](#ref-159) | Local embedding and re-ranking models and their benchmark. |
| ER blocking: DeepBlocker [[160]](#ref-160); Sudowoodo [[161]](#ref-161); Sparkly [[162]](#ref-162) | Dense and contrastive blocking; BM25 blocking as a strong baseline. |
| ER matching: Ditto [[163]](#ref-163); Unicorn [[164]](#ref-164); MatchGPT [[165]](#ref-165); ComEM [[166]](#ref-166) | Cross-encoder and LLM matchers; "select among candidates" works best for LLMs. |
| Record linkage tools: Splink [[167]](#ref-167); Zingg [[168]](#ref-168) | Probabilistic linkage at scale; note Zingg is AGPL. |
| Trajectory representation: TrajCL [[169]](#ref-169); START [[170]](#ref-170); surveys [[171]](#ref-171), [[172]](#ref-172) | Contrastive trajectory encoders for road and taxi data; no vessel track-to-schedule model found. |

**Missing:** no two-tower model was found that matches vessel tracks against declared schedules or claimed identities. Adversarial entity resolution, where attackers deliberately create near-duplicate identities, is not addressed by mainstream tools [[173]](#ref-173), [[174]](#ref-174).

### 5.6 LLM agents in supply chains and their reliability

| Work | What it does |
|---|---|
| Agent bullwhip [[175]](#ref-175) | LLM agents in the Beer Game beat humans but show run-to-run instability that amplifies across echelons; GRPO post-training reduces tail events. |
| Agentic AI Autonomy Assessment [[176]](#ref-176) | Measures task-level autonomy; upstream tiers benefit from autonomy, downstream tiers are harmed. |
| SupChain-Bench [[177]](#ref-177) | Long-horizon tool orchestration in supply-chain SOPs remains unreliable (Findings of ACL 2026). |
| Helicase [[178]](#ref-178) | Multi-agent LLM construction of supply-chain knowledge graphs with per-fact uncertainty. |
| OptiGuide [[179]](#ref-179); InvAgent [[180]](#ref-180) | LLMs for supply-chain optimisation what-ifs; LLM multi-agent inventory management. |
| Neurosymbolic logistics planning [[181]](#ref-181) | LLM planning with uncertainty-triggered clarification. |
| AgentNoiseBench [[182]](#ref-182); τ-bench [[183]](#ref-183), [[184]](#ref-184) | Noise injected mid-trajectory hurts most; reliability over repeated runs (pass^k) falls sharply. |
| Error cascades [[185]](#ref-185), [[186]](#ref-186), [[187]](#ref-187), [[188]](#ref-188) | One false fact spreads through multi-agent systems; failure taxonomies; graph-based guards that cut infected edges. |

**Missing:** all of these use clean or randomly noisy data. None models deliberately falsified physical, identity or commitment evidence, and none gates actions on evidence reliability.

### 5.7 Agent security, provenance and governance

| Work | What it does |
|---|---|
| CaMeL [[39]](#ref-39) | Separates control flow from data flow so untrusted data cannot choose which tool runs. |
| FIDES [[40]](#ref-40) | Information-flow-control labels enforced deterministically. |
| Design patterns for securing agents [[189]](#ref-189) | Six patterns: Action-Selector, Plan-Then-Execute, LLM Map-Reduce, Dual LLM, Code-Then-Execute, Context-Minimization. |
| Benchmarks: AgentDojo [[190]](#ref-190); ASB [[191]](#ref-191); InjecAgent [[192]](#ref-192) | Prompt-injection benchmarks; ASB reports an average attack success rate of 46.91% across 13 model backbones. |
| Model hardening: StruQ [[193]](#ref-193); Meta SecAlign [[194]](#ref-194); detectors [[195]](#ref-195), [[196]](#ref-196) | Structured queries, preference-optimised open models, activation-delta and masked re-execution detectors. |
| Provenance [[197]](#ref-197), [[198]](#ref-198), [[199]](#ref-199) | Provenance integrity layers; verification-status laundering; survey of execution provenance. |
| OWASP LLM Top 10 2026 [[77]](#ref-77), [[200]](#ref-200); Agentic Top 10 [[78]](#ref-78); Agent Control Standard [[201]](#ref-201) | Excessive Agency at #3; authorisation in deterministic logic; a "Guardian" hook returning allow/deny/modify/ask/defer. |
| MCP specification [[202]](#ref-202), [[203]](#ref-203), [[204]](#ref-204); A2A [[205]](#ref-205) | Tool annotations must be treated as untrusted; human-in-the-loop is a SHOULD; MCP under Linux Foundation project governance; A2A v1.0. |

**Missing:** these protect *instruction integrity*. A well-formed but false value (a spoofed position, a cloned identity, a broken promise) passes them all. The Agent Control Standard has no field for evidence reliability, which leaves room for a standards contribution.

### 5.8 Uncertainty, conformal guarantees and deferral

| Work | What it does |
|---|---|
| Conformal risk control [[206]](#ref-206) | Chooses a threshold so that expected loss stays below a target, with finite-sample guarantees under exchangeability. |
| Conformal language modelling, factuality, enhanced methods, alignment [[207]](#ref-207), [[208]](#ref-208), [[209]](#ref-209), [[210]](#ref-210) | Guarantees for sets of outputs, claim filtering and selecting trustworthy outputs. |
| Introspective planning (vs KnowNo) [[211]](#ref-211) | Conformal prediction for when a planner should ask for help. |
| AbstentionBench [[212]](#ref-212) | LLMs, especially reasoning models, rarely abstain when they should. An external gate is needed. |
| Learning to defer [[213]](#ref-213), [[214]](#ref-214) | When to hand a decision to a human, with consistent training objectives. |
| Uncertainty of Thoughts [[215]](#ref-215) | Choosing which question to ask next by expected information gain. |
| Tools: MAPIE [[216]](#ref-216); TorchCP [[217]](#ref-217); LM-Polygraph [[218]](#ref-218) | Open conformal and uncertainty libraries. |

**Missing:** conformal guarantees assume exchangeable data, and an adaptive attacker breaks that assumption. Guarantees for multi-step agent pipelines with cost-weighted actions are thin. Only one AIS application of conformal prediction was found [[219]](#ref-219).

### 5.9 Benchmarks and what is absent

| Benchmark | Domain | Gap for us |
|---|---|---|
| GADBench [[220]](#ref-220); TGB [[221]](#ref-221); DyGLib [[222]](#ref-222); TSB-AD [[223]](#ref-223); BOND/PyGOD [[224]](#ref-224) | Graph, temporal-graph and time-series anomalies | Finance, social and generic data only |
| AgentDojo [[225]](#ref-225); ASB [[226]](#ref-226); InjecAgent [[227]](#ref-227); τ²-bench [[228]](#ref-228) | Agent security and reliability | No logistics actions; no falsified evidence |
| SupChain-Bench [[229]](#ref-229) | Supply-chain tool use | Synthetic and clean |
| EnvShip-Bench [[2]](#ref-2); OMAD [[97]](#ref-97) | AIS trajectory prediction; synthetic maritime anomalies | Not spoofing, identity or commitment; not agent decisions |

A GitHub search found no established labelled benchmark for AIS spoofing, carrier-identity fraud, or booking-vs-actual discharge deviation, and none that scores agent decisions on falsified evidence [[230]](#ref-230). A GitHub search is not a literature search, so confirm with Google Scholar before claiming novelty in a manuscript.

## 6. The gap and the contributions

**One-sentence gap.** Detection research flags anomalies, and agent-security research protects instructions. Nothing decides, for a specific automated logistics action, whether the location, identity and commitment evidence behind it is reliable enough, hard enough to fake and worth the downstream risk.

| # | Contribution | Why it is new | Closest prior work |
|---|---|---|---|
| C1 | **Decision-weighted fidelity**: reliability of evidence defined per action, with blast-radius-aware thresholds | Data-quality and anomaly scores are action-agnostic | Selective prediction [[206]](#ref-206); Chow-style reject rules |
| C2 | **Cost-to-Deceive (CtD)**: the minimum cost for an attacker to make a harmful action look justified, computed on an evidence-dependency graph with coupled channels (one GNSS spoofer corrupts AIS, ELD and trackers together) | Detectors score anomalies; none measures how expensive the evidence is to fake | Multi-vessel coherence [[28]](#ref-28), [[79]](#ref-79); out-of-band verification advice [[30]](#ref-30) |
| C3 | **Commitment fidelity**: spoof-robust, shipment-level detection of divergence between declared voyage and observed execution, with a clause-aware explanation | Prior work is fleet-level, not spoof-robust, and not tied to contracts | Port-skipping from AIS [[57]](#ref-57), [[58]](#ref-58); DCSA events [[59]](#ref-59) |
| C4 | **Fidelity-weighted quickest change detection** for commitment divergence under jamming | Change-detection theory has not been applied with per-observation evidence reliability in this setting | Classic CUSUM; schedule recovery [[113]](#ref-113) |
| C5 | **A data-veracity layer for agents** that composes with CaMeL-style control/data separation and the OWASP Guardian interface, carrying a fidelity envelope between agents | Agent defences protect instructions, not truth | CaMeL [[39]](#ref-39); FIDES [[40]](#ref-40); ACS [[201]](#ref-201) |
| C6 | **FidelityBench-Logistics**: open benchmark with location, identity, commitment and agent-attack tracks, leakage-aware splits, an adaptive red-team and real-event case studies | No such benchmark exists (Section 5.9) | OMAD [[97]](#ref-97); AgentDojo [[190]](#ref-190); RelBench as a design template [[231]](#ref-231) |

**What is deliberately not claimed as new:** multi-vessel spoofing detection, port-call extraction, GNN fraud detection and conformal prediction themselves. These are used as components and baselines.

## 7. Research questions and hypotheses

| # | Research question | Hypothesis (to be tested, not assumed) |
|---|---|---|
| RQ1 | Does action-specific fidelity reduce harmful agent actions on corrupted location data better than anomaly-score thresholds? | H1: At equal automation rate, fewer wrong reroutes and ETA-driven rebookings during jamming. |
| RQ2 | Can commitment divergence (port omission, early discharge, rolling) be detected earlier and more reliably when each observation is weighted by its fidelity? | H2: Fidelity-weighted change detection gives shorter detection delay at the same false-alarm rate under Gulf-like jamming. |
| RQ3 | Does Cost-to-Deceive gating stop more identity-fraud actions than risk scores alone? | H3: Fewer loads tendered to hijacked identities at equal automation; static credentials score low CtD. |
| RQ4 | Do conformal thresholds keep the harmful-action rate below target, and how badly do they break under an adaptive attacker? | H4: The target holds on in-distribution and drifted data. Under adaptive attack the violation is measurable, and adaptive conformal reduces it. |
| RQ5 | Is instruction integrity enough? | H5: CaMeL-style isolation blocks injected instructions but not well-formed false values; only the fidelity layer reduces the latter. |
| RQ6 | Does Recursive-LM investigation of long histories beat long-context prompting and RAG? | H6: Higher evidence recall and case-file accuracy at equal or lower cost. |
| RQ7 | Does two-tower track-to-schedule retrieval improve candidate recall for commitment matching? | H7: Higher recall than BM25 and heuristics for candidate generation; final decisions still need re-ranking and calibration. |

## 8. Concepts explained (what each one is, and how this project uses it)

Each concept below is explained simply first, then tied to its exact role in the system.

### 8.1 Domain concepts

**AIS (Automatic Identification System).** Ships broadcast their identity (MMSI, IMO number, name), position, speed, course and a hand-typed destination over VHF radio. Shore stations and satellites receive these messages. The position comes from the ship's own GNSS receiver, so if GNSS is jammed or spoofed, AIS faithfully rebroadcasts the wrong position [[232]](#ref-232), [[85]](#ref-85). *Use:* the main location evidence, always treated as a claim, never as truth.

**GNSS jamming vs spoofing.** Jamming drowns out satellite signals, so receivers lose position or report stale or erratic fixes. Spoofing transmits fake signals so receivers report a confident but false position [[85]](#ref-85), [[82]](#ref-82). Jamming affects every ship in an area. Targeted spoofing can affect one ship. *Use:* the gate treats these differently. Area-wide anomalies lower the fidelity of every position in the zone, while a single-ship anomaly raises suspicion about that ship.

**Multi-vessel coherence.** If many independent ships in the same area show the same impossible jump at the same time, the cause is the environment (interference), not the ships [[28]](#ref-28), [[79]](#ref-79), [[80]](#ref-80). *Use:* a region-level input to location fidelity, and a weak label source for the benchmark.

**Port call and port omission.** A port call is a stop at a berth or anchorage, detected from AIS speed and geofences [[102]](#ref-102), [[104]](#ref-104). A port omission is a scheduled call that never happens. DCSA schedules encode omissions and blank sailings as explicit exception events [[59]](#ref-59), [[60]](#ref-60). *Use:* the execution side of commitment checking.

**DCSA events.** DCSA standards define container events (LOAD, DISC, gate-in/out) and transport events (arrival, departure) with planned, estimated and actual classifiers [[59]](#ref-59), [[124]](#ref-124). A LOAD on a vessel other than the booked one indicates a roll. A DISC at a port other than the port of discharge, with no onward LOAD, indicates premature discharge [[59]](#ref-59). *Use:* typed commitment and execution events. The open conformance code is Apache-2.0 [[233]](#ref-233).

**End of Voyage, liberty clauses, deviation.** Bill-of-lading clauses let carriers end carriage at a substitute port in defined circumstances. Courts read them against the contract's main purpose, and the 2026 declarations are largely untested in court [[51]](#ref-51), [[52]](#ref-52), [[53]](#ref-53), [[234]](#ref-234), [[235]](#ref-235). *Use:* the legal-predicate layer labels each divergence as "explained by a notice", "disputed" or "unexplained". It never labels a divergence as fraud.

**Carrier identity takeover and double brokering.** Attackers take over real carrier or broker accounts, change registry contact details, post fake loads or re-tender real ones, and divert freight [[30]](#ref-30), [[31]](#ref-31). *Use:* the identity track and the counterparty check.

### 8.2 The project's own concepts

**Evidence fidelity vs data quality.** Data quality asks whether a record is complete and well-formed. Fidelity asks whether it faithfully represents the real world *for the decision being made*. A perfectly formatted spoofed position has high data quality and zero fidelity.

**Decision-weighted fidelity (DWDF).** The probability that acting on this evidence will not cause harm beyond a tolerance, *for this specific action*. The same AIS fix can be fit for "update the dashboard" and unfit for "book alternative trucking".

**Cost-to-Deceive (CtD).** The cheapest way an attacker could make a harmful action look justified. If the only evidence is one email, faking it is cheap. If the gate also needs a call-back to a phone number on file for years, a terminal gate event and a consistent multi-month track, faking it is expensive. The agent acts only when CtD exceeds what the action is worth to an attacker.

**Coupled channels.** Two sources are not independent if one attack corrupts both. A GNSS spoofer corrupts the AIS position, the truck ELD position and the container tracker at once. A carrier's own systems issue its booking confirmation, its schedule and its event feed. CtD counts coupled channels as one.

**Blast radius.** How far a wrong action spreads through dependent shipments, sites and agents. Computed on the dependency graph. Bigger blast radius means a stricter evidence threshold.

**Fidelity envelope.** Every message between agents carries its claim, fidelity estimate, provenance roots, verification status and CtD. Fidelity can only fall along a pipeline unless new independent evidence is added, which prevents "verification-status laundering" [[198]](#ref-198).

**Commitment fidelity.** How closely what is actually happening (port calls, container events) matches what was promised (booking, bill of lading, schedule), weighted by how trustworthy each observation is.

**Verdicts.** Every proposed action receives one of:

| Verdict | Meaning |
|---|---|
| **ACT** | Execute automatically |
| **VERIFY** | Run the cheapest verification step that would change the decision, then re-assess |
| **REVIEW** | Send to a human with the evidence pack |
| **HOLD** | Do nothing yet; re-check on a timer |
| **SHADOW** | Simulate and log only, used for new action types and new models |

### 8.3 Recent AI techniques and exactly where each fits

**Recursive Language Models (RLM).** Instead of stuffing a huge input into the prompt, the long input is stored as a variable in a sandboxed Python REPL. The model writes code to slice and filter it and recursively calls smaller models on the pieces [[236]](#ref-236), [[237]](#ref-237). The official library is MIT and works with local vLLM. DSPy 3.4 includes `dspy.RLM` [[238]](#ref-238). A natively recursive RLM-Qwen3-8B is reported in the paper's second version [[239]](#ref-239), and the repository has an RL training harness [[240]](#ref-240). *Use:* the investigator. Months of AIS history, a carrier's full registry-change history, email threads, carrier advisories and bills of lading are loaded as variables. The RLM finds the smallest evidence set that supports or refutes the action and writes a cited case file. It runs asynchronously, never on the real-time path.

**Jev and "System One" typed decisions.** TypeSafe's Jev (released 15 September 2026) generates no text. It answers typed questions about a supplied state: yes/no, choose-one, or score, with probabilities, in one parallel call [[16]](#ref-16), [[241]](#ref-241), [[242]](#ref-242). It is a paid, closed API with MIT SDKs [[243]](#ref-243), [[244]](#ref-244). Third parties report 70–500 ms latency [[242]](#ref-242). DSPy itself warns that derived confidence is not a calibrated probability [[238]](#ref-238). *Use:* an **optional baseline** for the gate's typed questions ("Is this position physically consistent?", "Verdict: ACT/VERIFY/REVIEW/HOLD"). The **reproducible core** is an open equivalent:
- DSPy 3.4's `Noul`/`Choice`/`Score` decision types running on a local model [[238]](#ref-238);
- its ReAnchor optimizer to fit thresholds [[238]](#ref-238);
- vLLM constrained decoding over the verdict enum, with probabilities from token log-probabilities [[245]](#ref-245);
- all of it calibrated with conformal risk control [[206]](#ref-206).
TypeSafe's own MIT adapter can emulate the System One API on top of a local model for side-by-side comparison [[246]](#ref-246).

**Two-tower (dual-encoder) models.** Two separate neural encoders turn each side of a match into vectors in one space, and similarity is a dot product. One side can be pre-computed and indexed, so millions of candidates are searched in milliseconds [[146]](#ref-146), [[147]](#ref-147), [[148]](#ref-148). Two-tower models are fast but lose fine interactions, so production systems retrieve with a two-tower and then re-rank with a cross-encoder or an LLM [[153]](#ref-153), [[155]](#ref-155), [[156]](#ref-156). *Use:* three retrieval jobs, never the final decision:
1. **Track-to-schedule:** one tower encodes an observed AIS track segment, with a fidelity mask over jammed points. The other encodes declared service rotations. This retrieves which declared voyage best explains a track, and flags tracks that match a different port sequence from the one contracted.
2. **Identity resolution:** one tower encodes a caller or new carrier profile (contacts, addresses, equipment, history), the other encodes registry entities. This retrieves look-alikes and past aliases, followed by Splink/Ditto/LLM matching [[167]](#ref-167), [[163]](#ref-163), [[165]](#ref-165).
3. **Similar-case retrieval:** embeds past case files so the investigator can find precedents.
Honest limits: scores are not probabilities, training needs hard negatives, and an attacker who controls the input controls the embedding. Two-tower models add fidelity only when they compare *independent* channels [[150]](#ref-150).

**Constrained decoding.** The model is forced to output only tokens that fit a JSON schema or grammar. XGrammar is the default backend in vLLM and SGLang, and llguidance computes masks in about 50 µs per token [[247]](#ref-247), [[248]](#ref-248). *Use:* every LLM output in the system is a typed object (claims, verdicts, case-file entries). Free text never drives an action.

**CaMeL-style control/data separation.** The planner sees only the trusted user task. Untrusted documents are parsed by a quarantined model into typed values that carry capability tags, and a policy checks them before any tool call [[39]](#ref-39), [[189]](#ref-189). *Use:* carrier emails, rate confirmations and advisories are parsed into typed claims. The fidelity score and provenance roots ride on each value's tag, and low-fidelity values may inform decisions but cannot authorise irreversible tools.

**Conformal risk control.** A statistical method that picks a threshold so that the expected rate of a bad outcome stays below a chosen level α, with a finite-sample guarantee, provided calibration and future data are exchangeable [[206]](#ref-206), [[216]](#ref-216). *Use:* gate thresholds per action class ("no more than 2% of automated reroutes based on false evidence"). Adaptive (online) variants handle drift during jamming episodes. Under an adaptive attacker the guarantee does not formally hold. The paper measures how badly it degrades instead of claiming it holds.

**Learning to defer and value of information.** Learning to defer trains a model to decide when a human should decide instead [[213]](#ref-213), [[214]](#ref-214). Value of information picks the next question that most reduces expected loss per unit cost [[215]](#ref-215). *Use:* the VERIFY branch chooses the cheapest verification step: a terminal API, a call-back to a registered phone number, satellite AIS, a request for a live location share.

**Quickest change detection (CUSUM).** A classic sequential test that raises an alarm as soon as evidence accumulates that a process has changed, with a controlled false-alarm rate. *Use:* commitment divergence. The process is "the ship follows its declared rotation", and each observation's contribution is weighted by its fidelity, so jammed positions count less (Section 9).

**Temporal heterogeneous graph learning.** Graph neural networks over typed nodes (vessel, carrier, phone, email domain, port, load) and time-stamped edges. TGN, TGAT and DyGFormer are implemented in DyGLib [[135]](#ref-135). *Use:* identity-hijack patterns (a contact change, then a booking burst, then a pickup far from usual lanes) and vessel behaviour. Baselines must include tree ensembles with neighbourhood features, which often win [[22]](#ref-22).

**Entity resolution.** Deciding whether two records refer to the same real-world entity: block candidates, then match pairs [[160]](#ref-160), [[161]](#ref-161), [[163]](#ref-163). *Use:* carrier, broker and vessel identities across registries, emails and documents.

**Bi-temporal knowledge graphs.** Every fact records when it was true in the world and when the system learned it. Old facts are invalidated, not deleted [[249]](#ref-249). *Use:* the evidence store. Any past decision can be replayed exactly as the agent saw it, which is essential for audit and for honest evaluation.

**GraphRAG and LightRAG.** Retrieval over a knowledge graph built from documents [[250]](#ref-250), [[251]](#ref-251). *Use:* answering "which clause did the carrier invoke and what does it allow?" over carrier terms and advisories, with citations. A human still validates the rule.

**Document AI.** Open OCR and vision-language models such as olmOCR-2, DeepSeek-OCR and Granite-Docling via Docling read scanned bills of lading and rate confirmations [[252]](#ref-252), [[253]](#ref-253), [[254]](#ref-254). None of them detects forgery, so provenance and cross-source consistency checks do that job [[143]](#ref-143), [[255]](#ref-255).

**Time-series foundation models.** Pretrained forecasters give an "expected value" to compare against, for ETAs, dwell times and sensor streams. Chronos-2 and TimesFM 2.5 are Apache-2.0. TimesFM 3.0 is non-commercial [[256]](#ref-256), [[14]](#ref-14). *Use:* plausibility features in the fidelity estimator.

**RL post-training and prompt optimisation.** GRPO and its successors (DAPO, GSPO and others) are available in TRL [[257]](#ref-257), [[258]](#ref-258). GEPA optimises prompts from execution traces with far fewer runs [[259]](#ref-259). *Use:* GEPA or DSPy optimisation first, because it is cheap. RL post-training of the small gate model is an optional extension.

### 8.4 Infrastructure concepts

**BullMQ.** An MIT-licensed job queue on Redis-compatible servers, with Node.js, Python, Rust and other clients [[260]](#ref-260), [[261]](#ref-261). *Use:* the job and workflow layer. Its open-source features fit the design directly:
- **Flows:** a parent job ("verify this tender") waits atomically for child jobs ("call-back", "ELD check", "terminal event") and collects their results.
- **Job Schedulers:** periodic re-checks of HOLD decisions and of open commitments.
- **Deduplication:** debounce and throttle repeated alerts for the same shipment.
- **Rate limiting:** stay within external API limits.
- **Retries:** exponential backoff with jitter.
- **Telemetry:** OpenTelemetry traces and metrics through `bullmq-otel`.

Groups, batches and observables are **Pro-only (paid)**, so per-tenant fairness must be built manually [[260]](#ref-260). The Python client is a "close port" that does not support every Node feature [[262]](#ref-262). Run it on **Valkey** (BSD-3) to avoid Redis 8's licence choices [[7]](#ref-7).

**Temporal (durable execution).** An MIT workflow engine that persists every step, so long-running sagas survive crashes. It has first-party integrations that route LLM and tool calls through durable activities [[263]](#ref-263), [[264]](#ref-264). *Use:* optional, for multi-day per-shipment sagas (commitment watch from booking to delivery). BullMQ remains the default for short jobs.

**Kafka and NATS JetStream.** Durable event logs for high-volume streams. Kafka 4.x is KRaft-only, and its share groups make it usable as a work queue. NATS JetStream adds message-ID deduplication [[265]](#ref-265), [[266]](#ref-266). *Use:* raw AIS and event ingestion, partitioned by H3 region. Avoid Redpanda (BSL 1.1, not OSI open source) [[267]](#ref-267).

**Sagas, idempotency, outbox and circuit breakers.**
- A saga is a chain of steps with compensations.
- An idempotent consumer with a transactional outbox gives effectively-once side effects.
- A circuit breaker stops calls to a failing dependency [[268]](#ref-268), [[269]](#ref-269), [[270]](#ref-270).

*Use:* every tender, reroute or filing is a saga step with an idempotency key. Releasing cargo is the "pivot" step, after which nothing can be undone, so it gets the strictest gate.

**MCP and A2A.** MCP connects agents to tools. Its spec says tool annotations from untrusted servers must be treated as untrusted [[202]](#ref-202). A2A connects agents to each other [[205]](#ref-205). *Use:* TrackTrust is exposed as MCP tools (`check_position`, `check_counterparty`, `watch_commitment`, `decide`). The gate is enforced in the host or client, outside the LLM, so a poisoned tool description cannot tell the agent to skip it. A2A messages carry the fidelity envelope.

**OpenTelemetry GenAI conventions and Langfuse.** Standard trace attributes for model and agent spans. These are still in "Development" status, so pin a version [[271]](#ref-271). Langfuse is MIT outside its enterprise folders and self-hostable [[272]](#ref-272). *Use:* every gate decision is a trace with its features, model versions, tokens and latency.

## 9. Formal model

### 9.1 Objects

- **Channels** *c* with compromise cost *κ_c*, grouped into **coupling groups** *g*. A group is a set of channels that one attack corrupts together, such as one GNSS spoofer, or one carrier's IT systems.
- **Sources** *s*: AIS feed, carrier event API, terminal system, registry, phone line, email account, advisory page.
- **Claims** *k*: (subject, predicate, value, valid time, recorded time, source, provenance roots).
- **Evidence-dependency graph** *D*: channels → sources → claims → decision rule.
- **Commitment** *C_b* for booking *b*: vessel, voyage, port of loading, port of discharge *d\**, declared port sequence *π_b*, planned times. Commitments are versioned with recorded time.
- **Actions** *a* with loss *L(a, S)* under the latent true state *S*, tolerance *δ_a*, review cost *r_a*, and value to an attacker *B_a*.

### 9.2 Decision-weighted fidelity

F(E, a) = P( L(a, S) − L(a\*(S), S) ≤ δ_a | E )

It is estimated by a calibrated model F̂ over features:
- kinematic residuals;
- multi-vessel coherence;
- distinct provenance roots;
- contradiction density;
- evidence age relative to process speed;
- per-source reliability (a Beta posterior updated from outcomes);
- forecast residuals;
- two-tower agreement between independent channels.

### 9.3 Cost-to-Deceive

CtD(a′; E) = min over sets of coupling groups U of Σ_{g ∈ U} κ_g,
subject to: an attacker who controls U can produce evidence E′ that passes every consistency check and makes the decision rule choose the harmful action a′.

**Proposition 1 (to be proven).** If the decision rule accepts a claim only with support from at least *m* coupling groups that share no ancestor in *D*, then CtD is at least the sum of the *m* cheapest such groups. More generally, CtD is bounded below by a minimum weighted vertex cut between an attacker super-source and the decision node in *D*.

### 9.4 The gate

ACT on *a* if and only if all three hold:
1. F̂(E, a) ≥ τ_a;
2. CtD_lb(a) ≥ B_a;
3. hard constraints pass (physics, capacity, legal).

Otherwise the gate chooses VERIFY with step v\* = argmax_v [ expected loss reduction(v) − cost(v) − λ·delay(v) ], or REVIEW, or HOLD.

**Threshold (cost-sensitive reject rule with blast radius, to be proven).** With review cost *r_a*, local harm *h_a* and blast-radius multiplier *β_a* = (1/h_a) Σ_j p_aj h_j on the dependency graph:

τ_a\* = 1 − r_a / ( h_a (1 + β_a) )

So actions whose mistakes spread further need stronger evidence.

**Calibration.** τ̂_a is chosen by conformal risk control so that E[ 1{harm and executed} ] ≤ α_a on calibration data [[206]](#ref-206). Adaptive conformal updates handle drift. Under adaptive attack, the coverage violation is measured and reported.

**Fidelity envelope composition.** If a downstream action relies on claims k₁…k_n, then F_down ≥ 1 − Σ_i (1 − F(k_i)). This is a union bound that needs no independence assumption.

### 9.5 Commitment divergence as fidelity-weighted quickest change detection

For booking *b*:
- **H₀:** execution follows *C_b*.
- **H₁ʲ:** a deviation of type *j* starts at an unknown time ν. Types: port omission, early discharge or End of Voyage, roll to another vessel, unscheduled transhipment, rotation change.

Each observation *o_t* from coupling group *g* receives a weight *w_t* = F̂(o_t) ∈ [0, 1]. For example, an AIS fix inside an active jamming cluster gets a low weight.

Sₜʲ = max( 0, Sₜ₋₁ʲ + w_t · log( f₁ʲ(o_t) / f₀(o_t) ) ), with an alarm when Sₜʲ ≥ hʲ.

Likelihood features:
- two-tower similarity between the observed track segment and the declared rotation;
- port-call match;
- remaining time slack;
- typed carrier-advisory events extracted by the LLM (for example "End of Voyage, region R, from date t");
- DCSA event mismatches (LOAD vessel ≠ booked vessel; DISC location ≠ *d\** with no onward LOAD within N days).

*hʲ* is set for a target false-alarm rate. The research question is whether fidelity weighting shortens detection delay at a fixed false-alarm rate when observations are jammed (H2).

**Legal-predicate layer.** Typed rules label each alarm, for example:
- divergence ∧ advisory(EoV, carrier, region, t) → "explained by a published notice (liberty invoked)";
- divergence ∧ no advisory ∧ notice lead time < X days on a US trade → "review against FMC 46 CFR 542 examples" [[54]](#ref-54);
- otherwise → "unexplained".

Labels never assert intent.

**Exposure.** Expected cost to the cargo owner = storage + demurrage and detention + onward carriage + delay penalties − recoverable amounts. Exposure feeds *h_a* and *β_a*.

### 9.6 Metrics defined

| Metric | Definition |
|---|---|
| Harmful-action rate | Share of executed actions whose outcome exceeds the loss tolerance |
| Automation rate | Share of proposed actions executed without a human |
| Risk–coverage curve | Harmful-action rate as a function of automation rate |
| Detection delay | Time from deviation onset to alarm, at a fixed false-alarm rate |
| Cost-to-deceive achieved | Minimum red-team budget needed to cause a harmful action |
| Calibration error | Gap between predicted fidelity and observed harm frequency (ECE, Brier) |
| Fidelity-induced bullwhip | Extra variance in downstream orders or reroutes caused by corrupted evidence, against a clean twin run |
| Latency | p50/p95/p99 time from event to verdict |

## 10. Requirements

Priorities: **M** = must have for the first paper and MVP; **S** = should have; **C** = could have later.

### 10.1 Functional requirements

| ID | Requirement | Priority | Acceptance check |
|---|---|---|---|
| FR-01 | Ingest AIS from archives (NOAA, Danish, Norwegian, Finnish) and from a live stream, decoding NMEA with `pyais` | M | Replays one month of a region at real-time speed without loss |
| FR-02 | Clean communication-layer artifacts (duplicate MMSI, stale retransmissions, timestamp errors) before any spoofing inference [[80]](#ref-80) | M | Artifact rate reported per region; cleaned and raw counts logged |
| FR-03 | Score every position for physical plausibility (speed, turn rate, land mask, gaps) | M | Per-message score with reasons |
| FR-04 | Detect area interference by multi-vessel coherence and publish active jamming zones (H3 cells × time) | M | Zones match documented 2025–2026 events in replay |
| FR-05 | Detect port calls from AIS and mark calls made inside jamming zones or gaps as low-fidelity | M | Port-call precision/recall on labelled samples |
| FR-06 | Register commitments from bookings, bills of lading (PDF via document AI) and DCSA-style schedules, versioned bi-temporally | M | Every commitment has version history and source document link |
| FR-07 | Ingest carrier advisories (End of Voyage, port omissions, surcharges) and extract typed events with the clause invoked | M | Extraction F1 on a hand-labelled set of 2026 advisories |
| FR-08 | Run fidelity-weighted change detection per active booking and raise typed divergence alarms | M | Detection delay and false-alarm rate reported |
| FR-09 | Estimate cargo-owner exposure (storage, D&D, onward carriage) per alarm | S | Exposure within a stated error band on case studies |
| FR-10 | Label each alarm with the legal-predicate layer (explained / disputed / unexplained), never asserting intent | M | No alarm text accuses a party; legal labels traceable to a rule version |
| FR-11 | Counterparty check at tender: identity-change timeline, shared-contact graph, entity resolution against registries | S (paper 2) | Risk–coverage curve on the identity track |
| FR-12 | Compute decision-weighted fidelity, blast radius and Cost-to-Deceive for every proposed action | M | Values logged with every verdict |
| FR-13 | Return ACT / VERIFY / REVIEW / HOLD / SHADOW with reasons, required evidence and an idempotency key | M | 100% of verdicts carry reasons and keys |
| FR-14 | Run verification flows (terminal API, carrier API, call-back task, satellite cross-check) with timeouts, and re-assess | M | A timeout leads to HOLD, never to ACT |
| FR-15 | Generate RLM investigator case files with cited evidence for REVIEW items | S | Claim-level accuracy on labelled cases |
| FR-16 | Human review console: evidence pack, accept/override, reason codes fed back to calibration | M | Overrides stored with reason codes |
| FR-17 | Expose everything as MCP tools and a REST API; carry fidelity envelopes in A2A messages | M | A reference agent cannot execute a gated tool without a verdict |
| FR-18 | Benchmark harness: replay, attack and deviation injection, scoring, leaderboard export | M | One command reproduces every paper table |
| FR-19 | Red-team generator: adaptive attacker with a budget, synthetic data only | S | Attack success vs budget curves |
| FR-20 | Audit replay: reconstruct any past verdict exactly from the bi-temporal store | M | Replayed verdict identical to the logged one |

### 10.2 Non-functional requirements

| ID | Requirement | Target (to be measured, not assumed) |
|---|---|---|
| NFR-01 | Position scoring latency | p95 under 100 ms per message on the fast path |
| NFR-02 | Gate latency for ACT/VERIFY decisions | p95 under 300 ms without LLM; p95 under 5 s when a small typed model is called |
| NFR-03 | Investigator latency | Case file under 2 minutes (asynchronous) |
| NFR-04 | Throughput on one DGX Spark | Sustained replay of a regional AIS feed (for example the Gulf or the Danish straits) at real-time speed or faster; measured and reported |
| NFR-05 | Availability of the gate API | 99.9% target for the hosted product |
| NFR-06 | Fail-safe behaviour | Any missing model, source or timeout → HOLD or REVIEW; never fail-open on irreversible actions |
| NFR-07 | Idempotency | Duplicate events never cause duplicate tenders, reroutes or filings |
| NFR-08 | Explainability | Every verdict lists the top evidence items, their sources and fidelity |
| NFR-09 | Auditability | Every verdict stores graph snapshot, model, prompt, rule and policy versions |
| NFR-10 | Calibration | Harmful-action rate at or below the per-class target on held-out data; violation under attack reported |
| NFR-11 | Security | Untrusted text never becomes instructions; tool descriptions pinned and hashed; gate enforced outside the LLM |
| NFR-12 | Privacy | Contact identifiers hashed; minimal personal data; retention limits |
| NFR-13 | Licensing | Product dependencies OSI-approved; non-commercial data and models used only for research baselines |
| NFR-14 | Reproducibility | Seeds, versions, data hashes and configs released with the benchmark |
| NFR-15 | Observability | OpenTelemetry traces for every job and gate decision; dashboards for latency, deferral rate and drift |

### 10.3 Data, model, legal and ethical requirements

| ID | Requirement |
|---|---|
| DR-01 | Separate real public data from synthetic injections in every file and table; label every synthetic record |
| DR-02 | Vessel-disjoint and time-disjoint splits for all trajectory tasks [[21]](#ref-21) |
| DR-03 | Record the licence and terms of each data source; block non-commercial sources from product builds [[13]](#ref-13) |
| MR-01 | Every learned model must beat the strongest simple baseline (rules, tree ensembles with neighbour features) [[22]](#ref-22) |
| MR-02 | LLMs never make the final decision on irreversible actions; they extract, explain and investigate |
| MR-03 | All LLM outputs are schema-constrained typed objects [[245]](#ref-245) |
| LR-01 | No live RF spoofing or jamming. Illegal and unnecessary; all attacks are synthetic data |
| LR-02 | Never label a real carrier, vessel or person as fraudulent in public outputs; release only synthetic identities |
| LR-03 | Divergence reports describe facts and exposure, not motive |
| LR-04 | State that the tool supports, and does not replace, legal and operational judgement |

## 11. Processes

### P1 · Position ingestion and trust scoring (real time)

1. The AIS stream arrives on Kafka or NATS, partitioned by H3 region.
2. Decode with `pyais`, validate the schema, and drop or flag communication-layer artifacts.
3. Compute physics residuals against the vessel's recent state and type.
4. Update the H3 cell × 10-minute coherence statistic. If many independent vessels show the same impossible jump, open or extend a **jamming zone**.
5. Emit a position-trust score with reasons. Store raw and scored positions in the bi-temporal store.
6. Publish zone updates to subscribers (gate, commitment watch, dashboards).

### P2 · Commitment registration

1. The user uploads a booking confirmation or bill of lading, or connects a carrier event API.
2. Document AI extracts the fields. Typed claims are created (vessel, voyage, POL, POD, ETA, clauses).
3. Entity resolution links the vessel (IMO/MMSI/name) and carrier to known entities. Two-tower retrieval proposes candidates and a matcher confirms.
4. A commitment record is created with version 1. Every later change from the carrier creates a new version; nothing is overwritten.
5. A BullMQ Job Scheduler starts a watch for the commitment.

### P3 · Commitment watch (divergence detection)

```mermaid
flowchart LR
  OBS["New observation<br/>AIS port call, container event,<br/>carrier advisory"] --> W["Weight by fidelity<br/>(jamming zone? gap? source reliability?)"]
  W --> L["Likelihood ratio per deviation type<br/>omission, early discharge, roll,<br/>transhipment, rotation change"]
  L --> S["Update weighted CUSUM statistic"]
  S -->|below threshold| WAIT["Keep watching"]
  S -->|above threshold| A["Divergence alarm"]
  A --> LEG["Legal-predicate label<br/>explained / disputed / unexplained"]
  A --> EXP["Exposure estimate<br/>storage, D&D, onward carriage"]
  LEG --> G["FidelityGate"]
  EXP --> G
  G --> OUT["Recommended action:<br/>rebook, arrange onward transport,<br/>notify insurer, open dispute, wait"]
```

### P4 · Carrier advisory ingestion

1. A scheduled job fetches public advisory pages and carrier notices (respecting robots and terms).
2. The quarantined LLM extracts typed events: carrier, notice type (End of Voyage, port omission, surcharge), region, affected services and vessels, effective date, clause invoked, charges.
3. Events are linked to open commitments by vessel, service and region.
4. Each linked commitment's watch gets a new observation (P3).

### P5 · Counterparty check at tender (identity, paper 2)

1. The booking agent proposes "tender load L to carrier X".
2. The gate calls `check_counterparty`. This builds the identity-change timeline from registry snapshots, finds shared contacts across carriers, scores with the temporal graph model, and computes CtD over the evidence channels.
3. If CtD is below the load's value to a thief, a VERIFY flow starts: call back the phone number on file for the longest time, request a live location share, check equipment.
4. Re-assess. ACT, or REVIEW with the evidence pack.

### P6 · Gate decision and verification ladder

```mermaid
sequenceDiagram
  participant A as Agent
  participant G as FidelityGate
  participant K as Graph store
  participant Q as BullMQ flows
  participant H as Human reviewer
  A->>G: propose action (type, object, value)
  G->>K: fetch evidence subgraph as of now
  K-->>G: claims, fidelity, provenance roots
  G->>G: compute F, CtD lower bound, blast radius, constraints
  alt evidence sufficient
    G-->>A: ACT + idempotency key + reasons
  else cheap check can change the decision
    G->>Q: start VERIFY flow (children with timeouts)
    Q-->>G: verification results (or timeout)
    G->>G: re-assess (timeout leads to HOLD)
    G-->>A: ACT / REVIEW / HOLD
  else high stakes or unresolved
    G->>H: REVIEW with evidence pack and RLM case file
    H-->>G: decision + reason code
    G-->>A: verdict
  end
```

### P7 · Investigation (asynchronous)

1. REVIEW items and high-exposure alarms enqueue an investigation job.
2. The RLM loads the full history as REPL variables: tracks, registry changes, advisories, emails, documents.
3. It writes code to filter, calls sub-models on slices, and assembles a case file. Every claim cites an evidence ID.
4. Conformal claim filtering marks low-confidence claims [[208]](#ref-208).
5. The case file is attached to the review item.

### P8 · Human review and feedback

1. The reviewer sees the verdict, evidence, case file and recommended action.
2. They accept, override or request more evidence, with a reason code.
3. Outcomes (was the evidence true? was the action harmful?) update per-source reliability and the calibration set.

### P9 · Calibration and model lifecycle

1. Nightly: recompute calibration per action class; run exchangeability and drift tests.
2. If the harmful-action rate on recent outcomes exceeds target, tighten thresholds automatically and alert.
3. New models go through shadow mode, then canary (one lane or region), then promotion. Every step is evaluated on the benchmark and on shadow traffic.

### P10 · Benchmark and red-team cycle

1. Build scenario: pick region, period, vessels and synthetic commitments.
2. Inject attacks and deviations with versioned, seeded operators.
3. Run each agent configuration and baseline; score; export tables.
4. Red-team: the adaptive attacker gets a budget and tries to cause harmful actions. Record cost-to-deceive achieved.
5. Publish the leaderboard with the exact commit hash.

### P11 · Incident response

1. Trigger: deferral rate spikes, a new jamming zone opens, or many divergence alarms fire on one carrier or region.
2. A circuit breaker moves the affected action classes to REVIEW-only.
3. On-call checks dashboards and sources; communicates with users.
4. Post-incident: add the pattern to the benchmark as a new scenario.

## 12. System architecture

```mermaid
flowchart TB
  subgraph Ingest
    AIS["AIS streams and archives"] --> BUS["Kafka or NATS JetStream"]
    DOCS["Bookings, B/L PDFs, carrier events, advisories"] --> BQ["BullMQ flows on Valkey"]
    REG["Registries: FMCSA files, vessel identity"] --> BQ
  end
  BUS --> PHY["Position trust + jamming zones"]
  BQ --> EXT["Document AI + quarantined LLM extraction<br/>(typed claims only)"]
  PHY --> KG["Bi-temporal evidence graph<br/>PostgreSQL + PostGIS + Apache AGE + pgvector"]
  EXT --> KG
  KG --> CW["Commitment Watch<br/>weighted CUSUM + legal predicates"]
  KG --> ID["Counterparty Trust<br/>temporal GNN + entity resolution"]
  KG --> TT["Two-tower retrieval<br/>track-to-schedule, identity, cases"]
  AGT["Agents: booking, ETA, rerouting<br/>(planner never reads raw documents)"] -->|MCP: decide| GATE["FidelityGate<br/>F, CtD, blast radius, constraints,<br/>conformal thresholds"]
  CW --> GATE
  ID --> GATE
  TT --> GATE
  PHY --> GATE
  GATE -->|ACT| EXE["Executor: idempotent saga steps"]
  GATE -->|VERIFY| BQ
  GATE -->|REVIEW| HR["Review console"]
  GATE -->|REVIEW / high exposure| RLM["RLM investigator (async)"]
  RLM --> HR
  HR --> CAL["Calibration + source reliability"]
  CAL --> GATE
  GATE --> OBS["OpenTelemetry + Langfuse"]
```

### 12.1 Components and licences (all OSI-approved unless marked)

| Layer | Choice | Licence | Note |
|---|---|---|---|
| Stream bus | Apache Kafka 4.x (KRaft) or NATS JetStream | Apache-2.0 | [[265]](#ref-265), [[266]](#ref-266) |
| Job workflows | BullMQ (open-source features only) on Valkey | MIT; BSD-3 | Pro features are paid [[260]](#ref-260), [[7]](#ref-7) |
| Long sagas (optional) | Temporal | MIT | [[263]](#ref-263) |
| Store | PostgreSQL + PostGIS + Apache AGE + pgvector | PostgreSQL; GPL-2.0+; Apache-2.0; PostgreSQL | Neo4j CE is GPLv3; FalkorDB (SSPL) and Memgraph (BSL) are not OSI [[273]](#ref-273), [[274]](#ref-274), [[275]](#ref-275) |
| Temporal memory | Graphiti | Apache-2.0 | [[249]](#ref-249) |
| Spatial index | H3 | Apache-2.0 | |
| Analytics | DuckDB + spatial | MIT | |
| LLM serving | vLLM or SGLang; llama.cpp | Apache-2.0; MIT | [[5]](#ref-5), [[276]](#ref-276) |
| Structured outputs | XGrammar / llguidance via vLLM | Apache-2.0 / MIT | [[247]](#ref-247), [[248]](#ref-248) |
| Models | gpt-oss-120b/20b; Qwen3.5/3.6 MoE; Gemma 4 | Apache-2.0 for gpt-oss; check each Qwen and Gemma weight licence | [[6]](#ref-6), [[277]](#ref-277), [[278]](#ref-278) |
| Agent programs | DSPy 3.4 (RLM, decision types, GEPA) | MIT | [[279]](#ref-279), [[238]](#ref-238) |
| Graph ML | PyTorch Geometric, DyGLib, PyGOD | MIT / BSD | [[135]](#ref-135), [[280]](#ref-280) |
| Conformal | MAPIE, TorchCP | BSD-3; LGPL | [[216]](#ref-216), [[217]](#ref-217) |
| Entity resolution | Splink; Sentence-Transformers; FAISS/Qdrant | MIT; Apache-2.0; MIT/Apache-2.0 | Avoid Zingg (AGPL) in the product [[167]](#ref-167), [[168]](#ref-168) |
| Document AI | Docling + Granite-Docling; olmOCR-2 | MIT; Apache-2.0 | [[254]](#ref-254), [[252]](#ref-252) |
| Forecasting | Chronos-2; TimesFM 2.5 | Apache-2.0 | Not TimesFM 3.0 in the product [[256]](#ref-256), [[14]](#ref-14) |
| Observability | OpenTelemetry; Langfuse | Apache-2.0; MIT (non-ee) | Phoenix is Elastic License 2.0 [[272]](#ref-272), [[281]](#ref-281) |
| Testing | pytest, Hypothesis, Locust; Chaos Mesh | MIT / MPL / Apache-2.0 | k6 is AGPL (fine as an unmodified test tool) |

## 13. Data plan

| Data | Access | Use | Terms caveat |
|---|---|---|---|
| NOAA MarineCadastre AIS (US waters; daily files for 2025) | Free download | Training, replay, benchmark | Metadata gives no licence; redistribution terms ambiguous [[282]](#ref-282), [[1]](#ref-1), [[2]](#ref-2) |
| Danish Maritime Authority AIS | Free download | Training, replay; used by TrAISformer and EnvShip-Bench | Conditions of use apply [[283]](#ref-283), [[284]](#ref-284) |
| Norwegian Coastal Administration AIS | Open API tier | Replay, validation | Open tier excludes small craft [[3]](#ref-3), [[285]](#ref-285) |
| Finnish AIS dataset (2021–2022) | Zenodo, CC BY 4.0 | Training | Record count disputed between sources [[4]](#ref-4) |
| aisstream.io live stream | Free API key | Live demo, Gulf monitoring | No published SLA, coverage or terms [[17]](#ref-17), [[18]](#ref-18) |
| Global Fishing Watch APIs (port visits, AIS gaps, SAR detections) | Free token | Research labels and cross-checks | CC BY-NC: research only, not product [[13]](#ref-13), [[286]](#ref-286) |
| Copernicus Sentinel-1 SAR | Free tier (12 TB/month) | Dark-vessel and spoof cross-checks for case studies | Revisit is days, not real time [[287]](#ref-287) |
| IMF PortWatch chokepoint transits | Free | Context for Hormuz and Red Sea case studies | Terms not verified [[288]](#ref-288) |
| DCSA standards and conformance code | Free, Apache-2.0 | Event and schedule schemas | Newest Track & Trace 3.0 public only in H2 2027 [[289]](#ref-289), [[233]](#ref-233) |
| Carrier advisories (MSC, RCL, Emirates Line, Hapag-Lloyd, Maersk) | Public web pages | Hand-built 2026 End of Voyage dataset linked to vessels | Respect site terms; store citations [[10]](#ref-10), [[11]](#ref-11), [[12]](#ref-12), [[34]](#ref-34), [[41]](#ref-41) |
| CMA CGM Track & Trace API (DCSA based) | API key | Real container events for test bookings | Free tier not confirmed [[290]](#ref-290) |
| FMCSA Company Census and authority files | Public domain | Identity track (paper 2) | Real small-company contact data: release only synthetic identities [[291]](#ref-291) |
| Synthetic commitments, attacks and deviations | Generated | Exact labels | Always labelled synthetic |

**The 2026 Gulf case study.** Build a small, documented dataset from the public 2026 notices: carrier, date, region, clause invoked, substitute ports, named vessels where given (RCL named several) [[11]](#ref-11). Link it to AIS tracks of those vessels where coverage exists (GFW for research use). This gives real, citable examples of commitment divergence under heavy jamming, which no existing benchmark has.

## 14. Benchmark: FidelityBench-Logistics

| Track | Base data | Injected cases (labelled) | Agent decisions scored |
|---|---|---|---|
| Location | NOAA, Danish, Norwegian, Finnish AIS | Area jamming (circle and airport-displacement patterns), targeted spoofing, MMSI cloning, spoofed port calls, dark periods | ETA updates, reroutes, alternative-transport bookings |
| Commitment | Real tracks + synthetic bookings on real services; 2026 Gulf notices as real cases | Port omission, early discharge/End of Voyage, roll, unscheduled transhipment, rotation change; with and without jamming | Rebook, arrange onward transport, dispute, wait |
| Identity | FMCSA public data → synthetic identities; vessel identity records | Contact-change hijack, dormant-authority reactivation, shared-contact rings, double brokering, zombie IMO reuse | Tender or not; which verification |
| Agent attack | Synthetic emails, rate confirmations, advisories | Prompt injection, authority framing, forged documents, well-formed false values | Whether the agent's decision changes |

**Rules.**
- Vessel- and time-disjoint splits [[21]](#ref-21).
- Fixed seeds.
- Every operator versioned.
- Clean twin runs for every corrupted run.
- Adaptive red-team rounds with fixed budgets.
- Leaderboard on the RelBench pattern: fixed tasks, temporal splits, submission validator [[231]](#ref-231).
- Code Apache-2.0. Data released only where source terms allow, with download scripts otherwise.

## 15. Experiments, baselines and statistics

| ID | Baseline | Why it is there |
|---|---|---|
| B0 | Rules (speed, land mask, registry checks, schedule diff) | What industry does today |
| B1 | Single-track detectors (GeoTrackNet-style, Bi-LSTM, autoencoder) | Literature baselines [[90]](#ref-90) |
| B2 | Multi-vessel coherence detector | Strongest 2026 detection idea [[28]](#ref-28), [[79]](#ref-79) |
| B3 | Tree ensemble with neighbour features; static and temporal GNNs | Graph baselines that must be beaten [[22]](#ref-22), [[135]](#ref-135) |
| B4 | LLM agent with tools, no gate | Naive autonomy |
| B5 | Agent with LLM self-confidence gate | Tests "the model knows when it is wrong" (it usually does not) [[212]](#ref-212) |
| B6 | Agent with CaMeL-style isolation, no fidelity layer | Tests instruction integrity alone [[39]](#ref-39) |
| B7 | Jev as the typed gate (optional) | Proprietary System One comparator [[16]](#ref-16) |
| Full | Fidelity + CtD + weighted change detection + conformal thresholds + RLM investigator | Proposed system |

**Experiments:**
1. Harm map: fault type × severity × action type.
2. Risk–coverage curves for all gates.
3. Detection delay at fixed false-alarm rate for commitment divergence, with and without jamming.
4. Adaptive red-team: harmful actions vs attacker budget.
5. Instruction-integrity vs data-veracity ablation (B6 vs Full).
6. RLM vs long-context vs RAG investigation at equal cost.
7. Two-tower vs BM25 vs heuristics for candidate recall.
8. Systems test: bursts, slow sources, worker kills, duplicate events.
9. Gulf 2026 case study.

**Statistics.**
- Paired runs on the same latent world.
- At least 30 seeds per configuration.
- Bootstrap confidence intervals.
- Holm correction for multiple comparisons.
- Pre-registered primary metrics: harmful-action rate at fixed automation, and detection delay at a fixed false-alarm rate.

## 16. Compute plan (one DGX Spark)

| Workload | Model or tool | Evidence it fits |
|---|---|---|
| Large planner / investigator / red team (offline) | gpt-oss-120b (MXFP4) | Measured on one Spark: about 58.7 tokens/s decode and about 2,444 tokens/s prefill at empty context; about 42.8 tokens/s decode at 32k context (llama.cpp) [[8]](#ref-8) |
| Fast typed gate | Qwen3.5 small model (4B–9B) or gpt-oss-20b, constrained decoding | gpt-oss-20b measured at about 83 tokens/s decode on one Spark [[8]](#ref-8) |
| Mid-size agent model | Qwen3.5-35B-A3B or Qwen3.6-35B-A3B | Released Feb–Apr 2026; single-Spark recipes exist but throughput not verified [[277]](#ref-277), [[292]](#ref-292) |
| RLM sub-calls | Small Qwen or gpt-oss-20b | As above |
| GNNs, entity resolution, change detection | PyTorch Geometric, Splink, NumPy | CPU/GPU, small memory |
| Embeddings | BGE-M3 or Qwen3-Embedding | Local [[157]](#ref-157), [[158]](#ref-158) |

**Design consequence:** at about 59 tokens/s, a 500-token answer from the 120B model takes several seconds. The real-time gate therefore uses rules, graph features and small models, and the large model works only asynchronously [[8]](#ref-8), [[9]](#ref-9). LMSYS likewise found the Spark better suited to smaller models and batching than to large-model production serving [[9]](#ref-9).

## 17. Product: TrackTrust

**What it is.** A real-time trust layer for logistics decisions, with four modules sharing one evidence graph:

| Module | Question it answers | First users |
|---|---|---|
| **Commitment Watch** (MVP) | "Is my container still going where I paid for it to go? If not, what will it cost me and what should I do?" | Dubai and India importers, exporters and forwarders hit by 2026 End of Voyage discharges [[42]](#ref-42), [[34]](#ref-34) |
| **Position Trust** | "Can I trust this ship's position and ETA right now?" | Forwarders, port and terminal planners, marine insurers |
| **Counterparty Trust** | "Is this carrier or caller really who they claim to be?" | Small and mid-size brokers and shippers |
| **FidelityGate API** | "Should my AI agent act on this?" | Teams building booking, dispatch and voice agents |

**MVP scope (months 6–10).**
- Commitment Watch and Position Trust for Gulf, Red Sea and India lanes.
- Inputs: bookings and bill-of-lading PDFs, live AIS (free stream plus any partner feed), public advisories, carrier event APIs where available.
- Outputs: divergence alerts with exposure estimate, clause context and an evidence pack the user can attach to a dispute or insurance notice.

**API sketch.**

```json
POST /v1/decide
{
  "action": {"type": "book_onward_trucking", "shipment_id": "SHP-88213", "value_usd": 4200},
  "evidence_refs": ["ais:pos:9876543:2026-03-04T06:10Z", "adv:MSC:EoV:2026-03-03", "dcsa:DISC:SHP-88213"],
  "context": {"region": "Arabian Gulf"}
}

200 OK
{
  "verdict": "VERIFY",
  "fidelity": 0.58,
  "threshold": 0.85,
  "cost_to_deceive_lower_bound_usd": 300,
  "blast_radius": 1.8,
  "reasons": [
    "vessel position inside active jamming zone H3:8a2a... since 05:40Z",
    "End of Voyage notice from carrier covers this region and date",
    "no DISC event yet at the substitute port"
  ],
  "next_evidence": [{"type": "terminal_event_check", "port": "OMSOH", "max_wait_s": 900}],
  "idempotency_key": "SHP-88213:book_onward_trucking:v2",
  "decision_id": "dec_..."
}
```

**Production hardening (so it does not break).**

| Concern | Practice |
|---|---|
| Duplicate side effects | Idempotency keys; idempotent consumers with transactional outbox; saga steps with compensations [[269]](#ref-269), [[270]](#ref-270) |
| Dependency outage | Circuit breakers; rules-only fallback with stricter thresholds; default HOLD for irreversible actions [[268]](#ref-268) |
| Jamming bursts | Partition streams by region; queue-based load levelling; backpressure; autoscaling consumers |
| Verification hangs | BullMQ flows with timeouts; timeout leads to HOLD |
| Prompt injection via documents | Quarantined extraction into typed claims; planner never reads raw text; tool descriptions pinned and hashed; gate enforced in the host [[39]](#ref-39), [[202]](#ref-202) |
| Silent drift | Nightly calibration; drift and exchangeability tests; automatic threshold tightening |
| Audit | Event-sourced decision log with all versions; bi-temporal replay |
| Release safety | Shadow mode, then canary region, then promotion; benchmark gate in CI |
| Testing | Property-based tests, load tests with Locust, chaos tests (kill workers, delay sources) with Chaos Mesh |

**Business model.**
- Open core: the gate engine, benchmark and connectors are Apache-2.0.
- A free tier for small exporters (limited shipments per month).
- Paid: hosted service, premium AIS sources, ERP and TMS connectors, compliance reports.
- Data cost is the main running cost. Start with free sources and a partner forwarder's own data.

**Competitors.** Maritime intelligence (Windward, Kpler, Pole Star), visibility platforms (project44, FourKites, Vizion) and carrier vetting (Highway). All are closed. TrackTrust differs in four ways:
- it is agent-native, through MCP tools and a decision API;
- it measures cost-to-deceive explicitly;
- it puts clause context on divergences;
- its benchmark and method are open, and it is priced for small and mid-size firms in the Gulf and India.

## 18. Risks, ethics and legal

| Risk | Mitigation |
|---|---|
| Novelty challenged (multi-vessel detection now exists) | Claim the decision layer, CtD, commitment fidelity and the benchmark, not detection; cite the 2026 papers directly [[28]](#ref-28), [[79]](#ref-79) |
| Synthetic labels criticised | Real-event case studies (Gulf 2026 notices, Baltic events), hand-labelled samples, leakage-aware splits |
| Gulf live coverage too thin | Use archives for science; position the live product as best-effort until a partner feed exists; a low-cost receiver can feed AISHub [[19]](#ref-19) |
| Conformal guarantee broken by attackers | Report it honestly; use adaptive conformal; red-team evaluation as a primary result |
| Defamation / accusing carriers | Report divergence and exposure only; legal labels from published notices; human review |
| Licence violations | Research-only data and models kept out of product builds (GFW, TimesFM 3.0, TabPFN-2.5+, Jev) [[13]](#ref-13), [[14]](#ref-14), [[15]](#ref-15) |
| Dual use (attackers learn) | Publish methods and synthetic benchmark; keep production thresholds private; responsible-disclosure note |
| Personal data (FMCSA contacts) | Hash identifiers; never publish real identities; synthetic release only |
| Scope creep | Paper 1 = maritime location + commitment only |
| Regulatory change | Rules as versioned code with effective dates [[55]](#ref-55) |

**Do not claim:**
- that the system detects all spoofing or proves carrier motive;
- that synthetic attack rates reflect real-world frequency;
- that Jev is open;
- that conformal guarantees hold against adaptive attackers;
- that the product is "production-safe" before the stress tests in Section 15 are passed.

## 19. Plan (15 months, October 2026 to December 2027)

| Months | Work | Output |
|---|---|---|
| Oct–Nov 2026 | Read the core papers in full; formal model; proofs of Propositions; data pipeline for NOAA/DMA/Norway/Finland | Problem-formulation draft |
| Nov 2026–Jan 2027 | Location track (coherence, physics, port calls); commitment schema; 2026 Gulf advisory dataset | Benchmark v0.1 |
| Jan–Mar 2027 | Baselines B0–B6; weighted change detection; first gate | First results tables |
| Mar–May 2027 | CtD, conformal calibration, RLM investigator; red-team; benchmark v1.0 | Benchmark paper submission (NeurIPS 2027 Datasets & Benchmarks track, deadline expected around May 2027; inferred, check) [[293]](#ref-293) |
| May–Aug 2027 | TrackTrust MVP (Commitment Watch + Position Trust); pilot with a forwarder if possible | Working product |
| Aug–Oct 2027 | Full experiments, Gulf case study, writing | **Paper 1** submitted to TR-E or TR-C |
| Oct–Dec 2027 | Identity track; Counterparty Trust | **Paper 2** draft (IEEE T-ITS or Computers & Security) |

Journal review typically takes several months to a year, so a Q1 acceptance is most likely in 2028.

## 20. Target venues

JCR 2025 impact factors and quartiles below come from a third-party compilation of Clarivate data [[20]](#ref-20). Confirm them through your library before relying on them.

| Venue | JCR 2025 IF / quartile | Best for |
|---|---|---|
| Transportation Research Part E | 9.3 / Q1 | Paper 1 (logistics, commitment, maritime) |
| Transportation Research Part C | 8.4 / Q1 | Paper 1 (real-time AI in transport) |
| IEEE Transactions on Intelligent Transportation Systems | 9.1 / Q1 | Spoof-resilient trajectory and graph methods |
| Reliability Engineering & System Safety | 13.7 / Q1 | Risk-controlled gate and guarantees |
| Decision Support Systems | 7.5 / Q1 | Decision-gating framing |
| Computers & Security | 6.8 / Q1 | Identity and adversarial track (paper 2) |
| Maritime Economics & Logistics | 6.8 / Q1 | Commitment breaches and policy companion paper |
| Maritime Policy & Management | 4.4 / Q2 | Policy and legal-informatics angle |
| International Journal of Production Economics; IJPR; EJOR | 10.6; 8.7; 7.0 / Q1 | Operations framing |

**Conferences** (from the community ccf-deadlines files; confirm on official sites) [[293]](#ref-293), [[294]](#ref-294):
- Most deadlines still open in late 2026 are too soon for full results: The Web Conference 2027 (25 Oct 2026), ICDE 2027 round 2 (11 Nov 2026), IEEE S&P 2027 second deadline (17 Nov 2026).
- USENIX Security 2027 cycle 2 (26 Jan 2027) could suit an early agent-attack study.
- NeurIPS 2027 Datasets & Benchmarks (expected about May 2027) and KDD 2027 round 2 (date not yet listed) suit the benchmark.

## 21. References

Numbered in order of first citation. Each entry ends with how it was checked: *re-verified* (an independent second check confirmed it), *re-verified with corrections*, *seen once* (found by one researcher in search results or a fetched page and not re-checked), or *CHECK* (open the original before citing). Vendor statistics are unaudited.

<a id="ref-1"></a>1. *ocm-marinecadastre/ais-vessel-traffic*. NOAA Office for Coastal Management (GitHub), 2025-2026. <https://github.com/ocm-marinecadastre/ais-vessel-traffic> — fetched page.

<a id="ref-2"></a>2. mark000071 (GitHub handle). *EnvShip-Bench: An Environment-Enhanced Benchmark for Short-Term Vessel Trajectory Prediction (code release)*. GitHub / Hugging Face; MM 2026 Dataset Track (under review), 2026. <https://github.com/mark000071/EnvShip-Bench_Large_Dataset_Pipeline_and_datasets> — fetched page.

<a id="ref-3"></a>3. *Access to all AIS data (Kystverket)*. Norwegian Coastal Administration, n.d.. <https://kystverket.no/en/navigation-and-monitoring/ais/access-to-ais-data> — seen in search results.

<a id="ref-4"></a>4. Debayan Bhattacharya, Carlos Pichardo Vicencio, Ikram Ul Haq, Sébastien Lafond (Åbo Akademi). *A Large-Scale AIS Dataset from Finnish Water*. arXiv; Zenodo dataset under CC BY 4.0, 2026. <https://arxiv.org/pdf/2609.12938> — seen in search results.

<a id="ref-5"></a>5. vLLM project. *vllm-project/vllm LICENSE*. GitHub, 2026. <https://raw.githubusercontent.com/vllm-project/vllm/main/LICENSE> — fetched page.

<a id="ref-6"></a>6. *openai/gpt-oss*. GitHub (OpenAI), 2025. <https://github.com/openai/gpt-oss> — fetched page.

<a id="ref-7"></a>7. Valkey contributors. *valkey-io/valkey COPYING*. GitHub, 2024. <https://raw.githubusercontent.com/valkey-io/valkey/unstable/COPYING> — fetched page.

<a id="ref-8"></a>8. ggml-org. *llama.cpp benches/dgx-spark/dgx-spark.md*. GitHub, 2026 (undated; build 7941). <https://raw.githubusercontent.com/ggml-org/llama.cpp/master/benches/dgx-spark/dgx-spark.md> — fetched page.

<a id="ref-9"></a>9. LMSYS Org. *NVIDIA DGX Spark In-Depth Review (LMSYS blog source, 2025-10-13)*. LMSYS blog, 2025. <https://raw.githubusercontent.com/lm-sys/lm-sys.github.io/main/blog/2025-10-13-nvidia-dgx-spark.md> — seen in search results.

<a id="ref-10"></a>10. MSC Mediterranean Shipping Company. *Important Notice End of Voyage Declaration for Exports from the Arabian and Persian Gulf*. MSC customer advisory, 2026. <https://www.msc.com/en/newsroom/customer-advisories/2026/march/important-notice-end-of-voyage-declaration-for-exports-from-the-arabian-and-persian-gulf> — seen in search results.

<a id="ref-11"></a>11. Regional Container Lines (RCL). *CUSTOMER ADVISORY #04 : Service RWG2 Update to Middle East*. RCL customer advisories (also NEWS1339 #03-1, NEWS1341 #06-1); trade-press coverage at https://container-news.com/rcl-declares-end-of-voyage-for-middle-east-shipments and https://breakbulk.news/?p=50603, 2026. <https://rclgroup.com/PressReleaseArticle/NEWS1332> — seen in search results.

<a id="ref-12"></a>12. Emirates Shipping Line. *Customer Advisory ESL BUSAN 2606*. Emirates Line customer advisories (also https://www.emiratesline.com/wp-content/uploads/2026/04/Customer-Advisory-ESL-Sana-v-2605-RED-SEA.pdf), 2026. <https://www.emiratesline.com/wp-content/uploads/2026/03/Customer-Advisory-ESL-BUSAN-2606.pdf> — seen in search results.

<a id="ref-13"></a>13. *License and Rate Limits (Global Fishing Watch APIs)*. Global Fishing Watch, n.d.. <https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits> — seen in search results.

<a id="ref-14"></a>14. *google-research/timesfm*. GitHub (Google Research), 2025-2026. <https://github.com/google-research/timesfm> — fetched page.

<a id="ref-15"></a>15. *PriorLabs/TabPFN*. GitHub (Prior Labs), 2025-2026. <https://github.com/PriorLabs/TabPFN> — fetched page.

<a id="ref-16"></a>16. TypeSafe AI <support@typesafe.ai>. *typesafe-sdk (PyPI JSON metadata and wheel 0.7.2 source)*. PyPI, 2026. <https://pypi.org/pypi/typesafe-sdk/json> — fetched page.

<a id="ref-17"></a>17. *aisstream/aisstream*. GitHub (aisstream.io), n.d.. <https://github.com/aisstream/aisstream> — fetched page.

<a id="ref-18"></a>18. aisstream.io. *aisstream (GitHub org and repos: aisstream, example, issues, ais-message-models)*. GitHub, 2026. <https://github.com/aisstream> — fetched page.

<a id="ref-19"></a>19. *AISHub provider profile*. API Evangelist (third-party), n.d.. <https://providers.apievangelist.com/providers/aishub/> — seen in search results.

<a id="ref-20"></a>20. hitfyd (compiler); underlying data Clarivate JCR. *ShowJCR (JCR 2025 / CAS partition data compilation) – JCR2025-UTF8.csv*. GitHub, 2026. <https://github.com/hitfyd/ShowJCR> — fetched page.

<a id="ref-21"></a>21. Zobeir Raisi et al.. *Protocol before progress: leakage-aware evaluation of AIS trajectory prediction*. arXiv (22 Sep 2026), 2026. <https://arxiv.org/pdf/2609.25827> — seen in search results.

<a id="ref-22"></a>22. Jianheng Tang, Fengrui Hua, Ziqi Gao, Peilin Zhao, Jia Li. *GADBench: Revisiting and Benchmarking Supervised Graph Anomaly Detection*. NeurIPS 2023 Datasets and Benchmarks, 2023. <https://proceedings.neurips.cc/paper_files/paper/2023/hash/5eaafd67434a4cfb1cf829722c65f184-Abstract.html> — fetched page.

<a id="ref-23"></a>23. Highway (press release). *CloneOps.ai and Highway Announce Strategic Integration to Automate Carrier Screening and Fraud Prevention*. Highway, 2025. <https://highway.com/press-releases/cloneops-ai-and-highway-announce-strategic-integration-to-automate-carrier-screening-and-fraud-prevention> — seen in search results.

<a id="ref-24"></a>24. FreightWaves. *Transfix integrates Highway carrier vetting into TMS*. FreightWaves, 2026. <https://www.freightwaves.com/news/transfix-integrates-highway-carrier-vetting-into-tms> — seen in search results.

<a id="ref-25"></a>25. Rework. *Best AI Agents for Supply Chain in 2026: 14 Agents for Planning, Procurement, and Disruption Response*. Rework resources, 2026. <https://resources.rework.com/tools/ai-agents/best-ai-agents-for-supply-chain-2026> — seen in search results.

<a id="ref-26"></a>26. IT Brief UK. *FourKites unveils AI agents Tracy & Sam for efficiency boost*. IT Brief, 2025. <https://itbrief.co.uk/story/fourkites-unveils-ai-agents-tracy-sam-for-efficiency-boost> — seen in search results.

<a id="ref-27"></a>27. Gartner. *Gartner Predicts 60% of Supply Chain Disruptions Will Be Resolved Without Human Intervention by 2031*. Gartner press release 18 March 2026, 2026. <https://www.gartner.com/en/newsroom/press-releases/2026-03-18-gartner-predicts-60-percent-of-supply-chain-disruptions-will-be-resolved-without-human-intervention-by-2031> — seen in search results.

<a id="ref-28"></a>28. Georgia Institute of Technology researchers (per news coverage; individual names not captured). *She Spoofed Sea Ships by the Sea Shore: Measuring Large-Scale GPS Spoofing in Global Maritime Traffic*. arXiv (cs.CR); reported to appear at IEEE S&P 2027, 2026. <https://arxiv.org/abs/2609.37676> — seen in search results.

<a id="ref-29"></a>29. *AIS Spoofing surges in Baltic and Barents Seas*. Kuehne+Nagel (relaying Lloyd's List), 2025. <https://mykn.kuehne-nagel.com/news/article/ais-spoofing-surges-in-baltic-and-barents-sea-31-Mar-2025> — seen in search results.

<a id="ref-30"></a>30. FBI / IC3. *Internet Crime Complaint Center (IC3) PSA I-043026-PSA: Cyber-Enabled Strategic Cargo Theft Surging*. FBI Internet Crime Complaint Center, 2026. <https://www.ic3.gov/PSA/2026/PSA260430> — seen in search results.

<a id="ref-31"></a>31. AJOT (reporting Highway Q1 2026 index). *Vetted carriers are behind half of all freight theft as fraud hits a Q1 record*. American Journal of Transportation, 2026. <https://www.ajot.com/news/vetted-carriers-are-behind-half-of-all-freight-theft-as-fraud-hits-a-q1-record> — seen in search results.

<a id="ref-32"></a>32. Lloyd's List (with SynMax Intelligence). *From zombie tankers to fake IMO numbers: the identity frauds now playing out at sea*. Lloyd's List, 2025. <https://www.lloydslist.com/LL1155512/From-zombie-tankers-to-fake-IMO-numbers-the-identity-frauds-now-playing-out-at-sea> — seen in search results.

<a id="ref-33"></a>33. Vortexa. *Hidden Capacity: The Rise of Zombie Tankers*. Vortexa, 2025. <https://www.vortexa.com/insights/zombie-tankers-oil> — seen in search results.

<a id="ref-34"></a>34. *hormuz disruption detention storage india ports*. Maersk, 2026. <https://www.maersk.com/news/articles/2026/04/01/hormuz-disruption-detention-storage-india-ports> — seen in search results.

<a id="ref-35"></a>35. *Cargo rollovers rise as Maersk rolls more than 1 in 3 shipments in October*. Supply Chain Dive (Ocean Insights data); also https://gcaptain.com/another-new-normal-as-container-rollover-rates-increase/ and https://www.seatrade-maritime.com/containers/container-cargo-rollovers-at-major-ports-increase-75-in-december, 2020. <https://www.supplychaindive.com/news/rolled-cargo-port-maersk-msc-coronavirus-singapore/589626/> — seen in search results.

<a id="ref-36"></a>36. *Widespread GPS Jamming Hits 1,000-plus Ships in the Middle East*. Windward, 2026. <https://windward.ai/blog/gps-jamming-disrupts-1100-ships-in-the-middle-east-gulf/> — seen in search results.

<a id="ref-37"></a>37. *War zone GNSS interference surges across the Middle East Gulf*. Lloyd's List (4 Mar 2026), 2026. <https://www.lloydslist.com/LL1156512/War-zone-GNSS-interference-surges-across-the-Middle-East-Gulf> — fetched page.

<a id="ref-38"></a>38. *MSC terminates all Arabian Gulf shipments*. Seatrade Maritime News, 2026. <https://www.seatrade-maritime.com/containers/msc-terminates-all-arabian-gulf-shipments> — seen in search results.

<a id="ref-39"></a>39. Edoardo Debenedetti, Ilia Shumailov, Tianqi Fan, Jamie Hayes, Nicholas Carlini, Daniel Fabian, Christoph Kern, Chongyang Shi, Florian Tramèr. *CaMeL: Defeating Prompt Injections by Design (code for paper 'Defeating Prompt Injections by Design', arXiv 2503.18813)*. Google / Google DeepMind / ETH Zurich (arXiv), 2025. <https://github.com/google-research/camel-prompt-injection> — seen in search results.

<a id="ref-40"></a>40. Manuel Costa, Boris Köpf, Aashish Kolluri, Andrew Paverd, Mark Russinovich, Ahmed Salem, Shruti Tople, Lukas Wutschitz, Santiago Zanella-Béguelin. *Securing AI Agents with Information-Flow Control*. Microsoft; arXiv 2505.23643, 2025. <https://github.com/microsoft/fides> — fetched page.

<a id="ref-41"></a>41. *Week 12*. Hapag-Lloyd operational update, 2026. <https://www.hapag-lloyd.com/en/services-information/operational-updates/updates/2026/03/ops-update-middle-east-week12.html> — seen in search results.

<a id="ref-42"></a>42. GEODIS. *Middle East Situation*. GEODIS customer advisory (20 March 2026), 2026. <https://geodis.com/customer-advisory/middle-east-situation> — seen in search results.

<a id="ref-43"></a>43. *Baltimore port crisis: World's largest container ship company, MSC, dumps diverted cargo problem on U.S. companies*. CNBC, 2024. <https://www.cnbc.com/2024/03/28/worlds-biggest-shipping-firm-dumps-port-cargo-problem-on-us-companies.html> — seen in search results.

<a id="ref-44"></a>44. *Chaos is building for shippers as U.S. port strike continues and costs rise*. CNBC, 2024. <https://www.cnbc.com/2024/10/03/ports-strike-chaos-costs-starting-to-rise.html> — seen in search results.

<a id="ref-45"></a>45. *Container premiums: shippers compete for equipment, space as premium rates climb higher*. S&P Global Commodity Insights (Platts), 2021. <https://www.spglobal.com/energy/en/news-research/latest-news/shipping/060421-container-premiums-shippers-compete-for-equipment-space-as-premium-rates-climb-higher> — seen in search results.

<a id="ref-46"></a>46. Husch Blackwell (International Trade Insights blog). *The disappearance of the service contract in ocean shipping and resurgence of ocean tramp practices*. Husch Blackwell, 2021. <https://www.internationaltradeinsights.com/2021/06/the-disappearance-of-the-service-contract-in-ocean-shipping-and-resurgence-of-ocean-tramp-practices/> — seen in search results.

<a id="ref-47"></a>47. Chief ALJ Erin Wirth. *Public Version FEDERAL MARITIME COMMISSION Office of Administrative Law Judges*. FMC Office of Administrative Law Judges, 2026. <https://www2.fmc.gov/readingroom/docs/23-02/(143)%2023-02%20Initial%20Decision%20(public%20version).pdf/> — seen in search results.

<a id="ref-48"></a>48. *OOCL challenges FMC court system after $45m ruling - Splash247*. Splash247, 2026. <https://splash247.com/oocl-challenges-fmc-court-system-after-45m-ruling/> — seen in search results.

<a id="ref-49"></a>49. Holland & Knight. *FMC Potpourri: Notable Rulings, Filed Agreements (September 17, 2024)*. Holland & Knight; also https://www.maritime-executive.com/article/fmc-orders-hamburg-sud-to-pay-10m-for-retaliating-against-shipper, 2024. <https://www.hklaw.com/en/insights/publications/2024/09/fmc-potpourri-notable-rulings-filed-agreements> — seen in search results.

<a id="ref-50"></a>50. *Asia-Europe carriers leave boxes on quays as they eye better-paid cargo - The Loadstar*. The Loadstar, 2020. <https://theloadstar.com/asia-europe-carriers-leave-boxes-on-quays-as-they-eye-better-paid-cargo/> — seen in search results.

<a id="ref-51"></a>51. Hill Dickinson LLP. *'End of Voyage' declarations: a growing trend*. Hill Dickinson (law firm insight), 2026. <https://www.hilldickinson.com/our-view/articles/end-of-voyage-declarations-a-growing-trend/> — seen in search results.

<a id="ref-52"></a>52. *carrier voyage termination force majeure and cargo insurance*. Kennedys Law LLP, 2026. <https://www.kennedyslaw.com/en/thought-leadership/article/2026/carrier-voyage-termination-force-majeure-and-cargo-insurance> — seen in search results.

<a id="ref-53"></a>53. *'End of Voyage' declarations: a growing trend*. Hill Dickinson, 2026. <https://www.hilldickinson.com/our-view/articles/end-of-voyage-declarations-a-growing-trend/> — seen in search results.

<a id="ref-54"></a>54. *definition of unreasonable refusal to deal or negotiate with respect to vessel space accommodations*. Federal Register 89 FR (23 July 2024), 2024. <https://www.federalregister.gov/documents/2024/07/23/2024-16148/definition-of-unreasonable-refusal-to-deal-or-negotiate-with-respect-to-vessel-space-accommodations> — seen in search results.

<a id="ref-55"></a>55. *US Court upholds FMC rule on carrier refusals to deal with shippers*. Container News, 2026. <https://container-news.com/us-court-upholds-fmc-rule-on-carrier-refusals-to-deal-with-shippers> — seen in search results.

<a id="ref-56"></a>56. *An Insurer’s Guide to the Key Changes in the UAE’s New Maritime Law - UAE Federal Decree No. (43) of 2023*. The Shipowners' Club, 2024. <https://www.shipownersclub.com/latest-updates/news/insurers-guide-key-changes-uaes-new-maritime-law-uae-federal-decree-no-43-2023/> — seen in search results.

<a id="ref-57"></a>57. Lingye Zhang, Dong Yang, Xiwen Bai, Kee-hung Lai. *How liner shipping heals schedule disruption: A data-driven framework to uncover the strategic behavior of port-skipping*. Transportation Research Part E 176, 103229, 2023. <https://ideas.repec.org/a/eee/transe/v176y2023ics136655452300217x.html> — seen in search results.

<a id="ref-58"></a>58. Carlos Pais-Montes, Jean-Claude Thill, David Guerrero. *[Title not captured in search results] AIS-based measurement of port call cancellations, Europe–Far East, before and during COVID-19*. Maritime Economics & Logistics 26:490–508 (DOI 10.1057/s41278-023-00264-y), 2024. <https://ideas.repec.org/a/pal/marecl/v26y2024i3d10.1057_s41278-023-00264-y.html> — seen in search results.

<a id="ref-59"></a>59. Digital Container Shipping Association (DCSA). *Operational Vessel Schedules standard*. DCSA; also Track & Trace https://dcsa.org/standards/track-and-trace and the self-certification checklist https://dcsa.org/wp-content/uploads/2020/10/20210621_DCSA_SCC-for-TT-1.2.pdf, 2024. <https://dcsa.org/standards/operational-vessel-schedules> — seen in search results.

<a id="ref-60"></a>60. *Operational Vessel Schedules*. DCSA, 2021. <https://dcsa.org/standards/operational-vessel-schedules/documentation-operational-vessel-schedules> — seen in search results.

<a id="ref-61"></a>61. Yang, D.; Wu, L.X.; Wang, S.A.. *Can we trust the AIS destination port information for bulk ships?–Implications for shipping policy and practice*. Transportation Research Part E 149, 102308 (DOI 10.1016/j.tre.2021.102308), 2021. <https://research.polyu.edu.hk/en/publications/can-we-trust-the-ais-destination-port-information-for-bulk-shipsi/> — seen in search results.

<a id="ref-62"></a>62. *367,000-Ship Study Finds Global GPS Spoofing, Red Sea Activity Before Grounding*. Hackread, 2026. <https://hackread.com/ship-study-global-gps-spoofing-red-sea-activity/> — seen in search results.

<a id="ref-63"></a>63. *More Than 1,100 Ships Hit by Widespread GPS Disruption After Iran Strikes*. OCCRP (5 Mar 2026), 2026. <https://www.occrp.org/en/news/more-than-1100-ships-hit-by-widespread-gps-disruption-after-iran-strikes> — seen in search results.

<a id="ref-64"></a>64. TIMEWELL (column). *Hormuz Strait transit data analysis (August 2026: 393 of 642 logged transits were jamming artifacts)*. timewell.jp, 2026. <https://timewell.jp/en/columns/hormuz-strait-transit-data-analysis> — seen in search results.

<a id="ref-65"></a>65. The Maritime Executive. *Dark Transits of Hormuz and Spoofing Increase as Ships Avoid Omani Route*. The Maritime Executive, 2026. <https://maritime-executive.com/article/dark-transits-of-hormuz-and-spoofing-increase-as-ships-avoid-omani-route> — seen in search results.

<a id="ref-66"></a>66. *Update 015 JMIC Advisory Note 15 MAR 2026 FINAL*. JMIC (hosted by MSCIO), 2026. <https://mscio.eu/media/documents/Update_015_-_JMIC_Advisory_Note_15_MAR_2026_FINAL.pdf> — seen in search results.

<a id="ref-67"></a>67. *Update 073 to JMIC Advisory Note (19 July)*. JMIC (hosted by UKMTO), 2026. <https://www.ukmto.org/-/media/ukmto/products/update-073-jmic-advisory-note-19-july.pdf?rev=51a8aaa4bb06463fbce249d39abccb76> — seen in search results.

<a id="ref-68"></a>68. CCJ (reporting Verisk CargoNet). *CargoNet: Cargo theft losses surged 60% in 2025*. CCJ, 2026. <https://www.ccjdigital.com/regulations/article/15815405/cargo-theft-activity-flat-losses-surged-in-2025-cargonet> — seen in search results.

<a id="ref-69"></a>69. Verisk CargoNet. *Cargo Theft Losses More Than Double to $304 Million in Q2 Despite a Drop in Thefts, Driven by High-Value Metals and Technology Heists*. Verisk newsroom, 2026. <https://www.verisk.com/company/newsroom/cargo-theft-losses-more-than-double-to-$304-million-in-q2-despite-a-drop-in-thefts-driven-by-high-value-metals-and-technology-heists/> — seen in search results.

<a id="ref-70"></a>70. Highway. *Q2 2026 Freight Fraud Index: Half of All Incidents Now Tied to Communication Based Attacks*. Highway (press release via Yahoo Finance), 2026. <https://finance.yahoo.com/technology/articles/q2-2026-freight-fraud-index-135200680.html> — seen in search results.

<a id="ref-71"></a>71. FMCSA, US DOT. *Federal Register :: Availability of Motus, FMCSA's New Registration System*. Federal Register, 2026. <https://www.federalregister.gov/documents/2026/04/29/2026-08334/availability-of-motus-fmcsas-new-registration-system> — seen in search results.

<a id="ref-72"></a>72. CCJ. *Cybercriminals find new fraud target in FMCSA's Motus system*. CCJ, 2026. <https://www.ccjdigital.com/technology/cybersecurity/article/15836500/cybercriminals-find-new-fraud-target-in-fmcsas-motus-system> — seen in search results.

<a id="ref-73"></a>73. MarineLink. *IMO Approves New Guidelines on Ship Registration*. MarineLink, 2026. <https://www.marinelink.com/news/imo-approves-new-guidelines-ship-538223> — seen in search results.

<a id="ref-74"></a>74. Vizion. *Strait of Hormuz disruption sends container booking activity plummeting across Arabian Gulf ports*. Vizion blog (related: https://www.vizionapi.com/blog/gulf-container-booking-recovery-hormuz), 2026. <https://www.vizionapi.com/blog/strait-of-hormuz-disruption-sends-container-booking-activity-plummeting-across-arabian-gulf-ports> — seen in search results.

<a id="ref-75"></a>75. *400 global schedule reliability drops to 62 6 in june 2026*. Sea-Intelligence, 2026. <https://sea-intelligence.com/press-room/400-global-schedule-reliability-drops-to-62-6-in-june-2026> — seen in search results.

<a id="ref-76"></a>76. BCG. *Why AI Isn't Delivering ROI in Logistics*. BCG, 2026. <https://www.bcg.com/publications/2026/why-ai-isnt-delivering-roi-logistics> — seen in search results.

<a id="ref-77"></a>77. OWASP GenAI Security Project. *GenAI-LLM-Top10 2026 final (repository folder)*. OWASP, 2026. <https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/main/2026/final> — fetched page.

<a id="ref-78"></a>78. OWASP GenAI Security Project. *GenAI-Security-Advisor corpus MANIFEST (entry: OWASP Top 10 for Agentic Applications 2026 v1.0)*. OWASP, 2025. <https://github.com/GenAI-Security-Project/GenAI-Security-Advisor/blob/main/corpus/MANIFEST.yaml> — fetched page.

<a id="ref-79"></a>79. Jón Winkel, Tom Willems, Cillian O'Driscoll, Ignacio Fernandez-Hernandez. *SeaSpoofFinder – Potential GNSS Spoofing Event Detection Using AIS*. arXiv, 2026. <https://arxiv.org/abs/2602.16257> — seen in search results.

<a id="ref-80"></a>80. Sanghyeon Park, DeukJae Cho, Pyo-Woong Son (per search summary). *AIS-Based Maritime GNSS RFI Monitoring With Multi-Vessel Coherence and Communication-Integrity Artifact Mitigation (title as shown in one search result; another result gives 'Wide-Area GNSS Spoofing and Jamming Detection Using AIS-Derived Spatiotemporal Integrity Monitoring')*. arXiv, 2026. <https://arxiv.org/abs/2603.11055> — seen in search results.

<a id="ref-81"></a>81. Sanghyeon Park, Halim Lee, Pyo-Woong Son. *Track-Consistency-Based GNSS RFI Monitoring Using Crowdsourced ADS-B Sensor Networks*. arXiv (v1 21 Jun 2026; v2 13 Aug 2026), 2026. <https://arxiv.org/abs/2607.09700> — seen in search results.

<a id="ref-82"></a>82. Argyris Kriezis, Yu-Hsuan Chen, Dennis Akos, Sherman Lo, Todd Walter. *GNSS Jamming and Spoofing Monitoring Using Low-Cost COTS Receivers*. arXiv (intended for ION NAVIGATION), 2025. <https://arxiv.org/abs/2509.13600v1> — seen in search results.

<a id="ref-83"></a>83. Tao Zhang et al.. *Detection of AIS Closing Behavior and MMSI Spoofing Behavior of Ships Based on Spatiotemporal Data*. Remote Sensing (MDPI), CC BY 4.0, 2020. <https://doi.org/10.3390/rs12040702> — seen in search results.

<a id="ref-84"></a>84. *An approach to detect identity spoofing in AIS messages*. Expert Systems with Applications (Elsevier, per PII), c.2024 (inferred from PII; not confirmed). <https://www.sciencedirect.com/science/article/abs/pii/S0957417424011230> — seen in search results.

<a id="ref-85"></a>85. Gary C. Kessler. *AIS Spoofing: A Tutorial for Researchers*. MarCaS 2024 (slides), 2024. <https://www.garykessler.net/gck/202410_MarCaS_AIS_Spoofing.pdf> — seen in search results.

<a id="ref-86"></a>86. *Study: Baltic GPS Disruption Comes From a Tactically-Controlled Network*. The Maritime Executive (22 Dec 2025), 2025. <https://maritime-executive.com/article/study-baltic-gps-disruption-comes-from-a-tactically-controlled-network> — seen in search results.

<a id="ref-87"></a>87. *MSC Antonia Grounding in the Red Sea Attributed to Suspected GNSS Spoofing*. Inside GNSS, 2025. <https://insidegnss.com/msc-antonia-grounding-in-the-red-sea-attributed-to-suspected-gps-spoofing/> — seen in search results.

<a id="ref-88"></a>88. Youngseok Hwang et al. (Seoul National University; KRISO). *Redefining Maritime Anomaly Detection via Equation-Grounded Synthetic Anomalies*. arXiv; KDD 2026 (AI4Sciences track, per README), 2026. <https://arxiv.org/pdf/2606.29721> — fetched page.

<a id="ref-89"></a>89. Ines Agrebi (University of Victoria). *Synthetic GPS Dataset for AI-Based Spoofing Detection on Maritime Autonomous Surface Ships*. IEEE DataPort, 2025. <https://ieee-dataport.org/documents/synthetic-gps-dataset-ai-based-spoofing-detection-maritime-autonomous-surface-ships> — seen in search results.

<a id="ref-90"></a>90. Duong Nguyen, Rodolphe Vadaine, Guillaume Hajduch, René Garello, Ronan Fablet. *GeoTrackNet-A Maritime Anomaly Detector using Probabilistic Neural Network Representation of AIS Tracks and A Contrario Detection*. IEEE Transactions on Intelligent Transportation Systems (DOI 10.1109/TITS.2021.3055614), 2021. <https://arxiv.org/pdf/1912.00682> — seen in search results.

<a id="ref-91"></a>91. Duong Nguyen, Ronan Fablet. *TrAISformer -- A Transformer Network with Sparse Augmented Data Representation and Cross Entropy Loss for AIS-based Vessel Trajectory Prediction*. IEEE Access (Jan 2024 per DOAJ record), 2024 (IEEE Access; arXiv 2021). <https://arxiv.org/abs/2109.03958> — seen in search results.

<a id="ref-92"></a>92. *DiffuTraj: A Stochastic Vessel Trajectory Prediction Approach via Guided Diffusion Process*. arXiv (12 Oct 2024), 2024. <https://arxiv.org/pdf/2410.09550> — seen in search results.

<a id="ref-93"></a>93. *AISFlow: Boundary-Informed Flow Matching for Long-Term AIS Trajectory Imputation*. ICML 2026, 2026. <https://icml.cc/virtual/2026/73576> — seen in search results.

<a id="ref-94"></a>94. University of Minnesota group incl. Shashi Shekhar (six authors). *Towards Physics-informed Diffusion for Anomaly Detection in Trajectories*. arXiv cs.LG, 2025. <https://arxiv.org/abs/2506.06999v2> — fetched page.

<a id="ref-95"></a>95. Arun Sharma, Shashi Shekhar. *Physics-Guided Abnormal Trajectory Gap Detection*. arXiv; ACM record lists 'Physics-Based Abnormal Trajectory Gap Detection' (12 Oct 2024), 2024. <https://arxiv.org/abs/2403.06268v1> — seen in search results.

<a id="ref-96"></a>96. Alam, Soares, Rodrigues-Jr, Spadon (per citing papers). *Physics-Informed Vessel Trajectory Prediction via Finite Difference Kinematic Losses*. Research Square (posted 19 Dec 2025), 2025. <https://www.researchsquare.com/article/rs-8291452/v1> — seen in search results.

<a id="ref-97"></a>97. Hwang, Bae, Lee, Seo, Kim, Lee, Park. *snudial/open-maritime-anomaly-detection (omad)*. GitHub, 2026. <https://github.com/snudial/open-maritime-anomaly-detection> — fetched page.

<a id="ref-98"></a>98. Kim, Park, Shin, Park, Han (Korea University; SeaVantage). *WAY: Estimation of Vessel Destination in Worldwide AIS Trajectory*. IEEE Transactions on Aerospace and Electronic Systems (DOI 10.1109/TAES.2023.3269729 per arXiv page), 2023 (IEEE TAES; arXiv posting Dec 2025). <https://arxiv.org/pdf/2512.13190> — seen in search results.

<a id="ref-99"></a>99. Yanzhao Su, Fang He, Yineng Wang. *A Retrieval-Enhanced Transformer for Multi-Step Port-of-Call Sequence Prediction in Global Liner Shipping*. arXiv, 2026. <https://arxiv.org/pdf/2605.15937> — seen in search results.

<a id="ref-100"></a>100. *Beyond the Next Port: A Multi-Task Transformer for Forecasting Future Voyage Segment Durations*. arXiv, 2026. <https://arxiv.org/abs/2601.08013v1> — seen in search results.

<a id="ref-101"></a>101. Steidel, Lamm, Feuerstack, Hahn (as shown in search extract). *Correcting the Destination Information in Automatic Identification System Messages*. OFFIS publication record, unknown. <https://www.offis.de/offis/publikation/correcting-the-destination-information-in-automatic-identification-system-messages.html> — seen in search results.

<a id="ref-102"></a>102. Iphar et al.. *Port call extraction from vessel location data for characterising harbour traffic*. Ocean Engineering, 2024. <https://isidore.science/document/10670/1.caaae0e34fc26425321ecb18676d9f995f7b25ff> — seen in search results.

<a id="ref-103"></a>103. Hadjipieris et al.. *Unsupervised Port Berth Localization from Automatic Identification System Data*. Sensors (MDPI); arXiv 2505.12046, 2025. <https://doi.org/10.3390/s25226845> — seen in search results.

<a id="ref-104"></a>104. *Data Source, Methods and Quality Port Visits Using Real-Time Shipping Data*. Central Statistics Office (Ireland), n.d.. <https://www.cso.ie/en/releasesandpublications/fp/fp-pvrts/portvisitsusingreal-timeshippingdata/datasourcemethodsandquality/> — seen in search results.

<a id="ref-105"></a>105. Fernando S. Paolo, David Kroodsma, et al.. *Satellite mapping reveals extensive industrial activity at sea*. Nature 625, 85-91 (DOI 10.1038/s41586-023-06825-8), 2024. <https://pmc.ncbi.nlm.nih.gov/articles/PMC10764273> — seen in search results.

<a id="ref-106"></a>106. Heather Welch et al. (UCSC, Global Fishing Watch, NOAA Fisheries). *Hot spots of unseen fishing vessels*. Science Advances 8(44): eabq2109, 2022. <https://repository.library.noaa.gov/view/noaa/63172> — seen in search results.

<a id="ref-107"></a>107. Pierre Bernabé, Arnaud Gotlieb, Bruno Legeard, Dusica Marijan, Frank Olaf Sem-Jacobsen, Helge Spieker. *Detecting Intentional AIS Shutdown in Open Sea Maritime Surveillance Using Self-Supervised Deep Learning*. IEEE Transactions on Intelligent Transportation Systems (arXiv 2310.15586), 2023. <https://ieeexplore.ieee.org/document/10287194> — seen in search results.

<a id="ref-108"></a>108. *xView3-SAR: Detecting Dark Fishing Activity Using Synthetic Aperture Radar Imagery*. NeurIPS 2022 Datasets and Benchmarks, 2022. <https://proceedings.neurips.cc/paper_files/paper/2022/hash/f4d4a021f9051a6c18183b059117e8b5-Abstract.html> — seen in search results.

<a id="ref-109"></a>109. Sean Bin Yang, Ying Sun, Yunyao Cheng, Yan Lin, Kristian Torp, Jilin Hu. *Spatio-Temporal Trajectory Foundation Model - Recent Advances and Future Directions*. arXiv, 2025. <https://arxiv.org/html/2511.20729v1> — seen in search results.

<a id="ref-110"></a>110. *Representation Learning for Maritime Vessel Behaviour: A Three-Stage Pipeline for Robust Trajectory Embeddings*. Journal of Marine Science and Engineering (MDPI), 2026. <https://doi.org/10.3390/jmse14050507> — seen in search results.

<a id="ref-111"></a>111. Chen et al.. *TG‐GPT: A Generative Pre‐Trained Transformer With Gated Recurrent Units for AIS‐Based Ship Trajectory Prediction*. The Journal of Engineering (IET/Wiley), 2026. <https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/tje2.70151> — seen in search results.

<a id="ref-112"></a>112. Hanbat National University, KAIST and KRISO authors. *AIS-LLM: A Unified Framework for Maritime Trajectory Prediction, Anomaly Detection, and Collision Risk Assessment with Explainable Forecasting*. arXiv, 2025. <https://arxiv.org/pdf/2508.07668> — seen in search results.

<a id="ref-113"></a>113. Brouer, Dirksen, Pisinger, Plum, Vaaben. *The Vessel Schedule Recovery Problem (VSRP) – A MIP model for handling disruptions in liner shipping*. European Journal of Operational Research 224(2):362–374, 2013. <https://iaorifors.com/paper/77372> — seen in search results.

<a id="ref-114"></a>114. Yadong Wang, Yuyun Gu, Tingsong Wang, Jun Zhang. *A risk-averse approach for joint contract selection and slot allocation in liner container shipping*. Transportation Research Part E 164, 2022. <https://www.sciencedirect.com/science/article/abs/pii/S1366554522001727> — seen in search results.

<a id="ref-115"></a>115. Yuyun Gu, Yadong Wang, Tingsong Wang. *An approximate dynamic programming approach to dynamic slot allocation of spot containers with random arrivals, cancellations, and no-shows*. Transportation Research Part E 193, 2025. <https://www.sciencedirect.com/science/article/abs/pii/S1366554524004289> — seen in search results.

<a id="ref-116"></a>116. Jacob Feldman, Yukai Huang, Panos Kouvelis. *Prophet Inequalities for a New Class of Overbooking Problems in Container Shipping*. Operations Research (articles in advance), 2026. <https://pubsonline.informs.org/doi/10.1287/opre.2024.0842> — seen in search results.

<a id="ref-117"></a>117. Hui Zhao, Qiang Meng, Yadong Wang. *probability estimation model for the cancellation of container sl*. Transportation Research Part C 119, 102731, 2020. <https://research.polyu.edu.hk/en/publications/probability-estimation-model-for-the-cancellation-of-container-sl/> — seen in search results.

<a id="ref-118"></a>118. Hui Zhao, Qiang Meng, Yadong Wang. *exploratory data analysis for the cancellation of slot booking in*. Transportation Research Part C 106:243–263, 2019. <https://research.polyu.edu.hk/en/publications/exploratory-data-analysis-for-the-cancellation-of-slot-booking-in/> — seen in search results.

<a id="ref-119"></a>119. Bert Vernimmen, Wout Dullaert, Steve Engelen. *schedule unreliability in liner shipping origins and consequences*. Maritime Economics & Logistics 9(3):193–213, 2007. <https://research.vu.nl/en/publications/schedule-unreliability-in-liner-shipping-origins-and-consequences/> — seen in search results.

<a id="ref-120"></a>120. Zhong Chu, Ran Yan, Shuaian Wang. *Evaluation and prediction of punctuality of vessel arrival at port: a case study of Hong Kong*. Maritime Policy & Management 51(6):1096–1124, 2024. <https://nanyangtechnologicaluniv.demo.elsevierpure.com/en/publications/evaluation-and-prediction-of-punctuality-of-vessel-arrival-at-por> — seen in search results.

<a id="ref-121"></a>121. Viellechner, A.; Spinler, S.. *Novel Data Analytics Meets Conventional Container Shipping: Predicting Delays by Comparing Various Machine Learning Algorithms*. HICSS 2020 (DOI 10.24251/HICSS.2020.158), 2020. <https://scholarspace.manoa.hawaii.edu/items/85219e6c-7ceb-4529-8f10-16b91e60a8eb/full> — seen in search results.

<a id="ref-122"></a>122. *Commercial Schedules 1.0*. DCSA, 2024. <https://dcsa.org/standards/commercial-schedules/documentation-commerical-schedule-1> — seen in search results.

<a id="ref-123"></a>123. *DCSA releases final versions of Booking 2.0 and Bill of Lading 3.0 standards*. DCSA, 2025. <https://dcsa.org/newsroom/final-versions-of-booking-bill-of-lading-standards-released> — seen in search results.

<a id="ref-124"></a>124. *dcsa releases track trace interface standard version 2 2*. DCSA, 2021. <https://dcsa.org/newsroom/dcsa-releases-track-trace-interface-standard-version-2-2> — seen in search results.

<a id="ref-125"></a>125. *DCSA Reference Documentation / Standards / Standard Releases / Port Call / Port Call v2.0.0*. DCSA, 2025. <https://reference.dcsa.org/content/standards/releases/port-call/v2-0-0/port-call-v2-0-0-purpose-and-scope> — seen in search results.

<a id="ref-126"></a>126. *github.com/dcsaorg (GitHub organization page)*. GitHub, 2026. <https://github.com/dcsaorg> — fetched page.

<a id="ref-127"></a>127. *fmc publishes final rule on unreasonable refusal to deal*. Federal Maritime Commission, 2024. <https://www.fmc.gov/articles/fmc-publishes-final-rule-on-unreasonable-refusal-to-deal/> — seen in search results.

<a id="ref-128"></a>128. *Final Recommendations on the MTDS Requirements*. Federal Maritime Commission (Commissioner Bentzel), 2024. <https://www.fmc.gov/wp-content/uploads/2024/12/Final-Recommendations-on-the-MTDS-Requirements.pdf> — seen in search results.

<a id="ref-129"></a>129. Shenyang Huang et al. (incl. Jure Leskovec, Michael Bronstein). *Temporal Graph Benchmark for Machine Learning on Temporal Graphs*. NeurIPS 2023 Datasets and Benchmarks, 2023. <https://neurips.cc/virtual/2023/poster/73456> — fetched page.

<a id="ref-130"></a>130. Julia Gastinger et al.. *TGB 2.0: A Benchmark for Learning on Temporal Knowledge Graphs and Heterogeneous Graphs*. NeurIPS 2024 Datasets and Benchmarks, 2024. <https://proceedings.neurips.cc/paper_files/paper/2024/hash/fda026cf2423a01fcbcf1e1e43ee9a50-Abstract.html> — fetched page.

<a id="ref-131"></a>131. Jianheng Tang, Jiajin Li, Ziqi Gao, Jia Li. *Rethinking Graph Neural Networks for Anomaly Detection*. ICML 2022 (PMLR 162), 2022. <https://proceedings.mlr.press/v162/tang22b.html> — seen in search results.

<a id="ref-132"></a>132. Yingtong Dou, Zhiwei Liu, Li Sun, Yutong Deng, Hao Peng, Philip S. Yu. *Enhancing Graph Neural Network-based Fraud Detectors against Camouflaged Fraudsters (CARE-GNN repository)*. CIKM 2020, 2020. <https://github.com/YingtongDou/CARE-GNN> — fetched page.

<a id="ref-133"></a>133. Yixin Liu, Shiyuan Li, Yu Zheng, Qingfeng Chen, Chengqi Zhang, Shirui Pan. *ARC: A Generalist Graph Anomaly Detector with In-Context Learning*. NeurIPS 2024, 2024. <https://proceedings.neurips.cc/paper_files/paper/2024/hash/5acb720a361eecb34ee62d356859d246-Abstract.html> — fetched page.

<a id="ref-134"></a>134. Yiqing Lin et al.. *UniGAD: Unifying Multi-level Graph Anomaly Detection*. NeurIPS 2024, 2024. <https://papers.neurips.cc/paper_files/paper/2024/hash/f57de20ab7bb1540bcac55266ebb5401-Abstract-Conference.html> — seen in search results.

<a id="ref-135"></a>135. Yu et al. (BUAA). *Towards Better Dynamic Graph Learning: New Architecture and Unified Library (DyGLib)*. NeurIPS 2023, 2023. <https://github.com/yule-BUAA/DyGLib> — fetched page.

<a id="ref-136"></a>136. Sundong Kim, Yu-Che Tsai, Karandeep Singh, Yeonsoo Choi, Etim Ibok, Cheng-Te Li, Meeyoung Cha. *DATE: Dual Attentive Tree-aware Embedding for Customs Fraud Detection*. KDD 2020, 2020. <https://koasas.kaist.ac.kr/handle/10203/277526?mode=full> — seen in search results.

<a id="ref-137"></a>137. Karandeep Singh, Yu-Che Tsai et al.. *GraphFC: Customs Fraud Detection with Label Scarcity*. CIKM 2023 (arXiv), 2023. <https://arxiv.org/pdf/2305.11377> — seen in search results.

<a id="ref-138"></a>138. Egressy et al.; Altman et al. (IBM). *Multi-GNN (Provably Powerful Graph Neural Networks for Directed Multigraphs; Realistic Synthetic Financial Transactions for Anti-Money Laundering Models)*. AAAI 2024; NeurIPS 2023, 2023-2024. <https://github.com/IBM/Multi-GNN> — fetched page.

<a id="ref-139"></a>139. Youssef Elmougy, Ling Liu. *Demystifying Fraudulent Transactions and Illicit Nodes in the Bitcoin Network for Financial Forensics (Elliptic++)*. KDD 2023, 2023. <https://github.com/git-disl/EllipticPlusPlus> — fetched page.

<a id="ref-140"></a>140. MIT-IBM Watson AI Lab / Elliptic (per repo org). *The Shape of Money Laundering: Subgraph Representation Learning on the Blockchain with the Elliptic2 Dataset*. arXiv preprint 2404.19109, 2024. <https://github.com/MITIBMxGraph/Elliptic2> — fetched page.

<a id="ref-141"></a>141. Xuanwen Huang, Yang Yang et al.. *DGraph: A Large-Scale Financial Dataset for Graph Anomaly Detection*. NeurIPS 2022 Datasets and Benchmarks, 2022. <https://proceedings.neurips.cc/paper_files/paper/2022/hash/8f1918f71972789db39ec0d85bb31110-Abstract.html> — seen in search results.

<a id="ref-142"></a>142. safe-graph maintainers. *graph-fraud-detection-papers (safe-graph curated list)*. GitHub, 2026 (maintained). <https://github.com/safe-graph/graph-fraud-detection-papers> — fetched page.

<a id="ref-143"></a>143. qcf-568 (authors not listed in fetched summary). *Towards Robust Tampered Text Detection in Document Image: New Dataset and New Solution (DocTamper)*. CVPR 2023, 2023. <https://github.com/qcf-568/DocTamper> — fetched page.

<a id="ref-144"></a>144. Windward. *False Flags, Fraudulent Registries, and the Dark Fleet*. Windward, 2025-2026. <https://windward.ai/knowledge-base/false-flags-fraudulent-registries-and-the-dark-fleet/> — seen in search results.

<a id="ref-145"></a>145. MALA Lab (survey authors). *Awesome-Deep-Graph-Anomaly-Detection (companion to 'Deep Graph Anomaly Detection: A Survey and New Perspectives', IEEE TKDE 2025)*. GitHub / IEEE TKDE 2025, 2025. <https://github.com/mala-lab/Awesome-Deep-Graph-Anomaly-Detection> — fetched page.

<a id="ref-146"></a>146. Po-Sen Huang, Xiaodong He, Jianfeng Gao, Li Deng, Alex Acero, Larry Heck. *Learning Deep Structured Semantic Models for Web Search using Clickthrough Data*. ACM CIKM 2013 (Microsoft Research page), 2013. <https://www.microsoft.com/en-us/research/publication/learning-deep-structured-semantic-models-for-web-search-using-clickthrough-data/> — fetched page.

<a id="ref-147"></a>147. *Sampling-Bias-Corrected Neural Modeling for Large Corpus Item Recommendations (as cited in torch-rechub youtube_sbc.py)*. ACM RecSys 2019 (per citing sources), 2019. <https://github.com/datawhalechina/torch-rechub/blob/main/torch_rechub/models/matching/youtube_sbc.py> — seen in search results.

<a id="ref-148"></a>148. Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, Wen-tau Yih. *Dense Passage Retrieval for Open-Domain Question Answering (facebookresearch/DPR)*. EMNLP 2020, pp. 6769–6781, DOI 10.18653/v1/2020.emnlp-main.550, 2020. <https://github.com/facebookresearch/DPR> — fetched page.

<a id="ref-149"></a>149. Alec Radford, Jong Wook Kim, et al.. *Learning Transferable Visual Models From Natural Language Supervision (CLIP; OpenCLIP)*. ICML 2021, 2021. <https://github.com/mlfoundations/open_clip> — fetched page.

<a id="ref-150"></a>150. Lee Xiong, Chenyan Xiong, Ye Li, Kwok-Fung Tang, Jialin Liu, Paul Bennett, Junaid Ahmed, Arnold Overwijk. *Approximate Nearest Neighbor Negative Contrastive Learning for Dense Text Retrieval (ANCE)*. ICLR 2021, 2021. <https://www.microsoft.com/en-us/research/publication/approximate-nearest-neighbor-negative-contrastive-learning-for-dense-text-retrieval/> — fetched page.

<a id="ref-151"></a>151. Yingqi Qu et al.; Ruiyang Ren et al.. *RocketQA: An Optimized Training Approach to Dense Passage Retrieval for Open-Domain Question Answering; RocketQAv2: A Joint Training Method for Dense Passage Retrieval and Passage Re-ranking*. NAACL 2021; EMNLP 2021; PAIR in ACL Findings 2021, 2021. <https://github.com/PaddlePaddle/RocketQA> — fetched page.

<a id="ref-152"></a>152. Luyu Gao, Yunyi Zhang, Jiawei Han, Jamie Callan. *Scaling Deep Contrastive Learning Batch Size under Memory Limited Setup (GradCache)*. Proceedings of the 6th Workshop on Representation Learning for NLP, 2021. <https://github.com/luyug/GradCache> — fetched page.

<a id="ref-153"></a>153. *Retrieve & Re-Rank (Sentence-Transformers documentation)*. Hugging Face / Sentence-Transformers, 2026. <https://github.com/huggingface/sentence-transformers/blob/main/examples/sentence_transformer/applications/retrieve_rerank/README.md> — fetched page.

<a id="ref-154"></a>154. Nandan Thakur, Nils Reimers, et al.. *Augmented SBERT: Data Augmentation Method for Improving Bi-Encoders for Pairwise Sentence Scoring Tasks*. Linked as arXiv 2010.08240 via huggingface.co/papers, 2020. <https://github.com/huggingface/sentence-transformers/blob/main/examples/sentence_transformer/training/data_augmentation/README.md> — fetched page.

<a id="ref-155"></a>155. *ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT; ColBERTv2; PLAID*. SIGIR'20; ColBERTv2 NAACL'22; PLAID CIKM'22, 2020. <https://github.com/stanford-futuredata/ColBERT> — fetched page.

<a id="ref-156"></a>156. Xiangyang Li, Bo Chen, Huifeng Guo, et al., Ruiming Tang. *IntTower: the Next Generation of Two-Tower Model for Pre-ranking System*. CIKM 2022 (also DLP-KDD 2022 best paper), 2022. <https://github.com/archersama/IntTower> — fetched page.

<a id="ref-157"></a>157. Jianlv Chen, Shitao Xiao, Peitian Zhang, Kun Luo, Defu Lian, Zheng Liu. *BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation (FlagEmbedding)*. BAAI; technical report arXiv 2402.03216, 2024. <https://github.com/FlagOpen/FlagEmbedding> — fetched page.

<a id="ref-158"></a>158. *Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models*. Qwen team; arXiv 2506.05176, 2025. <https://github.com/QwenLM/Qwen3-Embedding> — fetched page.

<a id="ref-159"></a>159. Muennighoff, Tazi, Magne, Reimers; Enevoldsen et al.. *MTEB: Massive Text Embedding Benchmark; MMTEB: Massive Multilingual Text Embedding Benchmark*. arXiv 2210.07316; arXiv 2502.13595, 2025. <https://github.com/embeddings-benchmark/mteb> — fetched page.

<a id="ref-160"></a>160. *Deep Learning for Blocking in Entity Matching: A Design Space Exploration (DeepBlocker)*. VLDB 2021 (PVLDB vol. 14), 2021. <https://github.com/saravanan-thirumuruganathan/DeepBlocker> — fetched page.

<a id="ref-161"></a>161. Runhui Wang, Yuliang Li, Jin Wang. *Sudowoodo: Contrastive Self-supervised Learning for End-to-End Data Integration*. IEEE ICDE 2023, 2023. <https://github.com/megagonlabs/sudowoodo> — fetched page.

<a id="ref-162"></a>162. *Sparkly: TF/IDF Blocking for Entity Matching*. PVLDB vol. 16 (VLDB 2023), per linked paper, 2023. <https://github.com/anhaidgroup/sparkly> — fetched page.

<a id="ref-163"></a>163. *Deep Entity Matching with Pre-Trained Language Models (Ditto)*. README links arXiv 2004.00584 (venue not shown), 2020. <https://github.com/megagonlabs/ditto> — fetched page.

<a id="ref-164"></a>164. *Unicorn: A Unified Multi-tasking Model for Supporting Matching Tasks in Data Integration*. SIGMOD 2023 (DOI 10.1145/3588938), 2023. <https://github.com/ruc-datalab/Unicorn> — fetched page.

<a id="ref-165"></a>165. Ralph Peeters, Aaron Steiner, Christian Bizer (Univ. Mannheim). *Entity Matching using Large Language Models; Using ChatGPT for Entity Matching (MatchGPT)*. ADBIS 2023 (first paper); arXiv 2310.11244 (second), 2023. <https://github.com/wbsg-uni-mannheim/MatchGPT> — fetched page.

<a id="ref-166"></a>166. Tianshu Wang et al.. *Match, Compare, or Select? An Investigation of Large Language Models for Entity Matching (ComEM)*. COLING 2025 (aclanthology 2025.coling-main.8), 2025. <https://github.com/tshu-w/ComEM> — fetched page.

<a id="ref-167"></a>167. Robin Linacre, Sam Lindsay, Theodore Manassis, Zoe Slade, Tom Hepworth, Ross Kennedy, Andrew Bond. *Splink: Free software for probabilistic record linkage at scale.*. International Journal of Population Data Science 7(3), DOI 10.23889/ijpds.v7i3.1794, 2022. <https://github.com/moj-analytical-services/splink> — fetched page.

<a id="ref-168"></a>168. *Zingg — ML-based entity resolution*. Zingg (AGPL-3.0), 2026. <https://github.com/zinggAI/zingg> — fetched page.

<a id="ref-169"></a>169. Yanchuan Chang, Jianzhong Qi, Yuxuan Liang, Egemen Tanin. *Contrastive Trajectory Similarity Learning with Dual-Feature Attention (TrajCL)*. IEEE ICDE 2023, pp. 2933–2945, 2023. <https://github.com/changyanchuan/TrajCL> — fetched page.

<a id="ref-170"></a>170. Jiawei Jiang, Dayan Pan, Houxing Ren, Xiaohan Jiang, Chao Li, Jingyuan Wang. *Self-supervised Trajectory Representation Learning with Temporal Regularities and Travel Semantics (START)*. IEEE ICDE 2023, 2023. <https://github.com/aptx1231/START> — fetched page.

<a id="ref-171"></a>171. Yuchen Fang, Hao Miao, Yuxuan Liang, et al., Kai Zheng. *Awesome Spatio-Temporal Foundation Models (companion to 'Unraveling Spatio-Temporal Foundation Models via the Pipeline Lens: A Comprehensive Review')*. Survey arXiv 2506.01364; GitHub curated list, 2025. <https://github.com/LMissher/Awesome-Spatio-Temporal-Foundation-Models> — fetched page.

<a id="ref-172"></a>172. *Awesome-Trajectory-Computing (companion to 'Deep Learning for Trajectory Data Management and Mining: A Survey and Beyond')*. Survey arXiv 2403.14151; GitHub curated list, 2024. <https://github.com/yoshall/Awesome-Trajectory-Computing> — fetched page.

<a id="ref-173"></a>173. Runhui Wang, Yuliang Li, Jin Wang. *Sudowoodo: Contrastive Self-supervised Learning for End-to-End Data Integration*. IEEE ICDE 2023, 2023. <https://github.com/megagonlabs/sudowoodo> — fetched page.

<a id="ref-174"></a>174. Linacre et al. (UK Ministry of Justice). *Splink: Free software for probabilistic record linkage at scale*. International Journal of Population Data Science 7(3), 2022. <https://github.com/moj-analytical-services/splink> — fetched page.

<a id="ref-175"></a>175. Long, Simchi-Levi, et al.. *Reliability and Effectiveness of Autonomous AI Agents in Supply Chain Management*. arXiv 2605.17036, 2026. <https://arxiv.org/abs/2605.17036> — seen in search results.

<a id="ref-176"></a>176. SDU / Sherbrooke / CBS. *Agentic AI Autonomy Assessment: A Decision-Support Framework Towards Governed Supply Chain Systems*. arXiv 2607.25405, 2026. <https://arxiv.org/abs/2607.25405> — seen in search results.

<a id="ref-177"></a>177. Guan, Liu, Cao. *SupChain-Bench: Benchmarking Large Language Models for Real-World Supply Chain Management*. Findings of ACL 2026, 2026. <https://aclanthology.org/2026.findings-acl.371/> — seen in search results.

<a id="ref-178"></a>178. Long, Brintrup et al.. *Helicase: Uncertainty-Guided Supply Chain Knowledge Graph Construction with Autonomous Multi-Agent LLMs*. arXiv 2605.26835, 2026. <https://arxiv.org/abs/2605.26835> — seen in search results.

<a id="ref-179"></a>179. Beibin Li, Konstantina Mellou, Bo Zhang, Jeevan Pathuri, Ishai Menache. *Large Language Models for Supply Chain Optimization (OptiGuide)*. Microsoft; arXiv 2307.03875, 2023. <https://github.com/microsoft/OptiGuide> — fetched page.

<a id="ref-180"></a>180. Yinzhu Quan, Zefang Liu. *InvAgent: A Large Language Model based Multi-Agent System for Inventory Management in Supply Chains*. arXiv 2407.11384, 2024. <https://github.com/zefang-liu/InvAgent> — fetched page.

<a id="ref-181"></a>181. *Foundation Models for Logistics: Toward Certifiable, Conversational Planning Interfaces*. arXiv 2507.11352, 2025. <https://arxiv.org/abs/2507.11352> — seen in search results.

<a id="ref-182"></a>182. *AgentNoiseBench: Benchmarking Robustness of Tool-Using LLM Agents Under Noisy Condition*. arXiv 2602.11348, 2026. <https://arxiv.org/abs/2602.11348> — seen in search results.

<a id="ref-183"></a>183. Shunyu Yao, Noah Shinn, Pedram Razavi, Karthik Narasimhan. *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*. arXiv 2406.12045, 2024. <https://github.com/sierra-research/tau-bench> — fetched page.

<a id="ref-184"></a>184. Sierra Research; τ²-Bench by Victor Barres, Honghua Dong, Soham Ray, Xujie Si, Karthik Narasimhan; SABER by Cuadron et al.. *τ²-bench repository (cites τ²-Bench arXiv 2506.07982; τ-Knowledge arXiv 2603.04370; τ-Voice arXiv 2603.13686; SABER: Small Actions, Big Errors — Safeguarding Mutating Steps in LLM Agents, arXiv 2512.07850)*. GitHub, 2026. <https://github.com/sierra-research/tau2-bench> — fetched page.

<a id="ref-185"></a>185. *From Spark to Fire: Modeling and Mitigating Error Cascades in LLM-Based Multi-Agent Collaboration*. arXiv 2603.04474, 2026. <https://arxiv.org/abs/2603.04474> — seen in search results.

<a id="ref-186"></a>186. *Hallucination Cascade: Analyzing Error Propagation in Multi-Agent LLM Systems*. arXiv 2606.07937, 2026. <https://arxiv.org/abs/2606.07937> — seen in search results.

<a id="ref-187"></a>187. Mert Cemri, Melissa Z. Pan, Shuyi Yang, Lakshya A. Agrawal, Bhavya Chopra, Rishabh Tiwari, Kurt Keutzer, Aditya Parameswaran, Dan Klein, Kannan Ramchandran, et al.. *Why Do Multi-Agent LLM Systems Fail? (MAST)*. arXiv 2503.13657, 2025. <https://github.com/multi-agent-systems-failure-taxonomy/MAST> — fetched page.

<a id="ref-188"></a>188. Shilong Wang, Guibin Zhang, Miao Yu, Guancheng Wan, Fanci Meng, Chongye Guo, Kun Wang, Yang Wang. *G-Safeguard: A Topology-Guided Security Lens and Treatment on LLM-based Multi-agent Systems*. ACL 2025 Main (arXiv 2502.11127), 2025. <https://github.com/wslong20/G-safeguard> — fetched page.

<a id="ref-189"></a>189. Luca Beurer-Kellner, Beat Buesser, Ana-Maria Creţu, Edoardo Debenedetti, Daniel Dobos, Daniel Fabian, Marc Fischer, David Froelicher, Kathrin Grosse, Daniel Naeff, Ezinwanne Ozoani, Andrew Paverd, Florian Tramèr, Václav Volhejn. *Design Patterns for Securing LLM Agents against Prompt Injections*. arXiv 2506.08837, 2025. <https://github.com/ReversecLabs/design-patterns-for-securing-llm-agents-code-samples> — fetched page.

<a id="ref-190"></a>190. Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr. *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents*. NeurIPS 2024 Datasets and Benchmarks Track, 2024. <https://github.com/ethz-spylab/agentdojo> — fetched page.

<a id="ref-191"></a>191. Hanrong Zhang, Jingyuan Huang, Kai Mei, Yifei Yao, Zhenting Wang, Chenlu Zhan, Hongwei Wang, Yongfeng Zhang. *Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents*. ICLR 2025 (arXiv 2410.02644), 2025. <https://github.com/agiresearch/ASB> — fetched page.

<a id="ref-192"></a>192. *InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents*. arXiv 2403.02691 (venue not shown on the page), 2024. <https://github.com/uiuc-kang-lab/InjecAgent> — fetched page.

<a id="ref-193"></a>193. Sizhe Chen, Julien Piet, Chawin Sitawarin, David Wagner. *StruQ: Defending Against Prompt Injection with Structured Queries*. USENIX Security 2025 (arXiv 2402.06363), 2025. <https://github.com/Sizhe-Chen/StruQ> — fetched page.

<a id="ref-194"></a>194. Sizhe Chen, Arman Zharmagambetov, David Wagner, Chuan Guo. *Meta SecAlign: A Secure Foundation LLM Against Prompt Injection Attacks*. arXiv 2507.02735, 2025. <https://github.com/facebookresearch/Meta_SecAlign> — fetched page.

<a id="ref-195"></a>195. Sahar Abdelnabi, Aideen Fay, Giovanni Cherubin, Ahmed Salem, Mario Fritz, Andrew Paverd. *Get my drift? Catching LLM Task Drift with Activation Deltas*. SaTML 2025 (arXiv 2406.00799), 2025. <https://github.com/microsoft/TaskTracker> — fetched page.

<a id="ref-196"></a>196. Kaijie Zhu, Xianjun Yang, Jindong Wang, Wenbo Guo, William Yang Wang. *MELON: Provable Defense Against Indirect Prompt Injection Attacks in AI Agents*. ICML 2025 (arXiv 2502.05174), 2025. <https://github.com/kaijiezhu11/MELON> — fetched page.

<a id="ref-197"></a>197. Jesus Salas. *Correct Is Not Governed: Provenance Integrity in Agentic Workflows*. arXiv 2608.12761, 2026. <https://arxiv.org/abs/2608.12761> — seen in search results.

<a id="ref-198"></a>198. *Silence Is Endorsement: Verification-Status Laundering in LLM Agent Pipelines*. arXiv 2609.20211, 2026. <https://arxiv.org/abs/2609.20211> — seen in search results.

<a id="ref-199"></a>199. Wang et al.. *From Agent Traces to Trust: A Survey of Evidence Tracing and Execution Provenance in LLM Agents*. arXiv 2606.04990, 2026. <https://arxiv.org/abs/2606.04990> — seen in search results.

<a id="ref-200"></a>200. OWASP GenAI Security Project. *LLM03_ExcessiveAgency.md (OWASP GenAI LLM Top 10 2026)*. OWASP, 2026. <https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM03_ExcessiveAgency.md> — fetched page.

<a id="ref-201"></a>201. OWASP GenAI Security Project. *Agent Control Standard (ACS)*. OWASP, 2026. <https://github.com/GenAI-Security-Project/agent-control-standard> — fetched page.

<a id="ref-202"></a>202. Model Context Protocol project. *Model Context Protocol specification 2026-07-28: server/tools.mdx*. modelcontextprotocol (GitHub), 2026. <https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx> — fetched page.

<a id="ref-203"></a>203. *MCP specification 2026-07-28 changelog.mdx*. GitHub, 2026. <https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx> — fetched page.

<a id="ref-204"></a>204. *MCP GOVERNANCE.md*. GitHub, 2025-2026. <https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/GOVERNANCE.md> — fetched page.

<a id="ref-205"></a>205. *a2aproject/A2A*. GitHub / Linux Foundation, 2025-2026. <https://github.com/a2aproject/A2A> — fetched page.

<a id="ref-206"></a>206. Anastasios N. Angelopoulos, Stephen Bates, Adam Fisch, Lihua Lei, Tal Schuster. *Conformal Risk Control*. arXiv 2208.02814 (the repo cites the preprint), 2022. <https://github.com/aangelopoulos/conformal-risk> — fetched page.

<a id="ref-207"></a>207. Victor Quach, Adam Fisch, Tal Schuster, Adam Yala, Jae Ho Sohn, Tommi S. Jaakkola, Regina Barzilay. *Conformal Language Modeling*. arXiv 2306.10193, 2023. <https://github.com/Varal7/conformal-language-modeling> — fetched page.

<a id="ref-208"></a>208. Christopher Mohri, Tatsunori Hashimoto. *Language Models with Conformal Factuality Guarantees*. Not shown on the page, 2024. <https://github.com/tatsu-lab/conformal-factual-lm> — fetched page.

<a id="ref-209"></a>209. John J. Cherian, Isaac Gibbs, Emmanuel J. Candès. *Large language model validity via enhanced conformal prediction methods*. arXiv (the ID is a placeholder on the page), 2024. <https://github.com/jjcherian/conformal-safety> — fetched page.

<a id="ref-210"></a>210. Not shown on the fetched page. *Conformal Alignment (repository)*. GitHub, 2024. <https://github.com/yugjerry/conformal-alignment> — fetched page.

<a id="ref-211"></a>211. Kaiqu Liang, Zixu Zhang, Jaime Fernández Fisac. *Introspective Planning: Aligning Robots' Uncertainty with Inherent Task Ambiguity*. NeurIPS 2024 (arXiv 2402.06529), 2024. <https://github.com/kevinliang888/IntroPlan> — fetched page.

<a id="ref-212"></a>212. Polina Kirichenko, Mark Ibrahim, Kamalika Chaudhuri, Samuel J. Bell. *AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions*. arXiv 2506.09038, 2025. <https://github.com/facebookresearch/AbstentionBench> — fetched page.

<a id="ref-213"></a>213. Hussein Mozannar, David Sontag. *Consistent Estimators for Learning to Defer to an Expert*. ICML 2020 (arXiv 2006.01862), 2020. <https://github.com/clinicalml/learn-to-defer> — fetched page.

<a id="ref-214"></a>214. Hussein Mozannar, Hunter Lang, Dennis Wei, Prasanna Sattigeri, Subhro Das, David Sontag. *Who Should Predict? Exact Algorithms For Learning to Defer to Humans*. AISTATS 2023 (arXiv 2301.06197), 2023. <https://github.com/clinicalml/human_ai_deferral> — fetched page.

<a id="ref-215"></a>215. Zhiyuan Hu, Chumin Liu, Xidong Feng, Yilun Zhao, See-Kiong Ng, Anh Tuan Luu, Junxian He, Pang Wei Koh, Bryan Hooi. *Uncertainty of Thoughts: Uncertainty-Aware Planning Enhances Information Seeking in Large Language Models*. NeurIPS 2024 (arXiv 2402.03271), 2024. <https://github.com/zhiyuanhubj/UoT> — fetched page.

<a id="ref-216"></a>216. scikit-learn-contrib. *MAPIE*. GitHub (BSD-3-Clause), 2025. <https://github.com/scikit-learn-contrib/MAPIE> — fetched page.

<a id="ref-217"></a>217. Hongxin Wei's group (SUSTech). *TorchCP: A Python Library for Conformal Prediction*. JMLR vol. 26 (2025); technical report arXiv 2402.12683, 2025. <https://github.com/ml-stat-Sustech/TorchCP> — fetched page.

<a id="ref-218"></a>218. IINemo and contributors. *LM-Polygraph*. TACL 2025 ('Benchmarking Uncertainty Quantification Methods for Large Language Models with LM-Polygraph'); EMNLP 2023 demo; ACL 2025 tutorial, 2025. <https://github.com/IINemo/lm-polygraph> — fetched page.

<a id="ref-219"></a>219. *Enhancing Maritime Safety: Estimating Collision Probabilities with Trajectory Prediction Boundaries Using Deep Learning Models*. PMC (journal not captured), n.d. (likely 2025; not confirmed). <https://pmc.ncbi.nlm.nih.gov/articles/PMC11902398/> — seen in search results.

<a id="ref-220"></a>220. Jianheng Tang, Fengrui Hua, Ziqi Gao, Peilin Zhao, Jia Li. *GADBench: Revisiting and Benchmarking Supervised Graph Anomaly Detection*. NeurIPS 2023 Datasets and Benchmarks Track, 2023. <https://github.com/squareRoot3/GADBench> — fetched page.

<a id="ref-221"></a>221. Shenyang Huang et al.. *TGB: Temporal Graph Benchmark (repo); papers 'Temporal Graph Benchmark for Machine Learning on Temporal Graphs' and 'TGB 2.0: A Benchmark for Learning on Temporal Knowledge Graphs and Heterogeneous Graphs'*. NeurIPS Datasets and Benchmarks Track, 2023-2024. <https://github.com/shenyangHuang/TGB> — fetched page.

<a id="ref-222"></a>222. Le Yu et al. (BUAA). *Towards Better Dynamic Graph Learning: New Architecture and Unified Library (DyGLib)*. NeurIPS 2023, 2023. <https://github.com/yule-BUAA/DyGLib> — fetched page.

<a id="ref-223"></a>223. Qinghua Liu, John Paparrizos. *The Elephant in the Room: Towards A Reliable Time-Series Anomaly Detection Benchmark (TSB-AD)*. NeurIPS 2024 Datasets and Benchmarks Track, 2024. <https://github.com/thedatumorg/TSB-AD> — fetched page.

<a id="ref-224"></a>224. PyGOD team. *PyGOD: A Python Library for Graph Outlier Detection; BOND: Benchmarking Unsupervised Outlier Node Detection on Static Attributed Graphs*. JMLR 2024; NeurIPS 2022 D&B, 2022-2024. <https://github.com/pygod-team/pygod> — fetched page.

<a id="ref-225"></a>225. Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr. *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents*. NeurIPS 2024 Datasets and Benchmarks Track, 2024. <https://github.com/ethz-spylab/agentdojo> — fetched page.

<a id="ref-226"></a>226. AGI Research (agiresearch). *Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents*. ICLR 2025, 2025. <https://github.com/agiresearch/ASB> — fetched page.

<a id="ref-227"></a>227. UIUC Kang Lab. *InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents*. arXiv, 2024. <https://github.com/uiuc-kang-lab/InjecAgent> — fetched page.

<a id="ref-228"></a>228. Barres, Dong, Ray, Si, Narasimhan. *τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment (tau2-bench repo)*. arXiv / Sierra Research, 2025. <https://github.com/sierra-research/tau2-bench> — fetched page.

<a id="ref-229"></a>229. Shengyue Guan, Yihao Liu, Lang Cao. *SupChain-Bench: Benchmarking Large Language Models for Real-World Supply Chain Management*. ACL 2026 Findings (per README), 2026. <https://github.com/Damon-GSY/SC-bench> — fetched page.

<a id="ref-230"></a>230. various. *GitHub repository search results for 'AIS spoofing detection' (e.g. FogProtocol/ais-spoof-detector, cognis-digital/spoofwatch)*. GitHub, 2026. <https://github.com/FogProtocol/ais-spoof-detector> — fetched page.

<a id="ref-231"></a>231. *snap-stanford/relbench*. GitHub (Stanford SNAP), 2024-2026. <https://github.com/snap-stanford/relbench> — fetched page.

<a id="ref-232"></a>232. *IALA GUIDELINE 1082 AN OVERVIEW OF AIS Edition 2.0 June 2016*. IALA (hosted by USCG NAVCEN), 2016. <https://www.navcen.uscg.gov/sites/default/files/pdf/IALA_Guideline_1082_An_Overview_of_AIS.pdf> — seen in search results.

<a id="ref-233"></a>233. DCSA. *DCSA Conformance-Gateway – DCSA conformance framework and reference implementations*. GitHub, 2026. <https://github.com/dcsaorg/Conformance-Gateway> — fetched page.

<a id="ref-234"></a>234. *GH Renton & Co Ltd v Palmyra Trading Corp*. CMI case database, 1956. <https://cmlcmidatabase.org/gh-renton-co-ltd-v-palmyra-trading-corp> — seen in search results.

<a id="ref-235"></a>235. *285 F3d 808 Sea-Land Service Inc v. Lozen International Llc Llc*. OpenJurist (9th Cir.), 2002. <https://m.openjurist.org/285/f3d/808> — seen in search results.

<a id="ref-236"></a>236. Alex L. Zhang, Tim Kraska, Omar Khattab (MIT OASYS lab). *GitHub - alexzhang13/rlm: General plug-and-play inference library for Recursive Language Models (RLMs), supporting various sandboxes.*. GitHub, 2025-2026. <https://github.com/alexzhang13/rlm> — fetched page.

<a id="ref-237"></a>237. Alex L. Zhang, Tim Kraska, Omar Khattab. *Recursive Language Models*. arXiv, 2025 (Dec; BibTeX year 2026). <https://arxiv.org/abs/2512.24601> — seen in search results.

<a id="ref-238"></a>238. Stanford NLP / DSPy contributors. *dspy-3.4.0-py3-none-any.whl (package source: dspy/predict/rlm.py, dspy/clients/typesafe.py, dspy/adapters/types/decision.py, dspy/teleprompt/reanchor)*. PyPI (files.pythonhosted.org), 2026. <https://files.pythonhosted.org/packages/17/96/31628d4231b5dd7edbe9eaf5c975d1055f4b79b337062a1f957dca6dd931/dspy-3.4.0-py3-none-any.whl> — seen in search results.

<a id="ref-239"></a>239. Alex L. Zhang, Tim Kraska, Omar Khattab. *Recursive Language Models (v2, adds RLM-Qwen3-8B)*. arXiv 2512.24601v2, 2026. <https://arxiv.org/html/2512.24601v2> — seen in search results.

<a id="ref-240"></a>240. *alexzhang13/rlm training harness (training/ directory)*. GitHub, 2026. <https://github.com/alexzhang13/rlm/tree/main/training> — fetched page.

<a id="ref-241"></a>241. not stated. *jev (PyPI package: 'Decorator that compiles Python function definitions into Jev (TypeSafe System One) queries')*. PyPI, 2026. <https://pypi.org/pypi/jev/json> — fetched page.

<a id="ref-242"></a>242. DigitalOcean resources. *Jev / System One launch coverage (What is Jev? TypeSafe AI's System One decision model)*. DigitalOcean, 2026. <https://www.digitalocean.com/resources/articles/what-is-jev> — seen in search results.

<a id="ref-243"></a>243. *TypeSafe AI GitHub organisation (typesafe-ai)*. GitHub, 2026. <https://github.com/typesafe-ai> — fetched page.

<a id="ref-244"></a>244. *@typesafe-ai/sdk (npm registry metadata)*. npm, 2026. <https://registry.npmjs.org/@typesafe-ai%2fsdk> — fetched page.

<a id="ref-245"></a>245. vLLM project. *vLLM docs: Structured Outputs*. GitHub (docs source), 2026. <https://raw.githubusercontent.com/vllm-project/vllm/main/docs/features/structured_outputs.md> — fetched page.

<a id="ref-246"></a>246. *typesafe-ai/system-one-adapter-python*. GitHub, 2026. <https://github.com/typesafe-ai/system-one-adapter-python> — fetched page.

<a id="ref-247"></a>247. *mlc-ai/xgrammar*. GitHub, 2024-2026. <https://github.com/mlc-ai/xgrammar> — fetched page.

<a id="ref-248"></a>248. *guidance-ai/llguidance*. GitHub, 2025-2026. <https://github.com/guidance-ai/llguidance> — fetched page.

<a id="ref-249"></a>249. *getzep/graphiti*. GitHub (Zep), 2025-2026. <https://github.com/getzep/graphiti> — fetched page.

<a id="ref-250"></a>250. *HKUDS/LightRAG*. GitHub (HKU), 2024-2026. <https://github.com/HKUDS/LightRAG> — fetched page.

<a id="ref-251"></a>251. *microsoft/graphrag*. GitHub (Microsoft), 2024-2026. <https://github.com/microsoft/graphrag> — fetched page.

<a id="ref-252"></a>252. Allen Institute for AI. *allenai/olmocr*. GitHub, 2025-2026. <https://github.com/allenai/olmocr> — fetched page.

<a id="ref-253"></a>253. Haoran Wei, Yaofeng Sun, Yukun Li. *deepseek-ai/DeepSeek-OCR (DeepSeek-OCR: Contexts Optical Compression, arXiv:2510.18234)*. GitHub / arXiv, 2025. <https://github.com/deepseek-ai/DeepSeek-OCR> — fetched page.

<a id="ref-254"></a>254. *docling-project/docling*. GitHub (LF AI & Data), 2024-2026. <https://github.com/docling-project/docling> — fetched page.

<a id="ref-255"></a>255. Global Trade Review. *Singapore ups fight against fraud with real-time BL verification tool*. GTR, 2024-2025 (not shown). <https://www.gtreview.com/news/asia/singapore-ups-fight-against-fraud-with-real-time-bl-verification-tool/> — seen in search results.

<a id="ref-256"></a>256. *amazon-science/chronos-forecasting (Chronos-2: From Univariate to Universal Forecasting, arXiv:2510.15821)*. GitHub (Amazon), 2025. <https://github.com/amazon-science/chronos-forecasting> — fetched page.

<a id="ref-257"></a>257. *huggingface/trl docs/source/paper_index.md*. GitHub (Hugging Face), 2026. <https://github.com/huggingface/trl/blob/main/docs/source/paper_index.md> — fetched page.

<a id="ref-258"></a>258. *BytedTsinghua-SIA/DAPO*. GitHub (ByteDance Seed / Tsinghua AIR), 2025. <https://github.com/BytedTsinghua-SIA/DAPO> — fetched page.

<a id="ref-259"></a>259. Lakshya A. Agrawal, Shangyin Tan, ... Matei Zaharia, Omar Khattab. *gepa-ai/gepa (GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning, arXiv:2507.19457)*. GitHub / arXiv, 2025-2026. <https://github.com/gepa-ai/gepa> — fetched page.

<a id="ref-260"></a>260. Taskforce.sh. *bullmq README.md*. GitHub, 2026. <https://raw.githubusercontent.com/taskforcesh/bullmq/master/README.md> — fetched page.

<a id="ref-261"></a>261. *taskforcesh/bullmq*. GitHub (Taskforce.sh), 2026. <https://github.com/taskforcesh/bullmq> — fetched page.

<a id="ref-262"></a>262. Taskforce.sh. *BullMQ Python: Introduction*. GitHub (docs source), 2026. <https://raw.githubusercontent.com/taskforcesh/bullmq/master/docs/gitbook/python/introduction.md> — fetched page.

<a id="ref-263"></a>263. Temporal Technologies. *temporalio/temporal LICENSE*. GitHub, 2025. <https://raw.githubusercontent.com/temporalio/temporal/main/LICENSE> — fetched page.

<a id="ref-264"></a>264. Temporal Technologies. *temporalio/sdk-python temporalio/contrib directory*. GitHub, 2026. <https://github.com/temporalio/sdk-python/tree/main/temporalio/contrib> — fetched page.

<a id="ref-265"></a>265. Apache Software Foundation. *Apache Kafka docs: upgrade.md*. GitHub (docs source), 2026. <https://raw.githubusercontent.com/apache/kafka/trunk/docs/getting-started/upgrade.md> — fetched page.

<a id="ref-266"></a>266. Synadia / NATS maintainers. *Releases · nats-io/nats-server*. GitHub, 2026. <https://github.com/nats-io/nats-server/releases> — fetched page.

<a id="ref-267"></a>267. Redpanda Data, Inc.. *redpanda-data/redpanda licenses/bsl.md*. GitHub, 2026. <https://raw.githubusercontent.com/redpanda-data/redpanda/dev/licenses/bsl.md> — fetched page.

<a id="ref-268"></a>268. Microsoft. *Circuit Breaker pattern (Azure Architecture Center source)*. Microsoft Azure Architecture Center, 2026. <https://raw.githubusercontent.com/MicrosoftDocs/architecture-center/main/docs/patterns/circuit-breaker.md> — seen in search results.

<a id="ref-269"></a>269. Microsoft. *Saga pattern (Azure Architecture Center source)*. Microsoft Azure Architecture Center, 2026. <https://raw.githubusercontent.com/MicrosoftDocs/architecture-center/main/docs/patterns/saga-content.md> — fetched page.

<a id="ref-270"></a>270. Microsoft. *Idempotent Consumer pattern (Azure Architecture Center source)*. Microsoft Azure Architecture Center, 2026. <https://raw.githubusercontent.com/MicrosoftDocs/architecture-center/main/docs/patterns/idempotent-consumer.md> — fetched page.

<a id="ref-271"></a>271. OpenTelemetry. *open-telemetry/semantic-conventions-genai*. GitHub / CNCF OpenTelemetry, 2026. <https://github.com/open-telemetry/semantic-conventions-genai> — fetched page.

<a id="ref-272"></a>272. Langfuse. *langfuse/langfuse LICENSE*. GitHub, 2026. <https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE> — fetched page.

<a id="ref-273"></a>273. Neo4j, Inc.. *neo4j/neo4j LICENSE.txt*. GitHub, 2026. <https://raw.githubusercontent.com/neo4j/neo4j/dev/LICENSE.txt> — fetched page.

<a id="ref-274"></a>274. FalkorDB. *FalkorDB LICENSE.txt*. GitHub, 2026. <https://raw.githubusercontent.com/FalkorDB/FalkorDB/master/LICENSE.txt> — fetched page.

<a id="ref-275"></a>275. Memgraph Ltd. *memgraph/memgraph LICENSE*. GitHub, 2026. <https://raw.githubusercontent.com/memgraph/memgraph/master/LICENSE> — fetched page.

<a id="ref-276"></a>276. The ggml authors. *ggml-org/llama.cpp LICENSE*. GitHub, 2026. <https://raw.githubusercontent.com/ggml-org/llama.cpp/master/LICENSE> — fetched page.

<a id="ref-277"></a>277. *QwenLM Qwen3.5 / Qwen3.6 repository page*. GitHub (Alibaba Qwen), 2026. <https://github.com/QwenLM/Qwen3.6> — fetched page.

<a id="ref-278"></a>278. *google-deepmind/gemma and gemma 4.0.1 PyPI wheel*. GitHub / PyPI (Google DeepMind), 2026. <https://github.com/google-deepmind/gemma> — fetched page.

<a id="ref-279"></a>279. *dspy (PyPI JSON metadata, version 3.4.0)*. PyPI, 2026. <https://pypi.org/pypi/dspy/json> — fetched page.

<a id="ref-280"></a>280. PyGOD team. *PyGOD: A Python Library for Graph Outlier Detection*. JMLR vol. 25 (2024), 2024. <https://github.com/pygod-team/pygod> — fetched page.

<a id="ref-281"></a>281. Arize AI. *Arize-ai/phoenix LICENSE*. GitHub, 2026. <https://raw.githubusercontent.com/Arize-ai/phoenix/main/LICENSE> — fetched page.

<a id="ref-282"></a>282. *Nationwide Automatic Identification System 2025*. NOAA InPort (Office for Coastal Management), 2025. <https://www.fisheries.noaa.gov/inport/item/77594> — seen in search results.

<a id="ref-283"></a>283. *AIS data management policy (Danish Maritime Authority)*. Danish Maritime Authority, n.d.. <https://dma.dk/safety-at-sea/navigational-information/ais-data/ais-data-management-policy-> — seen in search results.

<a id="ref-284"></a>284. CIA-Oceanix (IMT Atlantique group). *TrAISformer – A generative transformer for AIS trajectory prediction (repo)*. arXiv / GitHub, 2021. <https://github.com/CIA-Oceanix/TrAISformer> — fetched page.

<a id="ref-285"></a>285. sondreskarsten. *kystverket-ais-collector – Cloud Run Job: AIS positions collector for kystdatahuset*. GitHub, 2026. <https://github.com/sondreskarsten/kystverket-ais-collector> — fetched page.

<a id="ref-286"></a>286. Global Fishing Watch. *gfw-api-python-client (Global Fishing Watch API Python client)*. GitHub / PyPI, 2026. <https://github.com/GlobalFishingWatch/gfw-api-python-client> — fetched page.

<a id="ref-287"></a>287. eu-cdse (Copernicus Data Space Ecosystem). *Copernicus Data Space Ecosystem documentation – Quotas and Limitations (Quotas.qmd)*. GitHub (official CDSE org), 2026. <https://github.com/eu-cdse/documentation> — fetched page.

<a id="ref-288"></a>288. pipeworx-io. *mcp-imf-portwatch – IMF PortWatch MCP (global maritime trade & chokepoint signals)*. GitHub, 2026. <https://github.com/pipeworx-io/mcp-imf-portwatch> — fetched page.

<a id="ref-289"></a>289. *DCSA publishes Track & Trace 3.0.0, expanding standard to cover IoT and reefer visibility - Cyprus Shipping News*. Cyprus Shipping News, 2026. <https://cyprusshippingnews.com/2026/10/06/dcsa-publishes-track-trace-3-0-0-expanding-standard-to-cover-iot-and-reefer-visibility/> — seen in search results.

<a id="ref-290"></a>290. Cellpap. *cma-cgm_client – Ruby gem for the Logistic Tracking service API (DCSA OpenAPI Track & Trace v2.2.0)*. GitHub, 2023. <https://github.com/Cellpap/cma-cgm_client> — fetched page.

<a id="ref-291"></a>291. canblmz1. *fmcsa-mirror-data – Daily mirror of public-domain FMCSA datasets (L&I authority + company census)*. GitHub, 2026. <https://github.com/canblmz1/fmcsa-mirror-data> — fetched page.

<a id="ref-292"></a>292. eugr (community). *eugr/spark-vllm-docker*. GitHub, 2026. <https://github.com/eugr/spark-vllm-docker> — fetched page.

<a id="ref-293"></a>293. ccfddl community. *ccf-deadlines – conference YAML files (nips, aaai, iclr, icml, MX/www, aamas, acl, ijcai, ecai, icde, wsdm, icdm, cikm, ndss, uss, sp, ccs)*. GitHub, 2026. <https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference/MX/www.yml> — seen in search results.

<a id="ref-294"></a>294. ccfddl community. *ccf-deadlines – conference/DB/sigkdd.yml (KDD deadlines)*. GitHub, 2026. <https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference/DB/sigkdd.yml> — seen in search results.
