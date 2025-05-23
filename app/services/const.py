# Load API keys from environment variables
import os


EMAG_API_KEY = os.getenv("EMAG_API_KEY")
FITNESS1_API_KEY = os.getenv("FITNESS1_API_KEY")

# Build the EMAG_HEADERS dynamically
EMAG_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {EMAG_API_KEY}",
}
EMAG_URL = "https://marketplace-api.emag.{}/api-3/"
FITNESS1_API_URL = "https://fitness1.bg/b2b/api/products_v3"
FITNESS_CATEGORIES = [
    "Спортни протектори за тяло",
    "Шейкъри и бутилки",
    "Протеини",
    "Аминокиселини",
    "Въглехидрати",
    "Креатин",
    "Витамини и минерали",
    "Продукти за отслабване и детокс",
    "Спортни ръкавици",
    "Фитнес ластици",
    "Фитнес топки",
    "Хранителни добавки на прах",
    "Аксесоари за тренировка",
    "Други спортни добавки",
    "Други хранителни добавки",
    "Фитнес аксесоари",
]
THRESHLOD = 80

# Create a keyword dictionary for some small categories to improve matching
KEYWORDS_MAPPING = {
    "Шейкъри и бутилки": ["шейкър", "бутилка", "блендер бутилка"],
    "Спортни протектори за тяло": ["протектор"],
    "Протеини": [
        "протеин",
        "казеин",
        "суроватъчен",
        "телешки протеин",
        "яйчен протеин",
        "растителен протеин",
    ],
    "Аминокиселини": [
        "аминокиселин",
        "BCAA",
        "EAA",
        "аргинин",
        "глутамин",
        "таурин",
        "HMB",
    ],
    "Въглехидрати": [
        "въглехидрат",
        "декстроза",
        "малтодекстрин",
        "оризови въглехидрати",
        "рибоза",
        "специални въглехидрати",
    ],
    "Креатин": ["креатин"],
    "Витамини и минерали": ["витамин", "минерал", "мултивитамин"],
    "Продукти за отслабване и детокс": [
        "отслабване",
        "детокс",
        "карнитин",
        "термоген",
        "диуретик",
        "синефрин",
        "ябълков оцет",
        "пируват",
        "форсколин",
    ],
    "Спортни ръкавици": ["ръкавици"],
    "Фитнес ластици": ["ластиц", "тренировъчни ластици"],
    "Фитнес топки": ["топка"],
    "Други спортни добавки": [
        "предтренировъчни",
        "бустер",
        "стимулан",
        "хардкор",
        "igf",
        "естероид",
        "тестостерон",
        "туркестерон",
    ],
    "Аксесоари за тренировка": ["тренировка", "фитнес аксесоари"],
    "Други хранителни добавки": ["добавки"],
    "Хранителни добавки на прах": ["прах", "добавки на прах"],
    "Фитнес аксесоари": ["аксесоар", "фитнес"],
}
