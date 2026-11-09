# Motivation Stacking Engine & Scoring Standards

This document defines the quantitative motivation scoring framework implemented in `rel-aly-works`.

---

## 1. The Theory of Motivation Stacking

In off-market real estate acquisition, a single distress factor (e.g., an absentee owner) rarely leads to an actionable deal. However, when **multiple orthogonal distress vectors intersect** on the same property (e.g., an absentee owner whose inherited property has an active HOA assessment lien and delinquent ad valorem taxes), the likelihood of seller capitulation increases exponentially.

```
       ┌────────────────────────┐
       │   PROBATE / HEIRSHIP   │ (Liquidation urgency, estate dispersion)
       └───────────┬────────────┘
                   │
  ┌────────────────┼────────────────┐
  │                                 │
  ▼                                 ▼
┌──────────────────────┐    ┌──────────────────────┐
│   HOA LIEN / SUIT    │    │   TAX DELINQUENCY    │
│ (Accelerated threat) │    │ (County tax seizure) │
└──────────┬───────────┘    └──────────┬───────────┘
           │                           │
           └──────────────┬────────────┘
                          ▼
             ┌─────────────────────────┐
             │  COMPOUND MOTIVATION    │ (Distress Count >= 2, Score >= 75)
             │   HIGH-PRIORITY DEAL    │
             └─────────────────────────┘
```

---

## 2. Base Distress Signals & Weights

The base motivation score is calculated as a weighted summation across independent distress indicators, capped at a maximum of 100 points.

| Distress Vector | Base Points | Severity Class | Business Logic & Justification |
| :--- | :---: | :---: | :--- |
| **Notice of Trustee Sale / Lis Pendens** | **+40** | Critical | Active foreclosure clock is ticking. Legal deadline forces decision. |
| **Probate Docket / Affidavit of Heirship** | **+35** | High | Deceased owner. Beneficiaries frequently prefer cash liquidation over maintenance and property taxes. |
| **HOA Assessment Lien** | **+25** | High | In Texas, HOAs possess expedited foreclosure rights under Chapter 209 of the Texas Property Code. |
| **Tax Delinquency ($\ge 1$ year)** | **+20** | Medium | Inability or refusal to pay ad valorem taxes; county tax foreclosure suit is pending or active. |
| **Abstract of Judgment / Mechanic's Lien** | **+15** | Medium | Personal insolvency or contractor disputes clouding the property title. |
| **Absentee Owner (Out-of-State / City)** | **+15** | Low/Mod | Non-homestead property where the owner's mailing address is in another city or out-of-state. High landlord fatigue. |
| **High Equity ($\ge 50\%$)** | **+10** | Advantage | Sufficient margin for creative acquisition, subject-to, or cash discounted offer. |

---

## 3. Stacking Multiplier & Exponential Boost

Properties exhibiting overlapping distress factors receive a **Stacking Multiplier** ($M_s$) to prioritize multi-distress opportunities over single-signal records:

$$M_s = \begin{cases} 
1.00 & \text{if } N_{\text{distress}} = 1 \\
1.25 & \text{if } N_{\text{distress}} = 2 \\
1.50 & \text{if } N_{\text{distress}} \ge 3 
\end{cases}$$

$$\text{FinalScore} = \min\left(100, \text{round}\left(\left(\sum \text{BasePoints}\right) \times M_s\right)\right)$$

### Tier Classification

* **Tier 1: High Urgency (Score $\ge 75$, Distress Count $\ge 2$):**
  Immediate target for high-touch skip tracing, cold call, and direct mail.
* **Tier 2: Moderate Distress (Score $50 - 74$):**
  Monitored on weekly watchlists; targeted via sequence mailers.
* **Tier 3: Passive Lead (Score $< 50$):**
  Archived in analytical rolls for historical tracking and trend monitoring.

---

## 4. Time Decay Factor

Distress events that occurred recently carry substantially higher liquidation pressure than historical recordings:

$$\text{DecayMultiplier} = \exp\left(-\frac{\Delta t}{365}\right)$$

Where $\Delta t$ is the number of days elapsed since the recording date of the distress instrument.
* Records filed $< 60$ days ago retain $> 85\%$ strength.
* Records filed $> 180$ days ago decay to $< 60\%$ strength unless accompanied by a subsequent filing.
