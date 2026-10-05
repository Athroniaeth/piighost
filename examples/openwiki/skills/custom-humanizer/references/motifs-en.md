# AI writing tells in English

**Strength**:
- **S** (strong): one occurrence is enough;
- **C** (cluster): counts only when repeated or combined;
- **X** (context): counts only when the genre makes it hollow.

Every "after" below uses only information from the "before". When nothing is left to keep, delete.

## 1. Words and stock phrases

| Tell | Strength | Before → after | Don't flag when |
|---|---|---|---|
| **AI vocabulary, tier 1**: *delve, tapestry, testament, landscape* (figurative), *realm, embark, unlock the power, elevate, pave the way, game-changer, cornerstone, nestled, vibrant* | S | "Our tool unlocks the power of your data." → "Our tool exports your data to CSV." (only if the source says so; otherwise cut) | Literal sense ("the landscape photo") |
| **Tier 2**: *robust, seamless, comprehensive, crucial, pivotal, leverage, utilize, foster, streamline, enhance, empower, holistic* | C (2+ per paragraph) | "leverage a streamlined approach" → "use a simpler approach" | Precise technical meaning ("robust regression"); one isolated use |
| **Filler openers**: *In today's fast-paced world, In the ever-evolving landscape of, In an era where* | S | "In today's fast-paced market, we rebuilt checkout." → "We rebuilt checkout." | The context is real information |
| **Importance stamps**: *It's worth noting that, It's important to note, Notably, Importantly, Interestingly, and that matters* | S | "It's worth noting that the API is rate-limited." → "The API is rate-limited." | "Note:" before a real gotcha in docs |
| **Copula avoidance**: *serves as, stands as, functions as, boasts, features* (for *is* / *has*) | C | "The library serves as a wrapper." → "The library is a wrapper." | — |
| **-ing commentary tails**: *…, highlighting / underscoring / reflecting / ensuring…* | S | "We cut the timeout, ensuring a better experience." → "We cut the timeout." | The participle states a fact the source supports |
| **Vague attribution**: *experts say, studies show, many believe* | S | Keep the claim only with the source's actual reference; otherwise flag in **To confirm** | The text names the source |
| **Hedge stacking**: *could potentially, may in some cases arguably* | C | "could potentially help" → "could help" | Real, single uncertainty: keep it |
| **Corporate jargon**: *circle back, move the needle, low-hanging fruit, double-click on* | C | "Let's circle back on this." → "Let's discuss this again." | Internal register the author uses on purpose |
| **Chatbot residue**: *Great question!, I hope this helps, Certainly!, Let me know if you'd like…, As of my last update*; `oaicite`, `utm_source=chatgpt.com`, unfilled `[COMPANY]` | S | Delete | A real offer from the author in a message they sign ("happy to jump on a call"): keep it, shortened |
| **Signposted conclusion**: *Ultimately, In conclusion, The bottom line, At the end of the day* + a general moral | S | "At the end of the day, the dashboard reflects who we are." → delete | The conclusion adds a decision or a date |
| **Narrated candor**: *to be honest, the honest answer is, let me be clear, I won't sugarcoat it* | S | "To be honest, the migration is late." → "The migration is late." | Real disclosure (conflict of interest) |
| **Acknowledgement loop**: *You're asking about X. Here's…* | S | Answer directly | — |

## 2. Structures

| Tell | Strength | Before → after | Don't flag when |
|---|---|---|---|
| **Negative parallelism**: *It's not X, it's Y; not just X but Y; X isn't about A, it's about B*; tailing *"…, no guessing"* | S | "It's not a tool, it's a mindset." → delete, or state Y plainly if the source supports it | X is a real reader objection the text answers |
| **Staged opener / reveal**: *Here's the thing:, The catch?, The result?, What surprised me was* | S | "The result? Fewer bugs." → "There were fewer bugs." | FAQ; a genuine question to the reader |
| **Rule of three**: adjective triplets, three parallel clauses for rhythm | C | Synonyms: "clear, simple, and easy" → "simple". Three distinct claims: break the mould, keep the claims: "The tool is cheaper and more stable. It is also clearer." | Real enumeration (three steps, three files) |
| **Bold-label bullets**: "**Knowledge sharing:** reviews spread…" | C | "- **Speed:** builds take 3 min." → "- Builds take 3 min." | Reference docs (term then definition) |
| **One-line closers and aphorisms**: *And that changes everything. Simple as that.* | S | Delete | — |
| **Announcements**: *Let's dive in, Let's break it down, In this article we'll explore* | S | Delete | Docs where a short scope line helps the reader |
| **Whether opener**: *Whether you're a beginner or an expert, …* | S | Delete, or say who it is for | — |
| **Uniform rhythm**: 4+ sentences of the same length and shape | C | Merge related ideas, split overloaded ones, as the meaning requires | Instruction lists; the author's own even style |
| **Diff-anchored prose** in docs: *was added to replace the previous approach* | C | Describe the current state | Changelogs, commit messages, PR descriptions |

## 3. Formatting and punctuation

| Tell | Strength | Fix | Don't flag when |
|---|---|---|---|
| **Em dashes as default punctuation** (several per paragraph) | C | Replace most with commas, periods, colons or parentheses. Keep one where it reads best | One em dash in a page; the author's samples use them |
| Decorative bold, emoji bullets, emoji headings | C | Remove | Informal chat where the author uses them |
| Title Case Headings | X | Leave as is by default. Switch to sentence case only if the house style or the other headings use it | — |
| Excess structure: 3+ headings in under 300 words, 8+ bullets in under 200 words | C | Merge into prose or fewer sections | Reference material |

Curly quotes and the Oxford comma are **not** tells. Keep the source's convention.

## 4. Don't flag in English

- Passive voice in methods sections, incident reports and specs where the agent is unknown or irrelevant.
- Domain terms: *robust, framework, pipeline, ecosystem* (package ecosystems), *leverage* (finance).
- Short texts (under ~40 words): too little signal. Fix only strong tells.
- Even, plain prose by non-native writers or neurodivergent authors: uniformity alone proves nothing.
- Contractions, or their absence: follow the source.

## Full example

**Before**

> In today's rapidly evolving tech landscape, our team embarked on a journey to modernize the billing service. This wasn't just a migration — it was a complete reimagining of how we handle payments. By leveraging Kubernetes, we reduced deploy time from 25 minutes to 4, empowering engineers to ship faster. Ultimately, this initiative stands as a testament to our commitment to excellence.

**After**

> Our team modernized the billing service and moved it to Kubernetes. Deploys now take 4 minutes instead of 25.

**Report**

- **Changed**: filler opener, tier-1 vocabulary (*embarked on a journey, testament*), negative parallelism, *leveraging*, *-ing* tail, signposted conclusion.
- **Removed claims**: "complete reimagining of how we handle payments" and "engineers ship faster". Both are the source's claims with no facts behind them. Restore them as plain sentences if the author confirms them.
- **Meaning check**: 25 and 4 kept; "our team" kept; nothing added.
