# Brief: generating Black Ops II emblems automatically

**I want your best thinking on an architecture, not a summary of mine.** The
directions in section 9 exist so you don't waste time rediscovering the obvious
ones. They are a floor, not a menu. If the right answer is a framing nobody here
has considered, that is the answer I want.

**You have real data with this brief.** Section 1 says what's in the folder. Use
it — several of the open questions in section 8 can be answered in an afternoon
with what's already there, and I would rather you answer two of them than
speculate about all six.

---

## 1. What's in the folder

| item | what it is |
|---|---|
| `bo2_shapes_by_id/` | **The complete shape vocabulary.** 261 PNGs named `<id>_<category>_<name>.png`, plus `shapes.csv`. These are the only shapes the game can draw. |
| Loose `.png` / `.jpg` / `.webp` files | **Screenshots of real emblems** made by skilled players in-game. Batman, Freddy Krueger, Ken Kaneki, the Exorcist, FaZe Reaper, a wolf eye, and others. **These define the quality bar.** Look at them before anything else. |
| Folders (`batman`, `watchdogs`, `Faze`, `Kaufmo`, `bluespace`, …) | **Real `.emblem` files** for Plutonium (BO2 on PC). Actual layer data, not pictures. This is ground truth. |
| This file | The brief. |

### About the shape library

Every PNG is a white/alpha glyph. The game tints it with the layer's colour at
render time, so **what matters about a shape is its silhouette**, not its tone.
A shape's usefulness is often one edge of it, not the whole form.

| category | count | what it is |
|---|---|---|
| `tools` | 61 | the drawing kit — circles, half-circles, triangles, squares, hearts, blobs, `Mane`, `Tongue`, `Flag Breeze`, `Paint Splash`, `Swoop` |
| `emblems` | 106 | **finished pictorial artwork** — awards, skulls, animals, people, objects |
| `gear` | 39 | weapon silhouettes |
| `type` | 36 | A–Z, 0–9 |
| `ranks` | 19 | military insignia |

⚠️ **Two IDs are known-bad.** `057` and `096` are **the same image** — both were
mapped to "Interruption" upstream — and the shape **"Hail Mary" is missing from
the set entirely** because no ID points at it. So the folder has 261 files but
only 260 distinct shapes. One of `057`/`096` is very likely Hail Mary.

This cannot be resolved without checking in-game which shape each ID draws.
**Treat 57 and 96 as untrusted.** It matters more than it looks: a wrong ID means
a wrong render, which silently teaches a model an incorrect shape↔ID mapping with
no error ever surfacing.

### About the `.emblem` files

These come from Plutonium, the BO2 PC private server, which stores emblems at
`%localappdata%\Plutonium\storage\t6\players`. **Verify their layout before
trusting any parse** — I have not confirmed it:

- If a file is **exactly 1408 bytes**, it is the raw struct in section 3.
- If it is larger, there is a header or wrapper; locate the 1408-byte payload.
- Byte order may be either — detect it, don't assume (see section 3).

Parsing, once the payload offset is known:

```python
import struct

def parse(body, order="<"):          # order: "<" little, ">" big
    layers = []
    for i in range(32):
        rec = body[i*44:(i+1)*44]
        shape = struct.unpack(order + "H", rec[0:2])[0]
        if shape == 65535:           # empty layer
            continue
        r, g, b, a, x, y, sx, sy, rot = struct.unpack(order + "9f", rec[4:40])
        layers.append(dict(index=i, shape=shape, r=r, g=g, b=b, a=a,
                           x=x, y=y, sx=sx, sy=sy, rot=rot,
                           outlined=bool(rec[40]), flipped=bool(rec[41])))
    return layers
```

Sanity check the byte order by seeing which one puts every colour in 0..1 and
every shape ID under ~300. The wrong order produces floats around 1e30.

---

## 2. The goal

Given a text prompt ("Jesus Christ") **or** an uploaded image, produce a valid
BO2 emblem a skilled human would be impressed by, and write it to a real account
through an existing network proxy.

The mechanical half is solved. The hard half is **making something good**.

Two framings worth exploring, and they may need different architectures:

- **Interpretation** — "make me a Jesus Christ emblem." No reference image. The
  system decides what it should look like, then builds it.
