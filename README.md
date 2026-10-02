# LLM-to-Flow Distillation — project page

An interactive research website for **LLM-to-Flow Distillation: Teaching Natural Language Goals to Scientific Generators**.

The site includes the authors’ main method figure and a scroll-aware contents menu, all five discovery tasks, 23 curriculum/assessment stages, 64 recorded candidate examples (each with two judge passes), plus 28 clearly marked placeholder slots, searchable/filterable traces, shareable task/subgoal URLs, and every value from the two main result tables. Five clickable goal cards switch a single results panel between tasks. The cards reproduce the paper’s natural-language goals, with large goal labels and colors identifying PepDFM (peptides) and FlowMol3 (molecules). The goal cards contain the task wording without numerical footers. Each selected task has one large rounded results panel with a generator-colored heading, without metric tiles; its goal card has a bold border, stronger fill, and a checked Selected badge. The panel includes brief appendix-sourced task and proxy-baseline context, expandable teacher-observable lists, and interactive curriculum buttons showing verbatim operative goals and linking to each stage’s judge traces. Both subgoal views display the original wording as an italic quotation, without editorial summary headings; training-round or assessment information sits below the quotation. Each peptide task has one activity–toxicity scatterplot. Both docking tasks use an interactive grouped bar chart with GNINA, |Vina|, and |rDock| on the x-axis, method-colored bars showing |method score| − |pretrained score|, with zero marking the pretrained baseline. Black error bars retain each method’s printed Table 2 ± term with the pretrained mean treated as a fixed reference. The original signed values appear in the table and hover details. Proxy and observable descriptions are stacked to the left of the visible molecular docking PNG. The GSK3β table sits beside an interactive scaffold-novelty versus top-5% docking-quality plot on desktop, stacking on smaller screens. Its recorded means and Student-t 95% CIs across five sampling seeds are preserved, with interval whiskers matching each method’s marker. Numerical-table method names use the same palette with larger 16px type; table headers are 13px and result headings are 20px. Hover, focus, or tap the scaffold x-axis label for the scaffold metric definition. The old rounds plot and data disclosure remain removed; constrained design prominently shows zero full-goal hits in 38,500 pretrained samples beside the user-supplied `assets/hitGoal5.png`, alongside its selectable subgoal inspector and discovery-evidence table. Every plot uses marker legends and hover/tap values. It works without a JavaScript framework, runtime CDN, API key, or paid service.

The page uses a white background, self-hosted Inter fonts, and a compact centered paper title/author block. The larger left contents rail sits beside the reading column on wide screens and tracks the current section; on smaller screens it becomes an expandable contents button. The Method section follows the authors’ introduction and algorithm: a sequence of goal regions followed by the sample, SetGoal, LLM-Judge, and Minimize operations. A section divider separates “Method: LLM-to-Flow Distillation” from the opening figure; its contents-menu label is “Method (LFD)”. Results appears before the interactive trace explorer in both the page and the contents menu. The mathematical introduction and eight-line numbered pseudocode sit side by side on desktop and stack on smaller screens. The algorithm is capped at 460px and 40% of the desktop content width, and uses paper-style serif type in a softly colored, rounded box, with no comment lines or equation references. Below it, the authors’ KL interpretation uses the full section width with left-aligned prose and centered display equations. The two equivalent implicit-target expressions are individually centered. Paper links (including the arxiv button), numbered table/figure references, appendix mentions, and the citation block are removed from the rendered page. Evaluation notes remain below the trace explorer; the original provenance is retained in the source JSON and repository evidence files. The interpretation states the Bradley–Terry assumption and gives both the exponential-tilt target and its equivalent KL-regularized variational objective. Hover or focus the underlined operations to inspect their details, or click/tap to keep the panel open. Minimize includes the DPO loss and the surrogate-based update; Escape, the close control, and outside clicks dismiss the panel. The introduction uses Inter; the algorithm uses the self-hosted KaTeX serif family, with blue function controls and responsive type sizing. Equations use self-hosted KaTeX 0.18.10 with accessible MathML and readable text fallbacks. Font, icon, and renderer credits are in `assets/ATTRIBUTIONS.txt`.

## Preview

[Desktop preview](preview.png) · [Docking results preview](preview-docking.png) · [Table and novelty preview](preview-novelty.png) · [Subgoal preview](preview-subgoals.png) · [Trace explorer preview](preview-traces.png)

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

