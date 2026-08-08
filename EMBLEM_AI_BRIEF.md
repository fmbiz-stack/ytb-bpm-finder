# Brief: generating Black Ops II emblems automatically

**To whoever is reading this: I want your best thinking on an architecture, not a
summary of mine.** The directions in section 8 are there so you don't waste time
rediscovering the obvious ones. They are a floor, not a menu. If the right answer
is a framing nobody here has considered, that is the answer I want.

Attach alongside this document the reference emblem screenshots (Wolverine,
Slenderman, Batman, Pikachu, Pepsi, the photorealistic soldier). They define the
quality bar and they are hard to believe without seeing them.

---

## 1. The goal

Given either a text prompt ("Jesus Christ") or an uploaded image, produce a valid
Black Ops II emblem that a skilled human would be impressed by — then write it to
a real account through an existing network proxy.

The mechanical half is solved. The hard half is **making something good**.

---

## 2. The format (exact, verified)

An emblem is **1408 bytes**. Not an image — a display list. The game receives
instructions and renders them itself with its own textures.

```
32 layer records × 44 bytes each

offset  size  field
0       2     shapeId    uint16   (65535 = empty layer)
2       2     padding
4       36    9 × float32:  R, G, B, A, posX, posY, scaleX, scaleY, rotation
40      1     outlined   bool
41      1     flipped    bool
42      2     padding
```

Semantics, all confirmed against the live game:

- **R,G,B,A** — 0.0 to 1.0.
- **posX, posY** — fraction of the canvas from centre. `0.5` reaches the edge.
  Pixel offset = `pos × canvas_size`. **+Y is DOWN.**
- **scaleX, scaleY** — *exponents*. True scale is `2^value`. `0` → the shape
  fills the whole canvas. `-1` → half. `+3` → 8× the canvas. Always positive;
  mirroring is the separate `flipped` flag, never a negative scale.
- **rotation** — degrees, clockwise-positive.
- **outlined** — draw only a thin constant-width edge stroke instead of a filled
  glyph. This is how line work is done.
- **Layer order** — index 0 is furthest BACK, index 31 is frontmost.

Byte order depends on the console that wrote it (PS3 is big-endian PowerPC;
PC and the PS4/PS5 ports are little-endian x86). Detected per blob.

### The shape vocabulary

**261 shapes, IDs 0–260. All of them identified, all with a reference PNG on
disk.** Five categories:

| category | count | what it is |
|---|---|---|
| `tools` | 61 | the real drawing kit — circles, half-circles, triangles, squares, hearts, blobs, `Mane`, `Tongue`, `Flag Breeze`, `Paint Splash`, `Swoop` |
| `type` | 36 | A–Z, 0–9 |
| `emblems` | 106 | award icons |
| `gear` | 39 | weapon qualification icons |
| `ranks` | 19 | military rank insignia |

Every shape is a white/alpha glyph, tinted at render time by the layer's colour.
So a shape is really **a silhouette**, and what matters about it is the *shape of
its edges*, not what it depicts.

`shapeId` is a uint16, so **261–65535 is undocumented territory**. Nobody has
probed it. It may index other game textures. Unknown, possibly crashy, possibly
interesting.

---

## 3. What already exists

- **A renderer** (Python/PIL): 1408 bytes → PNG. Calibrated against the live game
  at roughly 0.95 registered pixel correlation. Slow — one emblem at a time.
- **All 261 shape PNGs**, named and ID-mapped.
- **A proxy** that captures emblems off the wire from any player you look at, and
  injects a chosen emblem into your own editor. So: a working **data collection
  pipeline** and a working **delivery mechanism**.
- A test suite, and a documented byte layout.

**What does not exist:** a writer (layers → 1408 bytes; trivial, hours), a fast or
differentiable renderer, and all of the generation intelligence.

---

## 3b. Prior art — read this before designing anything

Two existing projects matter. **Direction C below is already built.** Study it
before proposing it.

