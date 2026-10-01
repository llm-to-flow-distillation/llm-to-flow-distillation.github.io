# LLM-to-Flow Distillation — project page

An interactive research website for **LLM-to-Flow Distillation: Teaching Natural Language Goals to Scientific Generators**.

The site includes the authors’ main method figure and a scroll-aware contents menu, all five discovery tasks, 23 curriculum/assessment stages, 36 illustrative recorded judgments, searchable/filterable traces, shareable task/subgoal URLs, JSON downloads, the full paper, and every value from the paper’s two main result tables. It works without a JavaScript framework, runtime CDN, API key, or paid service.

The page uses a white background, self-hosted Inter fonts, and a compact centered paper title/author block. The left contents rail tracks the current section; on smaller screens it becomes an expandable contents button. The Method section follows the authors’ introduction and algorithm: a sequence of goal regions followed by the sample, SetGoal, LLM-Judge, and Minimize operations. A section divider separates Method from the opening figure. The mathematical introduction and eight-line numbered pseudocode sit side by side on desktop and stack on smaller screens. The compact algorithm uses paper-style serif type in a softly colored, rounded box, with no comment lines or equation references. Below it, the authors’ KL interpretation states the Bradley–Terry assumption and gives both the exponential-tilt target and its equivalent KL-regularized variational objective. Hover or focus the underlined operations to inspect their details, or click/tap to keep the panel open. Minimize includes the DPO loss and the surrogate-based update; Escape, the close control, and outside clicks dismiss the panel. The introduction uses Inter; the algorithm uses the self-hosted KaTeX serif family, with blue function controls and responsive type sizing. Equations use self-hosted KaTeX 0.18.10 with accessible MathML and readable text fallbacks. Font, icon, and renderer credits are in `assets/ATTRIBUTIONS.txt`.

## Preview

[Desktop preview](preview.png) · [Trace explorer preview](preview-traces.png)

From this directory, using Python 3.9 or newer:

```bash
python3 scripts/build.py
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

If workspace storage is limited, use `python3 scripts/build.py --output-dir /tmp/lfd-site` and serve that directory instead.

Open `http://localhost:8000`. On a remote cluster, forward port 8000 in VS Code or through SSH. The checked-in `index.html` also works directly after building; task data is loaded as a local script.

## Publish at the exact requested URL

GitHub serves an organization site at `https://<organization>.github.io/` from a repository named `<organization>.github.io`. Therefore the target is:

```text
Owner:       llm-to-flow-distillation
Repository:  llm-to-flow-distillation.github.io
Website:     https://llm-to-flow-distillation.github.io/
```

Create a **free GitHub organization** named `llm-to-flow-distillation`, with FedericoDiGennaro as its owner, then create the public repository `llm-to-flow-distillation.github.io` in that organization. In Settings → Pages, select **GitHub Actions** as the build source. Push this website repository’s `main` branch; the included workflow validates and deploys only `dist/`.

With GitHub CLI access to that organization, these are the equivalent repository commands, run from this directory after organization creation:

```bash
gh repo create llm-to-flow-distillation/llm-to-flow-distillation.github.io \
  --public --source=. --remote=origin \
  --description 'LLM-to-Flow Distillation: interactive research project page'
gh api --method POST repos/llm-to-flow-distillation/llm-to-flow-distillation.github.io/pages \
  -f build_type=workflow
git push -u origin main
```

Organization creation is an account-level GitHub step. The existing research repository’s SSH deploy key cannot create a new organization/repository. No custom domain or CNAME file is needed. A personal repository called `llm-to-flow-distillation` would also collide, case-insensitively, with Federico’s existing `LLM-to-Flow-Distillation` code repository.

Official instructions: [organization creation](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/creating-a-new-organization-from-scratch), [GitHub Pages URL rules](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Evidence and editorial scope

- `assets/paper.pdf` is the supplied 43-page preprint, preserved byte-for-byte. `data/provenance.json` records its source filename and SHA-256.
- `data/tasks.json` contains the public curricula, selected judgment summaries, uncertainties, source labels, and checkpoint-selection caveats. These are illustrative, **not** a complete raw trace export. Peptide traces are high-level summaries without candidate sequences or operational design details.
- Every peptide and GSK3β stage includes positive and negative examples verified against both recorded judge passes. D2 and constrained-design intermediate judgments were unavailable; those stages explicitly show this gap. Their final-goal examples come from the paper.
- The constrained task’s zero-update final assessment is kept separate from the intermediate training goal. The appendix/main-text numbering discrepancy is documented.
- `data/source-hashes.json` contains verified source receipts without private absolute filesystem paths. Raw research archives and credentials are not part of this repository.
- `data/results.json` transcribes Tables 1–2, including all printed ± terms. Their uncertainty type is not relabeled or inferred. These are computational outcomes, not measured biological efficacy.
- The paper’s exploratory anticancer continuation and CPP checkpoint-selection exception are retained in the relevant evidence panels. Published curricula and metrics are not altered.

Edit the JSON sources and run `python3 scripts/build.py` to regenerate `data/site-data.js` and `dist/`. The build validates stage counts, training-update totals, labels, source receipts, paper hash, and local links. Browser checks are in `scripts/check_browser.py`; `scripts/check_method_interactions.py` additionally tests hover, keyboard, pinning, touch, and responsive positioning. Both use Playwright and Chromium only for development.

Visual references supplied by the authors: [Vera](https://vera-layered-diffusion.github.io/) and [Discrete Flow Maps](https://malbergo.me/discrete-flow-maps.github.io/). The layout and interactive components here are original. Paper and figure rights remain with their authors; this repository does not assign them a new license.