`python3.11 scripts/import_traces.py --archive-root /path/to/archive` reproducibly imports only allowlisted fields from existing local records, without making model calls. SHA-256 receipts in `data/trace-sources.json` bind each candidate representation, both judgments, and the selected goal explanation to their sources. The explorer displays each size-matched positive/negative pair in a row on desktop and stacks it on mobile. It supports copying sequences/SMILES, switching judge passes, search, and label filters. The Sources tab/panel is removed; old links to that tab open Goal rationale. Source receipts remain in the repository data files. The goal-rationale view contains only the rationale card; curriculum-progress blocks, candidate shortcuts, context notes, and the copy-link/download footer are removed.


- `assets/paper.pdf` is the supplied 43-page preprint, preserved byte-for-byte. `data/provenance.json` records its source filename and SHA-256.
- `data/tasks.json` contains verbatim curricula, explicit teacher goal-selection explanations, and selected candidate sequences/SMILES with verbatim judgment rationales and uncertainties. Two judge passes can be inspected for each recorded candidate. These are illustrative, **not** a complete raw trace export. Original final goals are distinguished from LLM-proposed subgoals. Public exports exclude provider reasoning metadata and private paths.
- Every peptide and GSK3β stage has two distinct stable-positive and two distinct stable-negative candidates. Examples are editorially curated in `data/trace-pairs.json` for explicit, consistent explanations and size diversity, without ranking by downstream activity or docking. Each peptide stage pairs positives and negatives at exactly 12 and 38 amino acids. Molecular stages contain a smaller and a larger pair, with less than 20 Da between the positive and negative in each pair. These are illustrative comparisons, not random samples or causal controls. D2 and constrained-design stages each have four neutral, explicitly labeled placeholder slots; these contain no invented candidate, rationale, uncertainty, or recorded label. Earlier illustrative paraphrases remain archived in `data/trace-summary-archive.json`.
- The constrained task’s zero-update final assessment is kept separate from the intermediate training goal. The appendix/main-text numbering discrepancy is documented.
- `data/source-hashes.json` contains verified source receipts without private absolute filesystem paths. Raw research archives and credentials are not part of this repository.
- `data/result-panels.json` records the five exact paper goals and the reported constrained-design outcomes with their source pages. Goal 5 has different sampling budgets and qualitative discovery evidence; no synthetic metric or success rate is introduced.
- `data/charts.json` preserves the aggregate values behind Figure 7(c,d), source CSV hashes, sampling counts, and uncertainty definitions. GSK3β trajectory intervals are descriptive and not selection-adjusted; novelty intervals are conditional on frozen checkpoints. No numeric D2 plot source was found, so its original panels remain linked through the paper. Chart data contains no individual candidate sequences or private absolute paths.
- Self-hosted Plotly.js basic v4.1.1 renders plots directly in the page; its MIT license is included under `assets/plotly/`. Plotting needs no runtime CDN, external API, or account.
- `data/results.json` transcribes Tables 1–2, including all printed ± terms. Their uncertainty type is not relabeled or inferred. These are computational outcomes, not measured biological efficacy.
- The paper’s exploratory anticancer continuation and CPP checkpoint-selection exception are retained in the relevant evidence panels. Published curricula and metrics are not altered.

Edit the JSON sources and run `python3 scripts/build.py` to regenerate `data/site-data.js` and `dist/`. The build also versions local script and stylesheet URLs by content hash so browsers load changed assets after a normal refresh. It validates stage counts, training-update totals, labels, source receipts, paper hash, and local links. Browser checks are in `scripts/check_browser.py`; `scripts/check_method_interactions.py` additionally tests hover, keyboard, pinning, touch, and responsive positioning. Both use Playwright and Chromium only for development.

Visual references supplied by the authors: [Vera](https://vera-layered-diffusion.github.io/) and [Discrete Flow Maps](https://malbergo.me/discrete-flow-maps.github.io/). The layout and interactive components here are original. Paper and figure rights remain with their authors; this repository does not assign them a new license.

Interactive chart checks are in `scripts/check_results.py`. They verify all five task switches and keyboard/touch controls, peptide activity/toxicity coordinates, grouped docking deltas with negative improvements, signed hover values and black error bars, the GSK3β novelty plot and table layout, always-visible docking figures, the fifth-task evidence, and layouts from 360px through 2560px.
