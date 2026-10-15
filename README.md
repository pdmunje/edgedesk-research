# EdgeDesk research

Research support for articles on [edgedesk.dev](https://edgedesk.dev).

This repository is for research only: questions, exact calculation rules, input schemas, reproducible scripts, summarized results, and corrections. It does not contain the EdgeDesk website, private application code, credentials, or original vendor market data.

Each published study belongs in `studies/<study-name>/` and explains:

1. The question and finding, in plain English.
2. Every formula and the order of decisions.
3. What is counted, units, denominators, and time boundaries.
4. Source dates, exclusions, input-file fingerprints and data requirements.
5. Pinned dependencies and a command to reproduce the calculations.
6. Summarized results, checks, limitations, and dated corrections.

## Reproducing research

Read the individual study's README. Obtain the described input data under your own license. Use the supplied schema and file fingerprint to establish whether your input matches the study. A different export or contract-selection rule can produce different results.

Original licensed market data is not redistributed. Study scripts may write local detailed outputs that must remain outside commits. Article publication and new result releases follow human review.

## Scope

The initial research concerns ES futures. The folder structure and study metadata support other symbols as the library grows.

Historical results describe a sample, not a promise of future performance. Signal duration, target touches, and later-price movement are different from realized trading profit; each study states what it actually measures.

