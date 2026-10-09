# When the Data Lies: the short version

*Brief for sharing, 9 October 2026. Every number below is sourced in the [full document](final_topic_when_the_data_lies.md); vendor figures are unaudited.*

**Topic.** When the Data Lies: fidelity-gated AI agents for spoofed, stolen and broken logistics evidence.

**Paper 1 (working title).** Fidelity-Gated Automation for Liner-Shipping Commitments under GNSS Interference: Corruption-Aware Divergence Detection and Risk-Controlled Decisions.

## The problem

Logistics firms are letting AI agents rebook, reroute and release cargo on their own. Those agents trust three things: where the ship is, who the carrier is, and what the carrier promised. In 2026 all three failed at scale:

- **Location.** Within about a day of the 28 February strikes on Iran, Windward counted more than 1,100 ships in the Gulf with GPS/AIS interference.
- **Identity.** US and Canada cargo-theft losses reached about USD 725M in 2025 (Verisk CargoNet, quoted by the FBI). Attackers take over real carriers' accounts and registry records.
- **Commitment.** From 3 March, MSC and other carriers ended voyages at substitute ports and passed the extra cost to cargo owners.

Agent-security tools stop bad *instructions*. They do not catch a well-formed but false position, identity or promise. In our searches, nothing checks whether the evidence behind an action is true, how hard it is to fake, and how far a mistake would spread before the agent acts.

## What we will do

1. **Build the gate.** For each proposed action, score how reliable the evidence is *for that action*, require independent confirmations, weigh how far a mistake would spread, and return ACT, VERIFY, REVIEW or HOLD, with a calibrated cap on harmful automated actions.
2. **Build the commitment watch.** Flag early when a ship stops following the route the carrier promised, while giving little weight to positions from jammed areas.
3. **Build an open benchmark.** Use open AIS archives (US, Denmark, Norway, Finland) with synthetic attacks and deviations that carry exact labels. Test against strong baselines and an adaptive red team.
4. **Run a 2026 Gulf case study.** Use carrier notices and event data, reported descriptively, since free historical Gulf tracks don't exist.

## Path to publication

| When | What |
|---|---|
| Oct 2026 – Jan 2027 | Read the core papers in full, write the formal model, start a Gulf AIS recorder, build the data pipeline and benchmark v0.1, pre-register the main metrics |
| Feb – Apr 2027 | Build the gate and the change detector. Go/no-go at the end of April |
| May – Aug 2027 | Full experiments, red team, Gulf case study, writing |
| By Sep 2027 | Submit Paper 1 to Transportation Research Part E or C (Q1 per a third-party JCR 2025 list; confirm with your library) |
| 2028 | Paper 2 on identity fraud and cost-to-deceive, the benchmark paper, and the TrackTrust product |

**Before submitting:** open and read every source you cite, declare AI-tool use as the journal requires, and check whether your institution needs ethics review for any pilot or partner data.

## Honest limits

- A Q1 paper is realistic, not guaranteed; acceptance most likely lands in 2028.
- The system can show that a carrier diverged from its promise and what that costs. It cannot prove *why*.
- Carriers dumping cargo mid-voyage to take a higher bidder's cargo rests on one anecdotal 2020 trade-press report. Don't claim it as a practice.
- Don't headline the "61% of Hormuz transits were fake" figure: it has one unaudited source.
