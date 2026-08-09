#!/usr/bin/env python3
"""Export captured emblems into something you can hand to another model.

The toolkit stores each capture as a raw .bin (HTTP headers + the 1408-byte
emblem body), which is the valuable part but is unreadable on its own. This
turns a folder of captures into three things side by side:

    <name>.png    what the emblem looks like
    <name>.json   its 32 layers, decoded into named fields
    <name>.bin    the original bytes, untouched

Usage:
    python3 export_captures.py                     # find captures automatically
    python3 export_captures.py --saved <path>      # point at a saved/ folder
    python3 export_captures.py --out <path>        # where to write (default ./emblem_export)

Run it from the folder that contains bo2-emblem-toolkit/, or pass --toolkit.
"""
import argparse
import json
import os
import shutil
import sys


def find_toolkit(explicit=None):
    """Locate the bo2-emblem-toolkit checkout so we can import its renderer."""
    candidates = [explicit] if explicit else []
    here = os.path.dirname(os.path.abspath(__file__))
    candidates += [
        os.path.join(here, "bo2-emblem-toolkit"),
        here,
        os.getcwd(),
        os.path.join(os.getcwd(), "bo2-emblem-toolkit"),
    ]
    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "emblemtool")):
            return path
    return None


def find_saved(explicit=None):
    """Where the toolkit keeps captures, depending on how it was run."""
    if explicit:
        return explicit
    home = os.path.expanduser("~")
    candidates = [
        # packaged macOS .app
        os.path.join(home, "Library", "Application Support", "BO2EmblemToolkit", "saved"),
        # packaged Windows exe / portable install next to the binary
        os.path.join(os.environ.get("APPDATA", ""), "BO2EmblemToolkit", "saved"),
        # Linux
        os.path.join(home, ".local", "share", "BO2EmblemToolkit", "saved"),
        # run from source
        os.path.join(os.getcwd(), "bo2-emblem-toolkit", "saved"),
        os.path.join(os.getcwd(), "saved"),
    ]
    for path in candidates:
        if path and os.path.isdir(path):
            return path
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saved", help="path to the toolkit's saved/ folder")
    ap.add_argument("--toolkit", help="path to the bo2-emblem-toolkit checkout")
    ap.add_argument("--out", default="emblem_export", help="output folder")
    ap.add_argument("--size", type=int, default=512, help="rendered PNG size in px")
    args = ap.parse_args()

    toolkit = find_toolkit(args.toolkit)
    if not toolkit:
        sys.exit("Couldn't find bo2-emblem-toolkit/ (the folder containing emblemtool/).\n"
                 "Pass it with --toolkit /path/to/bo2-emblem-toolkit")
    sys.path.insert(0, toolkit)

    saved = find_saved(args.saved)
    if not saved:
        sys.exit("Couldn't find any captures.\n\n"
                 "They live in one of these, depending on how you ran the toolkit:\n"
                 "  macOS app     ~/Library/Application Support/BO2EmblemToolkit/saved\n"
                 "  from source   <toolkit folder>/saved\n"
                 "  Windows exe   next to the .exe, in saved\\\n\n"
                 "Point at it directly with --saved /path/to/saved")

    try:
        from emblemtool.shapes import render
        from emblemtool.shapes.shape_id_map import known_ids
    except ImportError as e:
        sys.exit(f"Couldn't import the toolkit's renderer ({e}).\n"
                 "Install its one dependency first:  pip3 install Pillow")

    os.makedirs(args.out, exist_ok=True)
    index, skipped = [], []

    for group in sorted(os.listdir(saved)):
        group_dir = os.path.join(saved, group)
        if not os.path.isdir(group_dir) or group.startswith("_"):
            continue  # _active is the armed-selection pseudo-group, not a capture

        meta = {}
        meta_path = os.path.join(group_dir, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)

        for filename in sorted(os.listdir(group_dir)):
            if not (filename.startswith("slot_") and filename.endswith(".bin")):
                continue
            slot = filename[len("slot_"):-len(".bin")]
            src = os.path.join(group_dir, filename)
            with open(src, "rb") as f:
                raw = f.read()

            body = render.strip_http(raw)
            order = render.detect_endianness(body)
            try:
                layers = render.parse_slot_bytes(raw)
            except Exception as e:
                skipped.append((f"{group}/{filename}", str(e)))
                continue

            label = (meta.get("labels", {}).get(slot) or "").strip()
            stem = f"{group}_slot{slot}" + (f"_{label.replace(os.sep, '-')}" if label else "")
            stem = "".join(c for c in stem if c.isalnum() or c in " ._-").strip()

            for layer in layers:
                layer["shape_name"] = known_ids.get(layer["shape"], "UNKNOWN")

            # The renderer scales a layer by materialising the whole bitmap at
            # 2^exponent x the output size. Real emblems reach exponent 6.0
            # (64x the canvas), which at a 512px output means a 32768px image -
            # PIL rejects it as a decompression bomb, and the sizes that do
            # squeak under the limit take minutes. So size the output from the
            # emblem's largest layer instead of finding out the hard way.
            #
            # These are the ambitious emblems, not the broken ones, so they must
            # never be dropped: a small thumbnail plus correct layer data beats
            # a hang. The .json below is the real deliverable either way.
            max_exp = max((max(l["sx"], l["sy"]) for l in layers), default=0.0)
            budget = 2048  # widest intermediate bitmap we're willing to build
            fits = int(budget / max(1.0, 2 ** max(0.0, max_exp)))
            png_size = max(32, min(args.size, fits)) if fits >= 32 else None

            png, render_error = None, ""
            if png_size:
                try:
                    png = render.render_file_png_bytes(src, size=png_size)
                except Exception as e:
                    png, render_error = None, f"{type(e).__name__}: {e}"
            else:
                render_error = (f"layer scale exponent {max_exp:.2f} "
                                f"({2 ** max_exp:.0f}x canvas) is too large to rasterise")

            record = {
                "source": f"{group}/{filename}",
                "label": label,
                "captured_at": meta.get("first_captured", ""),
                "byte_order": "little" if order == "<" else "big",
                "body_bytes": len(body),
                "layers_used": len(layers),
                "max_scale_exponent": max((max(l["sx"], l["sy"]) for l in layers), default=None),
                "png_rendered_at": png_size,
                "render_error": "" if png else render_error,
                "layers": layers,
            }

            with open(os.path.join(args.out, stem + ".json"), "w") as f:
                json.dump(record, f, indent=1)
            if png:
                with open(os.path.join(args.out, stem + ".png"), "wb") as f:
                    f.write(png)
            shutil.copy2(src, os.path.join(args.out, stem + ".bin"))

            files = [stem + ".json", stem + ".bin"] + ([stem + ".png"] if png else [])
            index.append({k: v for k, v in record.items() if k != "layers"} | {"files": files})

    with open(os.path.join(args.out, "index.json"), "w") as f:
        json.dump(index, f, indent=1)

    print(f"Captures read from : {saved}")
    print(f"Exported {len(index)} emblem(s) to: {os.path.abspath(args.out)}")
    if index:
        used = [e["layers_used"] for e in index]
        print(f"  layers used  : min {min(used)}, max {max(used)}, "
              f"average {sum(used)/len(used):.1f} of 32")
        orders = {e["byte_order"] for e in index}
        print(f"  byte order   : {', '.join(sorted(orders))}")
        exps = [e["max_scale_exponent"] for e in index if e["max_scale_exponent"] is not None]
        if exps:
            print(f"  max scale exp: {max(exps):.2f}  (2^n x canvas)")
        downscaled = [e for e in index if e["png_rendered_at"] and e["png_rendered_at"] < args.size]
        failed = [e for e in index if not e["png_rendered_at"]]
        if downscaled:
            print(f"  {len(downscaled)} emblem(s) needed a smaller PNG (oversized layers) - "
                  "these are usually the ambitious ones, not the broken ones")
        if failed:
            print(f"  {len(failed)} emblem(s) produced no PNG at all; their .json and .bin are still correct")
    for name, err in skipped:
        print(f"  skipped {name}: {err}")
    if not index:
        print("\nNothing found. Capture some emblems first: turn on Capture mode,\n"
              "then open other players' profiles on your console.")


if __name__ == "__main__":
    main()
