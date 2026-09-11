# Little Dorrit Editor Benchmark

> Vision language models reading handwritten corrections on printed pages from Charles Dickens’ Little Dorrit.

Given a scanned page, each model identifies the edits and returns the original text, intended correction, and location as JSON. Recognizing words is only part of the task: a model must also interpret carets, crossed-out phrases, and handwritten punctuation.

## Task and evaluation

Each correction includes an edit type (insertion, deletion, replacement, punctuation, capitalization, or italicize), original text, corrected text, line number, and the supplied page identifier. Line 0 is for titles or headings; body text begins at line 1. Predicted edits are compared with ground truth using an LLM judge. Scores aggregate TP, FP, and FN across pages and runs.

The interactive site offers Performance, Token price, Value & frontier, Rankings, and Detailed results. Performance defaults to all models. The value view compares F1 with an illustrative token workload, using logarithmic cost spacing and linear F1. It is not a measured cost-per-page chart. Confidence intervals help interpret close F1 scores; a point-estimate Pareto frontier does not incorporate that uncertainty.

## Data and documentation

- [Complete rankings, pricing, and caveats](https://dorrit.pairsys.ai/rankings.md)
- [Static HTML rankings](https://dorrit.pairsys.ai/rankings.html)
- [Raw edit-level results](https://dorrit.pairsys.ai/results.json)
- [Dated pricing snapshot and sources](https://dorrit.pairsys.ai/pricing.json)
- [Technical report](https://dorrit.pairsys.ai/technical-report.pdf)
- [Example page](https://dorrit.pairsys.ai/001.png)
- [Code and experiment configurations](https://github.com/PAIR-Systems-Inc/little-dorrit-editor)
- [Dataset](https://huggingface.co/datasets/pairsys/little-dorrit-editor)
