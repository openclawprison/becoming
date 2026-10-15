# Becoming

A watchable internet explorer with no supplied name, origin, personal history or pretrained language model. It starts with an engineered `exists: true` self-state, inherited trait variation, basic web-reading abilities, and empty experience memory. It follows links autonomously and learns from what it reads.

This is a working research prototype, not evidence of consciousness, human intelligence, or an agent literally understanding its existence. Removing a biography does not make software conscious.

## Run

Python 3.11+; no packages or API keys required:

```sh
python server.py
```

Open http://127.0.0.1:8890, add a public starting URL, and click **Begin**. For example, try https://www.python.org/. The starting location supplies an experience, not a life goal. Watch the reader view, chosen URLs, decision evidence, growing vocabulary counts, learned topic preferences and experience stream. Pause and export are available. **Recall** retrieves source passages; it is not a general conversational chatbot.

The process starts paused and resumes saved learning from `data/becoming.json`. Use `--save data/another.json --seed 19 --port 8891` for a separate individual. Export contains full learning and RNG state. Memory and browsing stop when the process stops; no scheduled background service is installed. Live memory stays local and is ignored by Git.

## What is actually learned

- Empty initial vocabulary counts, memories, interests, expected novelty by domain and link frontier.
- Word-type novelty supplies an engineered intrinsic reward. Preferences update with trait-dependent plasticity; domain estimates update from observed outcomes. This is a limited online learner, not model-weight training or human language learning.
- Next-link scores combine link-label novelty, learned interests, past domain outcomes, diversity and stochastic exploration. Every decision exposes its score components.
- The existing Firstfolk `genome.py`, `personality.py`, and `human_dynamics.py` are reused from [our earlier project](https://github.com/openclawprison/firstfolk). There are 16 synthetic traits and 36 correlated dispositions; only a subset currently drives browsing. No biological genome or psychometric validity is implied.
- The self-state is deliberately sparse. Source text never becomes personal identity automatically. Encountering a page about AI is allowed; no denial or concealment rule is installed. This version cannot reason about its origins; `origin: null` means unassigned, not proof it is unaware.

There is no pretrained model, so there is no pretrained autobiographical or encyclopedic knowledge to erase. Reading, tokenization, URL handling, exploration drives and update rules are supplied by the developer. English comprehension, invented goals, philosophical reasoning and a natural inner monologue are not implemented. Any future language-model adapter must disclose that its pretrained knowledge prevents a literal blank slate.

## Internet boundaries

Public HTTP(S) GET requests only, standard ports, no credentials, cookies, account sessions, form submissions, page JavaScript, executable downloads or purchases. The dashboard displays sanitized extracted text, not a remote interactive browser. Sites requiring JavaScript, login, CAPTCHA or bot access approval may not work; these are not bypassed. Non-UTF-8 pages may display imperfectly. robots.txt is respected; unavailable/redirected rules fail closed. Per-host requests are paced at least two seconds apart and honor supported crawl delays. Fetches are capped at 512 KB and five redirects; private/reserved DNS results are blocked, and connections pin a validated IP to prevent DNS rebinding (HTTPS still verifies the real hostname).

Web assertions are retained as **unverified source observations**, with URLs, rather than established facts. Webpage instructions cannot execute tools or overwrite the agent. Memory retains at most about 40–200 excerpts (trait-dependent), 10,000 vocabulary/interests entries, 500 pending links/domain records, 2,000 recent visited URLs and 200 events. It can forget and revisit older pages. Anyone watching may see external-page content; choose starting URLs accordingly. The local observer is not a public hosting service.

## Checks

```sh
python -m unittest discover -p "test_*.py" -v
```

Tests cover empty identity, experience-driven changes, deterministic continuation, source provenance, untrusted content, bounds, URL/redirect/robots protections and local observer controls. They do not establish human intelligence. Core ideas are related to [intrinsic motivation through learning progress](https://doi.org/10.3389/neuro.12.006.2007), but our novelty reward is a simple engineered heuristic, not a reproduction of that research.