- **Reproduction** — here is an image, reproduce it as faithfully as 32 layers
  allow, understanding the subject well enough to know what to keep and what to
  throw away.

---

## 3. The format (exact, verified)

An emblem is **1408 bytes**. Not an image — a display list. The game receives
instructions and renders them with its own textures.

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

Semantics, confirmed against the live game:

- **R,G,B,A** — 0.0 to 1.0.
- **posX, posY** — fraction of the canvas from centre; `0.5` reaches the edge.
  Pixel offset = `pos × canvas_size`. **+Y is DOWN.**
- **scaleX, scaleY** — *exponents*. True scale is `2^value`. `0` → fills the
  canvas, `-1` → half. Always positive; mirroring is the `flipped` flag, never a
  negative scale.
- **rotation** — degrees, clockwise-positive.
- **outlined** — draw only a thin constant-width edge stroke instead of a filled
  glyph. This is how line work is done.
- **Layer order** — index 0 is furthest BACK, 31 is frontmost.

Byte order follows the console that wrote it: PS3 is big-endian PowerPC, PC and
the PS4/PS5 ports are little-endian x86.

`shapeId` is a uint16, so **261–65535 is undocumented**. Nobody has probed it.

---

## 4. What already exists

- **A renderer** (Python/PIL): 1408 bytes → PNG, calibrated against the live game
  at ~0.95 registered pixel correlation. Slow, one emblem at a time.
- **The 261 shape PNGs**, ID-mapped (with the caveat in section 1).
- **A proxy** that captures emblems off the wire from any player you look at, and
  injects a chosen emblem into your own editor. A working **data collection
  pipeline** and a working **delivery mechanism**.

**What does not exist:** a writer (layers → 1408 bytes; trivial, hours), a fast
or differentiable renderer, and all of the generation intelligence.

---

## 5. Prior art — read this before designing anything

**Direction C in section 9 is already built.** Study it before proposing it.

### `505e06b2/Black-Ops-2-Emblem-Editor`
Browser re-implementation of the BO2 editor. All 261 shapes, 32 layers, full
transform controls. Its share format is `base64url(zlib.deflate(JSON))` —
verified decodable:

```json
{"playername": "...", "playerclantag": "...", "playerbg": "...",
 "stack": [{"name": "Full Circle", "x": 150, "y": 150, "rotate": 0,
            "hue": 0, "saturation": 0, "brightness": 1, "alpha": 1,
            "scalex": 1.275, "scaley": 1.275}, ...]}
```

Differences from the game binary — all mechanically convertible, since the
complete name↔ID map exists:

| | web editor | game binary |
|---|---|---|
| shape | by **name** | by **uint16 ID** |
| colour | HSB | RGB float |
| position | integer px, 300×300 canvas | fraction of canvas |
| scale | **linear** multiplier | **exponent**, `2^v` |
| outlined / flipped | **absent** | present |

The missing `outlined`/`flipped` matters — the web format **cannot express
outline layers**, one of the main expert techniques. Web → game is lossless;
game → web loses them.

### `ogarsan/Black-Ops-2-Emblem-Master`
A fork adding an LLM agent that composes emblems via tool calls — `add_layer`,
`move_layer`, `update_layer`, `get_emblem_state`, `get_free_layers`, `exec` —
**including a screenshot-based self-review step**. So "LLM + tools + vision
critique" exists and is testable today.

The best idea in its system prompt is a strategy ordering worth taking seriously:

> **Search the catalog before composing.** The `emblems` (106), `gear` (39) and
> `ranks` (19) categories are *finished artwork*, not primitives — skulls,
> animals, weapons, people. "A single prefab often beats 10 hand-placed
> primitives." For a skull, use a skull prefab rather than rebuilding one from
> circles.

That reframes the problem. It is not always "approximate an image with geometry."
Often it is "find the prefab that is already 80% of the subject, then compose
around it."

**Evaluate this fork empirically before proposing anything.** Run it, give it
hard prompts, compare against the reference screenshots. If it already gets
close, this is a tuning problem, not an architecture problem. If it plateaus at
"recognisable but crude" — the predicted outcome — then *characterising exactly
how it fails* is the most valuable input to whatever replaces it.

---

## 6. The quality bar

