"""Everything the site says appears in English and Chinese.

Text written by the AI uses one convention: the English version, then ` ||| `, then the Chinese
version. The page splits on it. This module checks the convention and, when the model forgets it,
translates the missing half, so a visitor never sees one language only."""
import re

SEP = "|||"
_CJK = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def bi(en: str, zh: str) -> str:
    """A fixed message in both languages, for errors and notices."""
    return f"{en}\n{zh}"


def language_of(text: str) -> str:
    """Which language a message is mostly written in (a Chinese name inside English stays English)."""
    return "Chinese" if len(_CJK.findall(text)) > len(_LATIN_WORD.findall(text)) else "English"


def has_both(text: str) -> bool:
    """True when a text already contains real English and real Chinese (e.g. a bilingual starter line)."""
    return len(_CJK.findall(text)) >= 2 and len(_LATIN_WORD.findall(text)) >= 2


def split(text: str) -> tuple[str, str]:
    en, _, zh = str(text or "").partition(SEP)
    return en.strip(), zh.strip()


def is_pair(text: str) -> bool:
    """English first, then |||, then Chinese; both halves present and in the right script."""
    if SEP not in str(text or ""):
        return False
    en, zh = split(text)
    return bool(_LATIN_WORD.search(en)) and bool(_CJK.search(zh))


def normalize(text: str) -> str:
    """Put a reply into the form 'English ||| 中文'. The model sometimes forgets the separator, or repeats it
    for every paragraph; sort the paragraphs by language and join them with a single separator. A reply
    that is in one language only is returned unchanged (the caller translates it)."""
    text = str(text or "").strip()
    if text.count(SEP) == 1 and is_pair(text):
        return text
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text.replace(SEP, "\n\n")) if p.strip()]
    en = [p for p in paragraphs if language_of(p) == "English"]
    zh = [p for p in paragraphs if language_of(p) == "Chinese"]
    if en and zh:
        return "\n\n".join(en) + f"\n{SEP}\n" + "\n\n".join(zh)
    return text


def plain(text: str) -> str:
    """For prompts and logs: 'English ||| 中文' becomes 'English / 中文'."""
    return " / ".join(part.strip() for part in str(text or "").split(SEP))


def counterpart(client, model: str, text: str) -> str:
    """The same text in the other language. Empty string when it is already bilingual or the call fails."""
    text = (text or "").strip()
    if not text or has_both(text):
        return ""
    target = "English" if language_of(text) == "Chinese" else "Chinese"
    try:
        r = client.chat.completions.create(
            model=model, max_tokens=500, extra_body={"thinking": {"type": "disabled"}},
            messages=[
                {"role": "system", "content": (
                    f"You translate for a Song-dynasty wuxia game website. Translate the user's text into {target}. "
                    "Keep names, tone and any *asterisk actions* as they are. Output only the translation, nothing else.")},
                {"role": "user", "content": text}])
        return (r.choices[0].message.content or "").strip()
    except Exception as e:  # a missing translation is better than a failed reply
        print("Translation failed:", repr(e))
        return ""


# Added to every prompt so the format is the last thing the model reads.
REPLY_FORMAT = ("Write every reply in BOTH languages: the complete English version first, then ONE line containing only |||, "
                "then the complete Chinese version (same meaning, same *actions*). Use the ||| line exactly once per reply, "
                "never once per paragraph, and never skip either half.")
FIELD_FORMAT = ("Every text field except name is written in both languages in one string, English first: "
                "'English text ||| 中文文字'. The name is Chinese followed by pinyin.")
