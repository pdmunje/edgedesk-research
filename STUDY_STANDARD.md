# Required format for every EdgeDesk backtest

Use the approved momentum report's plain-English structure and shared website layout.

1. **Question and answer:** What are we trying to learn? What happened, and why does it matter?
2. **Exact rules:** Write every formula and the order of decisions in readable pseudocode. Define inputs, units, timeframe, update schedule, zero values and when prices become available. Include a made-up worked example clearly labelled as illustrative.
3. **What gets counted:** Define the measured event (a trade, a price touch, an uninterrupted signal, etc.). Explain exactly when its clock starts and stops. Define each statistic and percentage denominator.
4. **Results:** Use descriptive table headings, explicit time/price units and sample counts. Separate observations from interpretation. Never confuse signal persistence, target touches, or later-price movement with realized trading profit.
5. **Meaning for the reader:** State what the evidence supports and what remains untested. Mark any proposed new rule as untested until it has its own calculation.
6. **Extra checks and data handling:** Explain sample dates, exclusions, missing data, futures rolls, execution timing, costs, earlier/later sample checks, and all exploratory parameter searches. Put optional detail in expandable sections.
7. **Dig deeper:** Link to a specific version of public calculation code, summarized results, input schema and source fingerprint, pinned dependencies, and reproduction instructions. No private machine paths or original vendor data.

Always include a source-evidence record, calculation status, human approval record and change history. Old model output is a lead to investigate, not verification. Use the same fields for every symbol; symbols must be metadata, not hard-coded into the site design.

Do not replace explanations with private shorthand or require a reader to inspect code to understand the study.