The reference screenshots in the folder were made **by humans, in-game, with a
thumbstick**, inside exactly these constraints. The bar is provably reachable
within the format — this is not a question of whether 32 layers is enough. It is
a question of whether we can find what a skilled human finds.

Look closely at the photorealistic ones. They read as photographs. They are 32
tinted silhouettes.

---

## 7. Techniques the experts use

Reverse-engineered from the references. This is craft knowledge, and it is the
part an optimiser will not stumble onto by itself:

1. **Large shapes clipped by the frame.** Scale a shape past the canvas and only
   a sliver is visible — a long, clean arc. Many of the smooth curves and
   gradient edges in the references are *the edges of oversized shapes*, not
   shapes. A layer is closer to a brush stroke than a sticker.
2. **Negative space carving.** A background-coloured shape on top cuts into what
   is underneath. Batman's ears and jawline are subtraction.
3. **Alpha stacking.** Several translucent copies, slightly offset, build soft
   shading on faces.
4. **Outline mode** for constant-width line work.
5. **Shapes chosen for one edge**, with the rest pushed off-canvas or hidden
   behind a later layer.

⚠️ **The clamps bound technique #1 far more than it first appears.** BO2 limits
both scale and off-canvas position. The web editor (built by people who studied
the game closely) enforces:

- canvas **300×300 px**; position valid range **−300..300**, outside values
  *rejected*, not clipped — about one canvas-width of overhang, no more
- scale clamped to **±5** on its linear multiplier, where "1.0 ≈ half the canvas,
  2.0 ≈ fills the canvas", default 1.15
- rotation 0..360

If that maps onto the game's exponent as it appears to, the largest usable shape
is on the order of **~2.5× the canvas**, not the enormous multiples one might
assume. Technique #1 is real but operates over a tight range.

**Treat those numbers as the editor's model of the game, not verified game
behaviour** — and note that **the `.emblem` files in this folder can settle it
directly** (section 8, question 1).

---

## 8. Open empirical questions

Several are now answerable immediately with the included data.

1. **What are the real clamps?** ✅ *Runnable now.* Parse the `.emblem` files and
   histogram `scaleX/scaleY` and `posX/posY`. Observed extremes bound the real
   limits, and pin the mapping between the editor's linear scale and the game's
   `2^v`. **Do this before designing any search space** — wrong bounds poison
   everything downstream.
2. **What does expert technique look like statistically?** ✅ *Runnable now.* How
   many layers do good emblems actually use? How many are subtractive
   (background-coloured, drawn over)? How often is `outlined` set? Few large
   layers or many small ones? How much alpha stacking? This is the prior worth
   having, and nobody has measured it.
3. **Is the clamp enforced by the editor or the renderer?** The editor stops you
   dragging past a limit; injected data never passes through the editor. If the
   clamp is UI-only, generated emblems could use ranges no hand-made emblem can
   reach — moves humans physically cannot perform. One test emblem settles it.
4. **Which of `057`/`096` is Hail Mary?** Requires in-game checking.
5. **What do shape IDs 261–65535 do?** Unknown. Possibly other textures.
   Expect crashes.
6. **Does the game validate the blob at all,** or will it render any well-formed
   struct? Determines how far the format can be pushed.

---

## 9. Failure modes to design against

These are the specific ways this project is expected to fail. A proposal that
doesn't address them isn't finished.

- **The infinite critique loop.** "Render → vision model says move it left → move
  it → now something else is wrong → forever." Any iterative loop needs an
  explicit convergence criterion, bounded iterations, monotonic
  accept-if-improved semantics, and oscillation detection. This is the failure I
  most expect.
- **The wrong objective.** Possibly the deepest issue. Pixel-matching a photo is
  probably *not* the goal — the reference emblems are bold graphic
  *interpretations*, not reproductions. Optimising L2 or even LPIPS against a
  photo may converge on something faithful and ugly while the references are
  unfaithful and great. **What number goes up when an emblem gets better?** I do
  not think anyone has answered this, and I consider it the crux.
- **The recognisable-but-ugly plateau.** Naive Geometrize-style fitting reliably
  produces something identifiable that nobody would want on their account.
  Getting off that plateau is the whole project.
- **Distribution mismatch.** Uniformly sampled synthetic data looks nothing like
  real emblems; a model trained on it won't generalise.
