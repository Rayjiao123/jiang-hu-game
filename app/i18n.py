"""Three languages: English, Chinese and Thai. The player chooses one on the home page and sees only that one.

Fixed text in the code (the story, error messages) is written once in all three, in one string: 'English ||| 中文 ||| ไทย'.
The server picks the part for the request's language before anything leaves it (see localize). Text the AI writes is a single
language from the start: the model is told which one, so there is nothing to split or translate."""
import re

SEP = "|||"
LANGS = ("en", "zh", "th")
DEFAULT = "en"
LANG_NAMES = {"en": "English", "zh": "Simplified Chinese (简体中文)", "th": "Thai (ภาษาไทย)"}

_CJK = re.compile(r"[一-鿿]")
_THAI = re.compile(r"[฀-๿]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
_MARKUP = re.compile(r"</?[A-Za-z_][\w-]*(?:\s[^<>]*)?/?>")


def tr(en: str, zh: str, th: str = "") -> str:
    """A fixed message in all three languages. A missing Thai falls back to English."""
    return f"{en} {SEP} {zh} {SEP} {th or en}"


def valid(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT


def parts(text: str) -> list[str]:
    return [p.strip() for p in str(text or "").split(SEP)]


def pick(text: str, lang: str) -> str:
    """The part of a fixed text in this language (the first part, English, when that language is missing)."""
    ps = parts(text)
    i = LANGS.index(valid(lang))
    return ps[i] if i < len(ps) and ps[i] else ps[0]


def plain(text: str) -> str:
    """For prompts and logs: the English part."""
    return parts(text)[0]


def localize(obj, lang: str):
    """Walk a response and replace every fixed three-language string by its part in `lang`."""
    if isinstance(obj, str):
        return pick(obj, lang) if SEP in obj else obj
    if isinstance(obj, dict):
        return {k: localize(v, lang) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [localize(v, lang) for v in obj]
    return obj


def join(*texts: str) -> str:
    """Join several three-language texts into one, language by language."""
    cols: list[list[str]] = [[], [], []]
    for t in texts:
        ps = parts(t)
        for i in range(3):
            cols[i].append(ps[i] if i < len(ps) and ps[i] else ps[0])
    gap = chr(10) * 2
    return f" {SEP} ".join(gap.join(c) for c in cols)


def complete(text: str) -> bool:
    """A fixed text is finished when it has all three languages, each in its own script."""
    ps = parts(text)
    return len(ps) == 3 and bool(_LATIN_WORD.search(ps[0])) and bool(_CJK.search(ps[1])) and bool(_THAI.search(ps[2]))


def in_language(text: str, lang: str) -> bool:
    """Is a text the AI wrote mostly in this language? (Names in another script do not count against it.)"""
    cjk, thai, latin = len(_CJK.findall(text)), len(_THAI.findall(text)), len(_LATIN_WORD.findall(text))
    if lang == "zh":
        return cjk >= 2 and cjk * 2 > latin and thai == 0
    if lang == "th":
        return thai >= 4 and thai > cjk and thai > latin
    return latin >= 2 and latin > cjk // 2 and thai == 0


def clean_ai(text: str, lang: str | None = None) -> str:
    """Text from the model, ready to show: stray tag markup and any '|||' the model wrote are removed. In Thai and English
    any Chinese characters are removed too: the model is given Chinese names and sometimes lets a Chinese word slip into the sentence,
    and names are given to it in the right spelling for the language anyway."""
    text = _MARKUP.sub("", str(text or "")).replace(SEP, "\n")
    if lang in ("en", "th"):
        text = re.sub(r"[一-鿿㐀-䶿，。！？；：、（）《》〈〉【】]+", "", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


STYLE = {
    "zh": "Write natural, idiomatic Chinese in the voice of a wuxia story, not a translation of English.",
    "th": "Write natural, idiomatic Thai in the voice of a Song-dynasty wuxia story, not a word-for-word translation: elders and the keeper may say ข้า and เจ้า; address the young woman as เจ้า, หนู or ลูก according to who is speaking.",
}


def reply_rule(lang: str) -> str:
    """The last thing the model reads on each turn."""
    return (f"Write your whole reply in {LANG_NAMES[valid(lang)]} only, whatever language the player wrote in. "
            f"Do not add a translation, and do not use the symbol {SEP}. Keep any *actions* in asterisks, in the same language. "
            + ("" if lang == "zh" else "Use no Chinese characters at all: write any number or name in this language's own script and spelling. ")
            + STYLE.get(valid(lang), ""))
