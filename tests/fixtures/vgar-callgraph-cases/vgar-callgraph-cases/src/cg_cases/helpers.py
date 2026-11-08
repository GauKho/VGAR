"""Plain module-level helpers used by groups 1, 7 and 10."""


def normalize(text):
    stripped = text.strip()
    return stripped.lower()


def measure(text):
    return len(text)
