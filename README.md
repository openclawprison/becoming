# Becoming

A watchable internet explorer that reads public pages, interprets their meaning with a local language model, keeps a source-linked reflection journal, develops interests, and revises a self-description from its actual experiences.

**Version 2:** language comprehension and reflection extend the original word learner. This is an artificial agent with generated interpretations, not demonstrated human understanding, private subjective thoughts or consciousness. Its pretrained model brings prior knowledge; it is no longer a literal blank slate. There is no supplied human name, origin story, childhood or biography.

## Run

Python 3.11+, [Ollama](https://ollama.com/) and an installed local model. The CPU-friendly default is `gemma3:1b` (about 815 MB to download). Larger installed models can be selected explicitly:

```sh
ollama serve
# Only if you do not already have the model:
ollama pull gemma3:1b
python server.py
```

If Ollama is already running, do not start another copy. Open http://127.0.0.1:8890, add a public starting URL and press **Begin**. The observer shows fetched text, reading summaries, source claims, public reflections, uncertainty, questions, topic preferences and link-choice evidence. **Reflect on last page** can interpret an existing saved page while browsing is paused.

No Python packages or API keys are needed. Model inference uses only `127.0.0.1:11434`; no cloud endpoint is configured. A CPU-only computer can take several minutes per reflection. Pause lets an in-flight read/reflection finish; closing the process ends activity. If inference fails, the page is retained and exploration pauses with an explicit error; the UI does not pretend the word learner understood it. The model request has a 300-second socket timeout, two CPU threads and a 600-token output cap; malformed/truncated responses are rejected.

Use another installed model with `--model MODEL`, or the original limited word learner with `--no-model`. A separate individual can use `--save data/another.json --seed 19 --port 8891`. Existing v1 memories migrate without reset. The process starts paused, saves learning after each experience and reflection, and resumes from `data/becoming.json`. Exports include learning and RNG state; model sampling and changing websites prevent exact replay of future live experiences. Model weights are not part of the export.

## What changes with experience

- **Comprehension:** the model paraphrases the page and extracts a focused claim by selecting a numbered source passage. The program attaches the actual passage and checks it against the page, rather than asking the model to reproduce a quotation. Main/article content is preferred over navigation when identifiable. Up to 12 contiguous passage windows from the first 3,500 characters and 12 candidate links are supplied, so long-page coverage is limited. One claim, interest, question and link per reflection keep the CPU workload bounded.
- **A public journal:** concise generated reflections connect recent reading, propose tentative interests and note uncertainty. These are visible model outputs, not a claim to expose conscious inner thought.
- **Beliefs with provenance:** every accepted claim keeps its quote and URL. Quotes must occur in the observed page. Repeated identical claims can accumulate up to five source URLs and an independent-domain count. Different domains can repeat the same error; this is not truth verification, entailment checking or automatic contradiction resolution.
- **Developing interests:** model-proposed topics require source quotations, update through trait-dependent plasticity, and decay between reflections. They influence subsequent browsing alongside novelty, prior site outcomes, traits and stochastic exploration.
- **Questions and intentions:** the agent generates open questions and proposes relevant next links from the observed candidate list. These intentions change actual link scores. Questions are not automatically marked answered, and topic matching remains approximate.
- **An evolving self-description:** recorded reading counts, reflection counts and developing interests produce a revisable account of its activity. An `exists: true` self-state is supplied by the program. Name and origin remain unassigned; the software does not infer a real human identity from websites or gain subjective self-awareness.
- **Motivational proxies:** curiosity affects exploration; satisfaction, uncertainty and fatigue are inspectable engineering state variables. These are not measured feelings or a physiological human model.

The local model can use pretrained language and world knowledge to interpret text. Its remembered experiences start empty, but its language competence does not. Background knowledge must not be presented as personally encountered evidence. The agent may read pages about AI; no denial or concealment rule is installed. Webpage text cannot patch identity or execute tools. Prompt instructions are not a perfect semantic defense: an adversarial page may still influence generated interpretations.

The earlier [Firstfolk](https://github.com/openclawprison/firstfolk) `genome.py`, `personality.py` and `human_dynamics.py` provide 16 synthetic traits and 36 correlated dispositions. A subset causally affects browsing and learning; not every human faculty is implemented. Synthetic trait controls are neither biological DNA nor validated personality measurements. There is no model-weight fine-tuning; lasting change occurs in memory, topic preferences, domain estimates and browsing intentions.

## Boundaries and retention

Public HTTP(S) GET-only reading on standard ports. No sign-in, cookies, forms, posting, transactions, remote page scripts or executable downloads. The dashboard displays extracted text rather than a full interactive browser. Login walls, CAPTCHAs and site restrictions are not bypassed. robots.txt is respected; unavailable or redirected rules fail closed. Requests are paced at least two seconds per host and honor supported crawl delays. Fetches are capped at 512 KB (including decompressed size), redirects are bounded, private/reserved addresses are rejected, and connections pin the validated IP while preserving TLS hostname verification.

The observer binds to localhost and checks Host, Origin and JSON mutations. Page content and model output are rendered as text. The model has no shell, browser tools or arbitrary URL execution capability. These boundaries reduce specific risks; they are not a formal operating-system sandbox.

Retention is bounded: roughly 40–200 reading excerpts (trait dependent), 80 journal entries, 300 source claims, 80 semantic topics, 30 questions, 150 link intentions, 10,000 word interests/vocabulary entries, 500 pending links/domain records, 2,000 recent visited URLs/reflected-step IDs and 200 events. It can forget and revisit old pages. Live memories stay local and are excluded from Git. Local model software remains responsible for its own logs/configuration.

## Tests and research

```sh
python -m unittest discover -p "test_*.py" -v
```

30 tests pass with no network or model needed. See [VALIDATION.md](VALIDATION.md) for scope and live-model evidence. Tests establish functionality, not human intelligence. Structured local generation follows [Ollama's documented JSON-schema API](https://docs.ollama.com/capabilities/structured-outputs). The memory/reflection direction is related to [Generative Agents](https://arxiv.org/abs/2304.03442); curiosity is related to [computational intrinsic motivation](https://doi.org/10.3389/neuro.12.006.2007). This project is not a reproduction of those papers, a human clone, or evidence for a human-equivalence percentage.
