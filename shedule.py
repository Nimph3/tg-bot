import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aiohttp

from config import DAY_NAMES, SHEET_CSV_URL, SCHEDULE_CACHE_TTL
from utils import normalize_spaces, get_free_time_text

logger = logging.getLogger(__name__)


@dataclass
class ClassSchedule:
    label: str
    block_title: str
    days: Dict[str, List[str]]


_cached_csv_text: Optional[str] = None
_cached_at: Optional[datetime] = None


async def _download_csv() -> Optional[str]:
    # Скачивание CSV. Без кэша.
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SHEET_CSV_URL) as resp:
                resp.raise_for_status()
                csv_text = await resp.text()
    except Exception as e:
        logger.exception("Ошибка запроса CSV: %s", e)
        return None

    if csv_text.lstrip().startswith("<"):
        logger.error("Ожидался CSV, но получен HTML. Проверь ссылку/доступ.")
        return None

    return csv_text


async def get_csv_text_cached() -> Optional[str]:
    # Получаем CSV с кэшем.
    global _cached_csv_text, _cached_at

    now = datetime.utcnow()
    if _cached_csv_text is not None and _cached_at is not None:
        if now - _cached_at < timedelta(seconds=SCHEDULE_CACHE_TTL):
            return _cached_csv_text

    csv_text = await _download_csv()
    if csv_text is not None:
        _cached_csv_text = csv_text
        _cached_at = now

    return csv_text


def reset_cache() -> None:
    # Сброс кэша CSV админ-команда.
    global _cached_csv_text, _cached_at
    _cached_csv_text = None
    _cached_at = None


async def get_class_schedule(parallel: str, variant: str) -> Tuple[Optional[ClassSchedule], Optional[str]]:
    # Возвращает расписание
    class_label = f"{parallel} {variant}"
    block_title = f"Расписание {parallel} {variant} класса"
    block_title_norm = normalize_spaces(block_title)

    csv_text = await get_csv_text_cached()
    if csv_text is None:
        return None, (
            "Не получилось получить данные с Google Sheets.\n"
            "Проверь ссылку, доступ к таблице и формат экспорта (CSV)."
        )

    reader = csv.reader(io.StringIO(csv_text))

    in_block = False
    header_processed = False
    day_indices: Dict[str, int] = {}
    day_to_lessons: Dict[str, List[str]] = {}

    for row in reader:
        nonempty_cells = [cell.strip() for cell in row if cell.strip()]
        joined = " ".join(nonempty_cells)
        joined_norm = normalize_spaces(joined) if joined else ""

        if not in_block:
            if joined_norm and joined_norm.startswith(block_title_norm):
                in_block = True
                header_processed = False
                day_indices.clear()
            continue

        if (
            joined_norm.startswith("Расписание ")
            and "класса" in joined_norm
            and not joined_norm.startswith(block_title_norm)
        ):
            break

        if not header_processed and any("№ урока" in cell for cell in row):
            for idx, cell in enumerate(row):
                name = cell.strip()
                if name in DAY_NAMES:
                    day_indices[name] = idx
            header_processed = True
            continue

        if not header_processed:
            continue

        if not row or not row[0].strip():
            continue

        lesson_cell = row[0].strip()
        parts = lesson_cell.splitlines()
        lesson_num = parts[0].strip()
        time = parts[1].strip() if len(parts) > 1 else ""

        for day, idx in day_indices.items():
            if idx >= len(row):
                continue
            subject = row[idx].strip()
            if not subject:
                continue

            line = f"{lesson_num}. {subject}"
            if time:
                line += f" ({time})"

            day_to_lessons.setdefault(day, []).append(line)

    if not day_to_lessons:
        return None, (
            f"Не удалось найти расписание для класса {class_label}.\n"
            f"Убедись, что в таблице есть строка с заголовком «{block_title}»."
        )

    schedule = ClassSchedule(
        label=class_label,
        block_title=block_title,
        days=day_to_lessons,
    )
    return schedule, None


def _fill_missing_lessons_with_free_time(lessons: List[str]) -> List[str]:
    # Добавляем смайлики
    if not lessons:
        return lessons

    num_to_line: Dict[int, str] = {}
    extra_lines: List[str] = []

    for line in lessons:
        stripped = line.lstrip()
        parts = stripped.split(".", 1)
        first = parts[0].strip() if parts else ""
        if first.isdigit():
            num = int(first)
            num_to_line[num] = line
        else:
            extra_lines.append(line)

    if not num_to_line:
        return lessons

    max_num = max(num_to_line.keys())

    for n in range(1, max_num + 1):
        if n not in num_to_line:
            phrase = get_free_time_text()
            num_to_line[n] = f"{n}. {phrase}"

    result: List[str] = [num_to_line[n] for n in sorted(num_to_line.keys())]
    result.extend(extra_lines)
    return result


def render_full_schedule(schedule: ClassSchedule) -> str:
    # Текст
    lines: List[str] = [
        f"<b>Расписание для класса {schedule.label}</b>",
        f"({schedule.block_title})",
        "",
    ]

    for day in DAY_NAMES:
        lessons = schedule.days.get(day)
        if not lessons:
            continue

        lessons = _fill_missing_lessons_with_free_time(lessons)

        lines.append(f"<b>{day}:</b>")
        for lesson_line in lessons:
            lines.append(f"• {lesson_line}")
        lines.append("")

    return "\n".join(lines).rstrip()


def render_day_schedule(schedule: ClassSchedule, day_name: str) -> str:
    # Расписание на один день
    lessons = schedule.days.get(day_name)
    if not lessons:
        phrase = get_free_time_text()
        return f"<b>{day_name}</b>: уроков нет. {phrase}"

    lessons = _fill_missing_lessons_with_free_time(lessons)

    lines: List[str] = [
        f"<b>Расписание для класса {schedule.label} на {day_name.lower()}:</b>",
        "",
    ]
    for lesson_line in lessons:
        lines.append(f"• {lesson_line}")

    return "\n".join(lines).rstrip()


def _day_name_for_date(d: date) -> Optional[str]:
    idx = d.weekday()
    if 0 <= idx < len(DAY_NAMES):
        return DAY_NAMES[idx]
    return None


def get_today_day_name() -> Optional[str]:
    return _day_name_for_date(date.today())


def get_tomorrow_day_name() -> Optional[str]:
    return _day_name_for_date(date.today() + timedelta(days=1))
