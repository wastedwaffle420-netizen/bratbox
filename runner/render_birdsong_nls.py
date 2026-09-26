#!/usr/bin/env python3
"""Render NLS-injected birdsong variants.

The game injects NLS sounds into templates at runtime
({fluster} -> "Hahhh", {cute} -> "BAKA", {combo} -> 23, ...).
This pre-renders every reachable variant so the TTS operator's
cache lookup hits on the final spoken text.

Union pools cover every intensity/mood branch of the inject functions.
"""
import ast
import itertools
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from elevenlabs_writer import (  # noqa: E402
    _ttscli_cache_key,
    jasmine_tts_text,
    fiend_tts_text,
    JASMINE_TTSCLI_VOICE,
    FIEND_TTSCLI_VOICE,
    JASMINE_VOICE_CACHE,
    FIEND_VOICE_CACHE,
)

VENDOR = (HERE / "../../ogre_full/ogre_full/wotw_bratbox/vendor_full"
          "/ogre_shader_v5.py").resolve()

# placeholder -> AST pool-constant names whose union covers all branches
POOLS = {
    "fluster": ["BIRDSONG_FLUSTER_SOUNDS"],
    "fluster_inline": None,  # + inline variants below
    "cute": ["BIRDSONG_CUTE_SOUNDS"],
    "whine": ["BIRDSONG_WHINES"],
    "react": ["BIRDSONG_REACTIONS"],
    "power": ["POWER_VERBS"],
    "soft": ["FIEND_SOFT_SOUNDS", "FIEND_BREATHY", "FIEND_PEAK"],
    "breathy": ["FIEND_BREATHY"],
    "opener": ["FIEND_OPENERS", "FIEND_OPENERS_SOFT", "FIEND_OPENERS_EAGER",
               "FIEND_COMMANDS_INTENSE"],
    "catch": ["FIEND_CATCHES", "FIEND_CATCHES_FOND", "FIEND_CATCHES_SMUG"],
    "puppy": ["FIEND_PUPPY", "FIEND_PUPPY_CAUGHT", "FIEND_PUPPY_FLUSTERED",
              "FIEND_VULNERABLE"],
    "tease": ["FIEND_TEASES", "FIEND_TEASES_SOFT", "FIEND_TEASES_SMUG"],
    "command": ["FIEND_COMMANDS", "FIEND_COMMANDS_SOFT",
                "FIEND_COMMANDS_INTENSE"],
}
FIEND_CUTE_POOLS = ["FIEND_CUTE_SOUNDS", "FIEND_CUTE_RARE", "FIEND_PLEASED",
                    "FIEND_BREATHY"]
FIEND_REACT_POOLS = ["FIEND_REACTIONS_LOW", "FIEND_REACTIONS_MID",
                     "FIEND_REACTIONS_HIGH"]
# inline pools from the inject functions' intensity/state branches
INLINE = {
    "fluster": ["Hahhh", "Nngh", "Guh", "Tch", "Gah", "Pfft"],
    "cute": ["Awaaa~", "Heeee~", "Mmm~", "BAKA", "Mwehhh~", "Nyeh~"],
}


def load_pools():
    src = VENDOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    vals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            nm = node.targets[0].id
            try:
                v = ast.literal_eval(node.value)
            except Exception:
                continue
            if isinstance(v, (list, tuple)) and v and all(
                    isinstance(x, str) for x in v):
                vals[nm] = list(v)
    return vals


def union_pool(names, vals):
    out = []
    for nm in names:
        for s in vals.get(nm, []):
            if s not in out:
                out.append(s)
    return out


def templates():
    src = VENDOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    tpl = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                v = ast.literal_eval(node.value)
            except Exception:
                continue

            def walk(x):
                if (isinstance(x, tuple) and len(x) == 2
                        and isinstance(x[0], str) and isinstance(x[1], str)):
                    if x[0] in ("BIRDSONG", "FIEND") and "{" in x[1]:
                        tpl.add((x[0], x[1].strip()))
                elif isinstance(x, (list, tuple)):
                    for i in x:
                        walk(i)
                elif isinstance(x, dict):
                    for k, i in x.items():
                        walk(i)
            walk(v)
    return sorted(tpl)


def jobs():
    vals = load_pools()
    seen = set()
    for speaker, tpl_text in templates():
        phs = sorted(set(re.findall(r"\{(\w+)\}", tpl_text)))
        if speaker == "BIRDSONG":
            voice, cache, clean = (JASMINE_TTSCLI_VOICE, JASMINE_VOICE_CACHE,
                                   jasmine_tts_text)
        else:
            voice, cache, clean = (FIEND_TTSCLI_VOICE, FIEND_VOICE_CACHE,
                                   fiend_tts_text)
        pool_lists = []
        skip = False
        for ph in phs:
            if ph == "combo":
                pool_lists.append([str(n) for n in range(1, 51)])
            elif ph == "cute" and speaker == "FIEND":
                pool_lists.append(union_pool(FIEND_CUTE_POOLS, vals)
                                   + INLINE["cute"])
            elif ph == "react" and speaker == "FIEND":
                pool_lists.append(union_pool(FIEND_REACT_POOLS, vals))
            elif ph in POOLS:
                pool_lists.append(union_pool(POOLS[ph], vals)
                                   + INLINE.get(ph, []))
            else:
                print(f"  unknown placeholder {{{ph}}} in: {tpl_text[:60]}",
                      flush=True)
                skip = True
        if skip:
            continue
        # dedupe within pools to keep the product small
        pool_lists = [list(dict.fromkeys(p)) for p in pool_lists]
        total = 1
        for p in pool_lists:
            total *= len(p)
        if total > 400:
            print(f"  skipping large expansion ({total}): {tpl_text[:60]}",
                  flush=True)
            continue
        for combo in itertools.product(*pool_lists):
            text = tpl_text
            for ph, val in zip(phs, combo):
                text = text.replace("{" + ph + "}", val)
            tts_text = clean(text)
            if not tts_text:
                continue
            key = _ttscli_cache_key(voice, tts_text)
            dest = cache / f"ttscli_{key}.mp3"
            tag = (voice, key)
            if tag in seen:
                continue
            seen.add(tag)
            if dest.is_file() and dest.stat().st_size > 1000:
                continue
            yield voice, tts_text, dest


def render_one(job):
    voice, tts_text, dest = job
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        ["tts", "speak", "--voice", voice,
         "--text", tts_text, "--output", str(dest)],
        capture_output=True, timeout=180)
    ok = (p.returncode == 0 and dest.is_file()
          and dest.stat().st_size > 1000)
    if not ok:
        err = (p.stderr or b"").decode(errors="replace")[-160:]
        print(f"FAILED {dest.name}: {err}", flush=True)
    return ok


def main():
    work = list(jobs())
    print(f"{len(work)} NLS variant clips to render", flush=True)
    done = failed = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for ok in ex.map(render_one, work):
            done += ok
            failed += (not ok)
            if (done + failed) % 25 == 0:
                print(f"  {done + failed}/{len(work)}", flush=True)
    print(f"done: {done} rendered, {failed} failed", flush=True)


if __name__ == "__main__":
    main()