### `505e06b2/Black-Ops-2-Emblem-Editor`
A browser re-implementation of the BO2 emblem editor. All 261 shapes, 32 layers,
full transform controls. Its share format is:

```
base64url( zlib.deflate( JSON.stringify(emblem) ) )
```

Verified decodable. The JSON is:

```json
{"playername": "...", "playerclantag": "...", "playerbg": "...",
 "stack": [{"name": "Full Circle", "x": 150, "y": 150, "rotate": 0,
            "hue": 0, "saturation": 0, "brightness": 1, "alpha": 1,
            "scalex": 1.275, "scaley": 1.275}, ...]}
```

Note the differences from the game's binary format — all mechanically
convertible, since we have the complete name↔ID map for all 261 shapes:

| | web editor | game binary |
|---|---|---|
| shape | by **name** | by **uint16 ID** |
| colour | HSB | RGB float |
| position | integer px on a 300×300 canvas | fraction of canvas |
| scale | **linear** multiplier | **exponent**, true scale = `2^v` |
| outlined / flipped | **absent** | present |

The missing `outlined` / `flipped` matters: the web format **cannot express
outline layers**, which is one of the main expert techniques. Web → game
conversion is lossless (those default to false); game → web loses them.

### `ogarsan/Black-Ops-2-Emblem-Master`
A fork adding an LLM agent that composes emblems by tool calls — `add_layer`,
`move_layer`, `update_layer`, `get_emblem_state`, `get_free_layers`, `exec`, etc.
**It already includes a screenshot-based self-review step.** So the
"LLM + tools + vision critique" architecture exists and is testable today.

The single most valuable idea in its system prompt is a strategy ordering nobody
here had considered:

> **Search the catalog before composing.** The `emblems` (106), `gear` (39) and
> `ranks` (19) categories are *finished artwork*, not primitives — skulls,
> animals, weapons, people. "A single prefab often beats 10 hand-placed
> primitives." For a skull, use a skull prefab rather than rebuilding one from
> circles.

That reframes the problem: it is not always "approximate an image with geometry."
Often it is "find the prefab that already is 80% of the subject, then compose
around it." Any serious proposal should decide where prefab-reuse sits relative
to primitive-composition.

**Before proposing anything, evaluate this fork empirically.** Run it, give it
hard prompts, and see where it actually lands relative to the reference emblems.
If it already gets close, the project is tuning, not architecture. If it plateaus
at "recognisable but crude" — the predicted outcome — then *characterising exactly
how it fails* is the most valuable input to whatever replaces it.

---

## 4. The quality bar, and why it's the interesting part

The reference emblems were made **by humans, in-game, with a thumbstick**, inside
exactly these constraints. So the bar is provably reachable within the format —
this is not a question of whether 32 layers is enough. It is a question of whether
we can find what a skilled human finds.

Look closely at the soldier emblem in particular. It reads as photographic. It is
32 tinted silhouettes.

---

## 5. Techniques the experts use

Reverse-engineered from the reference images. This is craft knowledge and it is
the part an optimizer will not stumble onto by itself:

1. **Enormous shapes clipped by the frame.** Scale a circle far past the canvas
   and only a sliver is visible — a long, clean, subtle arc. Most of the smooth
   curves and gradient edges in the references are *the edges of huge shapes*, not
   shapes. A layer is closer to a brush stroke than a sticker.
2. **Negative space carving.** Place a background-coloured shape on top to cut
   into what's underneath. Batman's ears and jawline are subtraction.
3. **Alpha stacking.** Several translucent copies, slightly offset, build the soft
   shading on faces.
4. **Outline mode** for constant-width line work.
5. **Shapes chosen for one edge**, with the rest of the shape pushed off-canvas or
   hidden behind a later layer.

⚠️ **Important correction, and it cuts technique #1 down to size.** BO2 clamps
both scale and off-canvas position — past a limit the shape stops scaling, and a
layer cannot be pushed arbitrarily far out. The web editor (built by people who
studied the game closely) enforces:

- **canvas 300×300 px**; position valid range **−300..300**, values outside
  *rejected*, not clipped — so roughly one canvas-width of overhang, no more
- **scale clamped to ±5** on its linear multiplier, where "1.0 ≈ half the canvas,
  2.0 ≈ fills the canvas", default 1.15
- rotation 0..360

If that linear scale maps onto the game's exponent as it appears to, the maximum
usable shape is on the order of **~2.5× the canvas — not the 30× I implied
earlier.** Technique #1 is real, but it operates over a much tighter range: the
useful "giant shape" is a couple of canvas-widths, not an enormous one.

**Treat those numbers as the editor's model of the game, not as verified game
behaviour.** They are the best starting hypothesis available and they must be
confirmed against captured data — see section 7. A search space built on wrong
bounds is poisoned from the start.

---

## 6. Failure modes to design against

These are the specific ways this project is expected to fail. A proposal that
doesn't address them isn't finished.

- **The infinite critique loop.** "Render → vision model says move it left → move
  it → now something else is wrong → repeat forever." Oscillation without
  convergence. Any iterative loop needs an explicit convergence criterion, a
  bounded iteration count, monotonic accept-if-improved semantics, and oscillation
  detection.
- **The wrong objective.** This may be the deepest issue. Pixel-matching a
  photograph is probably *not* the goal. The Wolverine emblem is not a picture of
  Wolverine — it is a bold graphic *interpretation*. Optimising L2 or even LPIPS
  against a photo may converge to something faithful and ugly, while the
  references are unfaithful and great. What is the actual objective function for
  "good emblem"? I don't think anyone has answered this.
- **The recognisable-but-ugly plateau.** Naive shape fitting (Geometrize-style)
  reliably produces something you can identify and nobody would want on their
  account. Getting off that plateau is the whole project.
- **Distribution mismatch.** Synthetic training data sampled uniformly looks
  nothing like real emblems, and a model trained on it will not generalise to real
  targets.
- **Discrete + continuous.** Shape ID is discrete (261 options), everything else
  is continuous. Mixed optimisation is awkward; gradients don't flow through the
  choice of shape.
- **Combinatorial depth.** 32 layers × 261 shapes × 9 continuous parameters,
  where later layers occlude earlier ones — so layers are not independent and
  greedy per-layer fitting is provably suboptimal.

---

## 7. Open empirical questions

All of these are answerable with the tools that already exist. Cheap to run,
and several of them constrain the design.

1. **What are the real scale and position clamps?** Partially answered — the web
   editor uses ±5 linear scale and ±300 px position (section 5). Confirm against
   the game by capturing ~200 expert emblems and histogramming `scaleX/scaleY`
   and `posX/posY`, and pin down the exact mapping between the editor's linear
   scale and the game's `2^v` exponent. Do this before designing any search space.
2. **Is the clamp enforced by the editor or by the renderer?** The editor stops
   you dragging past a limit. Injected data never passes through the editor. If
   the clamp is UI-only, generated emblems could use parameter ranges no
   hand-made emblem can reach — moves humans literally cannot perform. If the
   renderer clamps too, no advantage. One test emblem settles it.
3. **What do shape IDs 261–65535 do?** Unknown. Possibly other textures.
4. **What does the expert parameter distribution actually look like?** How many
   layers are subtractive? How often is `outlined` used? Do experts use few large
   layers or many small ones? This is the prior worth having.
5. **Does the game validate the blob at all,** or will it render any
   well-formed struct? Affects how far the format can be pushed.

---

## 8. Candidate directions

**Non-exhaustive on purpose. Argue with these.**

**A — Pure optimisation.** Rewrite the renderer in PyTorch with soft alpha
compositing so position/scale/rotation/colour are differentiable. Gradient descent
on continuous parameters, simulated annealing or periodic swap-and-test on the
discrete shape IDs. Known technique (cf. differentiable vector graphics). No
training. Expected to reach "recognisable, decent" and stall short of the
references.

