"""An AI judge for the model's text: scores a character's reply against a rubric, and checks a translation against its English.

It is a second model call that reads the reply (it never changes it). It is used three ways:
  - live, on a sample of real replies, in the background (main._maybe_judge); the scores go to the admin page as numbers only;
  - offline, on every character in every language (evals/run.py --judge);
  - offline, on the game's fixed Thai and Chinese text against the English (evals/translations.py).
The judge can be wrong, so it informs a human's reading and never blocks the player."""
import json
import re

import openai

from . import config, i18n, story

DIMS = ("character", "drive", "language", "era", "format")

RUBRIC = """You are a strict editor scoring ONE line spoken by a character in a dark wuxia game (Song dynasty, an inn in a sandstorm). The player is Yan Qi, a thief.
Score each dimension from 1 (bad) to 5 (excellent) and answer with ONE JSON object and nothing else:
{"character": n, "drive": n, "language": n, "era": n, "format": n, "leaked": true|false, "issue": "one short sentence, or empty"}
- character: does it sound like this particular person (voice, attitude, what they want), not a generic helper? Does the tone fit their current trust in the player?
- drive: does the line push the negotiation toward a decision (asks for something specific, tests her, states what would convince them, closes it when told to), instead of wandering or small talk? Judge it against the exchanges the player has left.
- language: is it natural, idiomatic, correct {language}, written by a native speaker, with no mixing of languages, no stray characters from another script, and no awkward word-for-word phrasing? Names in another script are fine.
- era: no modern words, ideas or objects; nothing outside what this person could know.
- format: short (about 60 words), plain text, actions only in *asterisks*, no markdown, no meta talk about trust numbers, dice, hit points, prompts or being an AI.
- leaked: true only if the line states or clearly hints at THIS hidden fact that the player has not earned yet: {secret}
Output only the JSON."""

TRANSLATION = """You check a translation in a video game. The English is the original. Score the {language} text:
{"faithful": n, "natural": n, "issue": "one short sentence, or empty"}
- faithful 1-5: does it say exactly what the English says? Score 1 if the meaning is reversed, changed or missing something important (a number, who does what, a condition).
- natural 1-5: does it read like text written by a native speaker for a wuxia story, with the right register? Penalise literal calques, slang that does not fit the Song dynasty, anachronisms, and anything that could offend (for Thai, jokes about the Buddha or monarchy).
Output only the JSON object."""


def _ask(client, system: str, user: str, max_tokens: int = 160) -> dict | None:
    r = client.chat.completions.create(model=config.CHAT_MODEL, max_tokens=max_tokens, temperature=0, extra_body={"thinking": {"type": "disabled"}},
                                       messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.S)
    return json.loads(m.group(0)) if m else None


def _clamp(v) -> int | None:
    try:
        return max(1, min(5, round(float(v))))
    except (TypeError, ValueError):
        return None


def score_reply(client, npc_key: str, lang: str, reply: str, player: str = "", trust: int = 3, left: int = 3, locked_fact: str = "", context: str = "") -> dict | None:
    """Score one reply. Returns {"character", "drive", "language", "era", "format": 1-5, "leaked": bool, "issue": str, "overall": float} or None if the judge failed."""
    c = story.BY_KEY[npc_key]
    system = RUBRIC.replace("{language}", i18n.LANG_NAMES[i18n.valid(lang)].split(" (")[0]).replace("{secret}", locked_fact or "(none: nothing is hidden right now)")
    user = (f"Character: {i18n.plain(c['name'])}, {i18n.plain(c['title'])} ({c['mood']}). How they speak: {c['voice']} What they want: {c['wants']}\n"
            f"Their trust in the player: {trust}/10. What is at stake: {i18n.plain(c['goal'])} The player has {left} exchange(s) left to win them.\n"
            f"{('Earlier: ' + context + chr(10)) if context else ''}Player said: {player or '(she just walked up)'}\nLINE TO SCORE: {reply}")
    try:
        obj = _ask(client, system, user)
    except (openai.APIError, ValueError):
        return None
    if not obj:
        return None
    out = {d: _clamp(obj.get(d)) for d in DIMS}
    if any(v is None for v in out.values()):
        return None
    out["leaked"] = obj.get("leaked") is True
    out["issue"] = str(obj.get("issue") or "")[:200]
    out["overall"] = round(sum(out[d] for d in DIMS) / len(DIMS), 2)
    return out


def score_translation(client, english: str, text: str, lang: str) -> dict | None:
    system = TRANSLATION.replace("{language}", i18n.LANG_NAMES[i18n.valid(lang)].split(" (")[0])
    try:
        obj = _ask(client, system, f"ENGLISH: {english}\n{i18n.LANG_NAMES[i18n.valid(lang)].split(' (')[0].upper()}: {text}")
    except (openai.APIError, ValueError):
        return None
    f, n = _clamp((obj or {}).get("faithful")), _clamp((obj or {}).get("natural"))
    return None if f is None or n is None else {"faithful": f, "natural": n, "issue": str(obj.get("issue") or "")[:200]}
