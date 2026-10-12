"""Check the game's fixed Thai and Chinese text against the English with the AI judge. Run it after editing any text in app/story.py:

    .venv\\Scripts\\python.exe -m evals.translations --lang th      (or zh, or all)

Every line is scored for faithfulness (does it say what the English says: a reversed meaning scores 1) and naturalness. Lines under 4 are listed.
It reads the text from app/story.py; the page's own strings (static/app.js, static/i18n.js) are not covered. A native speaker's read still matters more."""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from app import config, i18n, judge, main, story  # noqa: E402

if not config.DEEPSEEK_API_KEY:
    sys.exit("Set DEEPSEEK_API_KEY (in .env or the environment) to run this.")


def texts() -> list[tuple[str, str]]:
    out = [("setup", story.SETUP), ("goal", story.GOAL), ("how to", story.HOW_TO), ("prologue", story.PROLOGUE)]
    for k, a in story.ARTS.items():
        out += [(f"art {k} name", a["name"]), (f"art {k}", a["does"])]
    for c in story.CAST:
        out += [(f"{c['key']} {f}", c[f]) for f in ("title", "public", "goal", "arrival", "hostile", "down")] + [(f"{c['key']} reward", c["reward"]["gain"])]
    for k, e in story.ENDINGS.items():
        out += [(f"ending {k} title", e["title"]), (f"ending {k}", e["fallback"])]
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    want = args[args.index("--lang") + 1] if "--lang" in args else "th"
    langs = ["zh", "th"] if want == "all" else [want]
    client, bad, t0, n = main.llm(), 0, time.time(), 0
    for lg in langs:
        idx = i18n.LANGS.index(lg)
        print(f"\n===== {i18n.LANG_NAMES[lg]} =====")
        for label, text in texts():
            p = i18n.parts(text)
            s = judge.score_translation(client, p[0], p[idx], lg)
            n += 1
            if s is None:
                print(f"  ?     {label}: the judge did not answer")
            elif min(s["faithful"], s["natural"]) < 4:
                bad += 1
                print(f"  FIX   {label}: faithful {s['faithful']} natural {s['natural']}  {s['issue']}\n        EN: {p[0][:110]}\n        {lg.upper()}: {p[idx][:110]}")
    print(f"\n{n} lines checked, {bad} to look at ({time.time() - t0:.0f}s)")
    sys.exit(1 if bad else 0)
