import json
import os
from typing import Dict, Set, Tuple

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")


def load_state() -> Tuple[Dict[int, dict], Set[int]]:
    # Загружаем user_settings и known_users из JSON и возвращаем их.
    if not os.path.exists(USERS_FILE):
        return {}, set()

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}, set()

    raw_users = data.get("user_settings", {})
    raw_known = data.get("known_users", [])

    user_settings: Dict[int, dict] = {}
    for key, value in raw_users.items():
        try:
            chat_id = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            user_settings[chat_id] = value

    known_users: Set[int] = set()
    for item in raw_known:
        try:
            known_users.add(int(item))
        except (TypeError, ValueError):
            continue

    return user_settings, known_users


def save_state(user_settings: Dict[int, dict], known_users: Set[int]) -> None:
    # Сохраняем user_settings и known_users в JSON.
    os.makedirs(DATA_DIR, exist_ok=True)

    data = {
        "user_settings": {str(chat_id): settings for chat_id, settings in user_settings.items()},
        "known_users": sorted(list(known_users)),
    }

    tmp_path = USERS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, USERS_FILE)