**B — Learned proposer.** Train an image→layers model. The killer advantage: **the
renderer manufactures unlimited labelled data for free** — sample layer stacks,
render them, and you have `(image, exact parameters)` pairs with zero annotation.
Real captured emblems are then the *prior* that makes synthetic sampling
realistic, rather than the training set itself. Model proposes a layout, optimiser
refines it. Serious ML project.

*On real data:* there is no public corpus of emblems. Searched — the format specs
repo has documentation only, and the two editors ship 5 example emblems between
them. Real data has to be collected: capture off the wire with the proxy, and/or
harvest share codes from the community (Plutonium forums share `.emblem` files
from `%localappdata%\Plutonium\storage\t6\players`, and the web editor's codes are
decodable per section 3b). Assume hundreds are obtainable with effort, not
thousands cheaply. Plan accordingly — this is the argument for treating real
emblems as a *prior* over synthetic sampling rather than as a training set.

**C — LLM as artist, with tools. ⚠️ ALREADY BUILT — see section 3b.** Plan the
composition, choose shapes by name, place them, render, review with vision,
correct. `ogarsan/Black-Ops-2-Emblem-Master` implements exactly this, screenshot
self-review included. Do not re-propose it as new work. Either measure where it
plateaus and improve it specifically, or explain what it structurally cannot do.
It is also the approach most exposed to failure mode #1, so if you build on it,
the convergence design *is* the contribution.

**C2 — Prefab-first composition.** Distinct enough from C to state separately.
164 of the 261 shapes are finished artwork (`emblems` + `gear` + `ranks`), not
geometry. Retrieval over that set — "which prefab is closest to my subject?" —
may beat any amount of primitive fitting for subjects the catalog happens to
cover, and fail completely for those it doesn't. Worth knowing which subjects
fall on which side of that line before committing to an architecture.

**D — Idiom DSL.** LLMs are bad at raw coordinates and good at composition. So
don't ask for coordinates. Define higher-level primitives — `soft_shadow(under=X,
offset, strength)`, `gradient_wedge(direction)`, `carve(region)`, `stroke(path)` —
each of which compiles down to 2–4 layers using known expert technique. The model
composes idioms; the compiler emits bytes. This converts an impossible numeric task
into a solvable symbolic one, and encodes section 5 explicitly rather than hoping
it's rediscovered.

**E — Retrieval and recombination.** With a corpus of captured expert emblems,
find structurally similar ones and adapt their layer skeletons. Steal the
technique, replace the subject.

**F — Two-stage target.** Don't fit to a photo. First have an image model produce
a *flat-colour, bold-graphic, 4-to-6-tone stylisation* — something that is
achievable in 32 layers by construction — then fit to that. This attacks the
"wrong objective" problem directly by making the target reachable before
optimisation begins.

Combinations are likely better than any single one. D+F together, for instance,
look stronger to me than either alone — but I may be wrong, and I would rather you
tell me why than agree.

---

## 9. What I want back

1. **A recommended architecture**, with the reasoning — including why you rejected
   the alternatives.
2. **A staged plan**, where each stage produces something testable on its own and
   nothing is wasted if the next stage is abandoned.
3. **The objective function.** Concretely: what number goes up when the emblem
   gets better? I consider this the crux and the least solved part.
4. **The convergence design** for any iterative loop — how it terminates, how
   oscillation is detected, what "done" means.
5. **The first three experiments to run**, ordered, with what each one would tell
   us and what result would change the plan.
6. **An honest effort estimate** and where you expect it to fall short of the
   references.

If you think the framing in this document is wrong — that the objective is
misconceived, that the constraint is not where I claim, that there is a shortcut
nobody has taken — say so directly and make that the answer.

---

## 10. Ground rules

- Single-player cosmetic tool, personal account, own hardware.
- Only shapes the account has unlocked can be saved permanently by the game — the
  `tools` category is largely available early and is the safe palette. Generating
  rather than copying is an advantage here: you control the palette.
- Delivery is a solved problem. Don't spend effort there.
- Python, and a GPU is available if the design needs one.
