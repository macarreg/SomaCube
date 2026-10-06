import os
import re

_USERNAME_RE = re.compile(r'[A-Za-z0-9_]{3,20}')
_RESERVED = {
    'admin', 'administrator', 'moderator', 'mod', 'support', 'root',
    'system', 'staff', 'anonymous', 'null', 'undefined',
}

# Stems blocked anywhere inside a name. Leetspeak (sh1t) and stretched
# letters (fuuuck) are caught too.
_SUBSTRING_WORDS = {
    'fuck', 'shit', 'bitch', 'cunt', 'pussy', 'whore', 'slut', 'penis',
    'vagina', 'nigg', 'faggot', 'retard', 'tranny', 'hitler', 'rapist',
    'porn', 'jizz', 'wank', 'twat', 'blowjob', 'bollock', 'dildo',
    'cumshot', 'molest', 'pedophile', 'incest', 'boob', 'piss',
    'asshole', 'wetback', 'bastard',
}

# Short words that also sit inside innocent ones ("class", "Essex", "grape",
# "Pakistan"), so they're only blocked as a whole word: the entire name, or a
# segment split on underscores, digits, or capital letters (Big_Dick, AssMan).
_TOKEN_WORDS = {
    'ass', 'arse', 'dick', 'cock', 'prick', 'cum', 'tit', 'tits', 'anal',
    'sex', 'pedo', 'rape', 'fag', 'dyke', 'chink', 'spic', 'kike', 'gook',
    'coon', 'paki', 'negro', 'nazi', 'nazis', 'beaner',
}

_LEET_I = str.maketrans('013457', 'oieast')   # 1 -> i
_LEET_L = str.maketrans('013457', 'oleast')   # 1 -> l


def _load_extra_words():
    """Optional backend/username_blocklist.txt: one entry per line.
    Plain lines block anywhere in a name; lines starting with '=' block only
    as a whole word. '#' starts a comment."""
    path = os.path.join(os.path.dirname(__file__), 'username_blocklist.txt')
    subs, toks = set(), set()
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                word = line.strip().lower()
                if not word or word.startswith('#'):
                    continue
                if word.startswith('='):
                    toks.add(word[1:])
                else:
                    subs.add(word)
    except FileNotFoundError:
        pass
    return subs, toks


def _compile(words):
    # "fuck" -> f+u+c+k+  (tolerates repeated letters without collapsing the
    # name, which would make short stems match innocent words)
    parts = ['+'.join(re.escape(c) for c in w) + '+' for w in sorted(words)]
    return re.compile('|'.join(parts)) if parts else None


_extra_subs, _extra_toks = _load_extra_words()
_SUB_RE = _compile(_SUBSTRING_WORDS | _extra_subs)
_TOKEN_SET = _TOKEN_WORDS | _extra_toks


def contains_profanity(name):
    lower = name.lower()
    squashed = lower.replace('_', '')
    variants = {
        squashed,
        squashed.translate(_LEET_I),
        squashed.translate(_LEET_L),
        re.sub(r'\d', '', squashed),
    }
    if _SUB_RE and any(_SUB_RE.search(v) for v in variants):
        return True

    tokens = {t for t in re.split(r'[_0-9]+', lower) if t}
    for v in (lower.translate(_LEET_I), lower.translate(_LEET_L)):
        tokens.update(t for t in v.split('_') if t)
        tokens.add(v.replace('_', ''))
    tokens.update(t.lower() for t in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', name))
    tokens.add(squashed)
    return not tokens.isdisjoint(_TOKEN_SET)


def validate_username(raw):
    """Returns (clean_username, None) or (None, error_message)."""
    name = raw.strip() if isinstance(raw, str) else ''
    if not name:
        return None, 'Username is required.'
    if not _USERNAME_RE.fullmatch(name):
        return None, 'Usernames must be 3–20 characters: letters, numbers, and underscores only.'
    if name.lower() in _RESERVED:
        return None, 'That username is reserved.'
    if contains_profanity(name):
        return None, "That username isn't allowed. Please choose another."
    return name, None


def is_username_taken(name, exclude_user_id=None):
    from models import db, User  # local import avoids a circular import
    query = db.session.query(User.id).filter(db.func.lower(User.username) == name.lower())
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None