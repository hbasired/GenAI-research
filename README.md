# GenAI Research: Data Fidelity and Agentic AI in Logistics

Research workspace for choosing and developing a Q1-publishable topic on how data fidelity affects agentic AI in logistics and supply chains.

## Start here

- **Final topic:** [When the Data Lies](research-topics/final_topic_when_the_data_lies.md): fidelity-gated, spoof-resilient AI agents for location, identity and carrier-commitment evidence in maritime and freight logistics (also as `.html`).
- [`research-topics/README.md`](research-topics/README.md): overview, scorecard and recommendation across the three candidate topics that led to the final choice (also as `research-topics/00_overview.html`).
- [Topic 1 · Know When Not to Act](research-topics/topic1_fidelity_gated_autonomy.md): decision-aware data fidelity and risk-gated autonomy.
- [Topic 2 · When the Data Lies](research-topics/topic2_spoof_resilient_logistics.md): spoof-resilient agents for location and identity fidelity.
- [Topic 3 · Prove It Before It Ships](research-topics/topic3_verified_traceability.md): privacy-preserving evidence agents for EUDR, CBAM and battery-passport data.

Each topic has a matching `.html` reading version in `research-topics/`. To rebuild the HTML after editing a Markdown file:

```bash
pip install markdown==3.7
python research-topics/_build/build_pages.py
```

## Earlier material

- [`data_fidelity_agentic_supply_chain_research_dossier_full.md`](data_fidelity_agentic_supply_chain_research_dossier_full.md): the original ChatGPT dossier. Section 5 of the overview lists what was confirmed, what needs updating, and what it missed.