- **Discrete + continuous.** Shape ID is discrete (261 options), everything else
  continuous. Gradients don't flow through the choice of shape.
- **Combinatorial depth.** 32 layers × 261 shapes × 9 continuous parameters,
  where later layers occlude earlier ones — layers are not independent, so greedy
  per-layer fitting is provably suboptimal.

---

## 10. Candidate directions

**Non-exhaustive on purpose. Argue with these.**

**A — Pure optimisation.** Rewrite the renderer in PyTorch with soft alpha
compositing so position/scale/rotation/colour are differentiable. Gradient
descent on continuous parameters; simulated annealing or swap-and-test on
discrete shape IDs. Known technique (cf. differentiable vector graphics). No
training. Expected to reach "recognisable, decent" and stall short of the
references.

**B — Learned proposer.** Train an image→layers model. The key advantage: **the
renderer manufactures unlimited labelled data for free** — sample layer stacks,
render them, and you have `(image, exact parameters)` pairs needing no
annotation. The `.emblem` files are then the *prior* that makes synthetic
sampling realistic, rather than the training set itself. Model proposes,
optimiser refines.

*On data volume:* there is no public emblem corpus — the format-spec repo has
documentation only, and the two editors ship 5 examples between them. Real data
must be collected: captured off the wire with the proxy, harvested from
Plutonium community shares, or decoded from web-editor share codes. Assume
hundreds are obtainable with effort, not thousands cheaply. Plan for that.

**C — LLM as artist, with tools. ⚠️ ALREADY BUILT — see section 5.** Do not
re-propose as new work. Either measure where it plateaus and improve it
specifically, or explain what it structurally cannot do.

**C2 — Prefab-first composition.** 164 of the 261 shapes are finished artwork,
not geometry. Retrieval over that set — "which prefab is closest to my subject?"
— may beat any amount of primitive fitting for subjects the catalog covers, and
fail completely for those it doesn't. Worth knowing which subjects fall on which
side of that line before committing.

**D — Idiom DSL.** LLMs are bad at raw coordinates and good at composition. So
don't ask for coordinates. Define primitives — `soft_shadow(under=X, offset,
strength)`, `gradient_wedge(direction)`, `carve(region)`, `stroke(path)` — each
compiling to 2–4 layers using known expert technique. The model composes idioms;
a compiler emits bytes. Converts an impossible numeric task into a solvable
symbolic one, and encodes section 7 explicitly instead of hoping it is
rediscovered. **The `.emblem` files are the place to mine the idiom vocabulary
from** — find recurring layer motifs across real emblems.

**E — Retrieval and recombination.** Find structurally similar emblems in a
corpus and adapt their layer skeletons. Steal the technique, replace the subject.

**F — Two-stage target.** Don't fit to a photo. First have an image model
produce a *flat-colour, bold-graphic, 4-to-6-tone stylisation* — achievable in 32
layers by construction — then fit to that. Attacks the "wrong objective" problem
by making the target reachable before optimisation begins.

Combinations are likely better than any single one. D+F look stronger to me than
either alone — but I may be wrong, and I would rather you tell me why than agree.

---

## 11. What I want back

1. **A recommended architecture**, with reasoning — including why you rejected
   the alternatives.
2. **A staged plan**, each stage independently testable, nothing wasted if the
   next stage is abandoned.
3. **The objective function.** Concretely: what number goes up when the emblem
   gets better? The least solved part.
4. **The convergence design** for any iterative loop — termination, oscillation
   detection, what "done" means.
5. **Findings from the included data.** At minimum questions 1 and 2 in section
   8. Real measured numbers beat any amount of reasoning about what the limits
   might be.
6. **The first three experiments to run**, ordered, with what each would tell us
   and what result would change the plan.
7. **An honest effort estimate**, and where you expect it to fall short of the
   references.

If you think the framing here is wrong — that the objective is misconceived, that
the constraint is not where I claim, that there is a shortcut nobody has taken —
say so directly and make that the answer.

---

## 12. Ground rules

- Single-player cosmetic tool, personal account, own hardware.
- Only shapes the account has unlocked can be permanently saved by the game. The
  `tools` category is largely available early and is the safe palette.
  Generating rather than copying is an advantage: you control the palette.
- Delivery is solved. Don't spend effort there.
- Python; a GPU is available if the design needs one.
