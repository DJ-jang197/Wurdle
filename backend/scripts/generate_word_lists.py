"""Regenerate word lists: dictionary 5-letter words, excluding names and regions."""

from __future__ import annotations

import os
import urllib.request

WORD_LISTS_DIR = os.path.join(os.path.dirname(__file__), "..", "word_lists")
# ENABLE is the standard North American dictionary word list (Merriam-Webster Scrabble).
ENABLE_URL = "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt"
COMMON_URL = (
    "https://raw.githubusercontent.com/first20hours/google-10000-english/"
    "master/google-10000-english-no-swears.txt"
)

CURATED_ANSWERS = frozenset({
    "apple", "beach", "brain", "bread", "crane", "dream", "flame", "ghost",
    "grape", "heart", "house", "light", "music", "night", "ocean", "plant",
    "queen", "river", "shade", "smile", "snake", "sound", "spare", "stone",
    "storm", "table", "tiger", "train", "water", "world", "write", "young",
})

# Proper nouns, given names, and geographic regions/places (5 letters, lowercase).
PROPER_NOUNS_EXCLUDE = frozenset({
    "aaron", "adams", "ahmed", "alice", "alien", "amman", "andes", "angel",
    "angus", "ankara", "april", "arabs", "argos", "aries", "aruba", "asia",
    "athens", "austin", "bahrain", "bantu", "barry", "beirut", "belgium",
    "benin", "berlin", "betty", "bhutan", "billy", "bobby", "bonn", "boris",
    "bosnia", "boston", "brady", "brazil", "brian", "bruce", "cairo", "canada",
    "carla", "carlo", "carol", "celts", "chad", "chile", "china", "chloe",
    "clara", "congo", "coral", "croat", "cuba", "czech", "dallas", "david",
    "delhi", "denmark", "diana", "dubai", "dublin", "dutch", "eddie", "egypt",
    "elena", "emily", "emma", "english", "enoch", "epsom", "erica", "espana",
    "ethan", "europe", "evans", "fiji", "finns", "flore", "france", "frank",
    "gabon", "garry", "gaza", "georg", "ghana", "ghent", "greek", "guam",
    "haiti", "hanoi", "harry", "havana", "helen", "henry", "hindu", "homer",
    "honda", "india", "indus", "iraqi", "irene", "irish", "islam", "italy",
    "jacob", "james", "janet", "japan", "jason", "jenny", "jerry", "jesse",
    "jewel", "jimmy", "johns", "jones", "jose", "julia", "julie", "kabul",
    "karen", "kathy", "katie", "kenya", "kiev", "korea", "kuala", "kyoto",
    "lanka", "larry", "latin", "leeds", "leo", "libya", "linda", "lisbon",
    "lizzy", "louis", "lucas", "lucia", "luigi", "madrid", "malta", "maria",
    "marie", "mario", "marty", "mason", "mexico", "miami", "milan", "miles",
    "molly", "monaco", "moses", "mosul", "nancy", "nauru", "nepal", "nevada",
    "niger", "nile", "nokia", "norma", "north", "norway", "oman", "osaka",
    "osaka", "osaka", "oslo", "ottawa", "paige", "paris", "paul", "perth",
    "peru", "peter", "poland", "porto", "prague", "qatar", "quebec", "ralph",
    "randy", "rhode", "riga", "rome", "russia", "samoa", "sarah", "saudi",
    "scots", "seoul", "serbia", "shane", "shanghai", "sharon", "sidney",
    "simon", "singapore", "smith", "sofia", "spain", "sudan", "susan", "swede",
    "swiss", "syria", "taipei", "tammy", "tampa", "tango", "tara", "texas",
    "thai", "timor", "tokyo", "tommy", "tonga", "tracy", "tunis", "turks",
    "uganda", "union", "utah", "venus", "vienna", "wales", "warsaw", "wayne",
    "wendy", "willy", "yemen", "york", "yukon", "zambia", "zeus", "zurich",
    "maine", "idaho", "ohio", "iowa", "utah", "aruba", "congo", "malta",
    "samoa", "tonga", "niger", "ghana", "benin", "egypt", "haiti", "chile",
    "china", "india", "japan", "korea", "nepal", "qatar", "syria", "yemen",
    "spain", "italy", "wales", "dubai", "cairo", "delhi", "milan", "miami",
    "tampa", "dallas", "boston", "omaha", "salem", "miami", "paris", "rome",
    "oslo", "peru", "iran", "iraq", "cuba", "fiji", "guam", "laos",
})


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read().decode("utf-8")


def is_dictionary_word(word: str) -> bool:
    return len(word) == 5 and word.isalpha() and word not in PROPER_NOUNS_EXCLUDE


def main() -> None:
    enable_words = {w.strip().lower() for w in fetch(ENABLE_URL).splitlines() if w.strip()}
    dictionary5 = {w for w in enable_words if is_dictionary_word(w)}

    common_words = {w.strip().lower() for w in fetch(COMMON_URL).splitlines() if w.strip()}
    common5 = {w for w in common_words if is_dictionary_word(w)}

    valid_guesses = sorted(dictionary5)
    answers = sorted((dictionary5 & common5) | (dictionary5 & CURATED_ANSWERS))

    os.makedirs(WORD_LISTS_DIR, exist_ok=True)
    guesses_path = os.path.join(WORD_LISTS_DIR, "valid_guesses.txt")
    answers_path = os.path.join(WORD_LISTS_DIR, "answers.txt")

    with open(guesses_path, "w", encoding="utf-8") as f:
        f.write("\n".join(valid_guesses) + "\n")
    with open(answers_path, "w", encoding="utf-8") as f:
        f.write("\n".join(answers) + "\n")

    excluded = len(enable_words & {w for w in enable_words if len(w) == 5}) - len(dictionary5)
    print(f"Wrote {len(valid_guesses)} valid guesses and {len(answers)} answers.")
    print(f"Excluded {excluded} proper nouns / regions / names.")


if __name__ == "__main__":
    main()
