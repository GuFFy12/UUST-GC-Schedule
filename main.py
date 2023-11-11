from configparser import ConfigParser
from datetime import datetime, timedelta
from time import time, sleep
from typing import Callable, Tuple, Optional, Union

import requests
from bs4 import BeautifulSoup
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar
from gcsa.reminders import Reminder
from pytz import timezone


# Utilities

class Settings:
    def __init__(self):
        config_parser = ConfigParser()
        config_parser.optionxform = str

        config_file = config_parser.read("config.ini")
        if not config_file:
            raise ValueError('No config file found!')

        settings = config_parser["Settings"]
        self.task_scheduler_delay = int(settings.get("task_scheduler_delay", "0"))
        self.default_calendar = settings.get("default_calendar", "")
        self.schedule_semester_id = int(settings.get("schedule_semester_id", "0"))
        self.schedule_type = int(settings.get("schedule_type", "0"))
        self.student_group_or_teacher_id = int(settings.get("student_group_or_teacher_id", "0"))
        self.minutes_before_reminder_first_lesson = int(settings.get("minutes_before_reminder_first_lesson", "0"))
        self.minutes_before_reminder = int(settings.get("minutes_before_reminder", "0"))


def every(delay: Union[int, float], task: Callable, args: Optional[Tuple]):
    next_time = time() + delay
    while True:
        sleep(max(0.0, next_time - time()))
        try:
            task(*args)
        except Exception as error:
            print(f"{type(error).__name__} — {str(error)}")

        next_time += (time() - next_time) // delay * delay + delay


def get_date_of_first_september_week(current_date: datetime):
    first_september = timezone("Asia/Yekaterinburg").localize(datetime(current_date.year, 9, 1))

    if current_date < first_september:
        first_september = datetime(current_date.year - 1, 9, 1)

    day_of_week = first_september.weekday()

    return first_september - timedelta(days=day_of_week)


def get_date_from_schedule(date_of_first_september_week: datetime, week: int, day_of_week: str, lesson_time: str):
    index_day_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"].index(day_of_week)
    hours, minutes = map(int, lesson_time.split(":"))

    return date_of_first_september_week + timedelta(weeks=week - 1, days=index_day_of_week, hours=hours, minutes=minutes)


def get_lesson_number(lesson_start_time: str):
    return ["08:00", "09:35", "11:35", "13:10", "15:10", "16:45", "18:20", "19:55", "21:25", "22:55"].index(lesson_start_time) + 1


def get_event_color(lesson_type: str):
    event_colors = {
        "Лекция": "3",
        "Практика (семинар)": "6",
        "Лабораторная работа": "9",
        "Физвоспитание": "2",
        "Военная подготовка": "10",
        "Лекция + практика": "4",
        "Консультация": "7",
        "Экзамен": "11",
        "Консультация экзамена": "11",
        "Ликвидация задолженостей": "11",
        "Зачёт с оценкой": "11",
        "Зачёт": "11",
        "Защита (Курсовой/РГР/Лабораторной)": "11",
        "Лекция + практика + лабораторная работа": "1",
        "Мероприятие": "5",
        "Кураторский час": "5",
        "Прочее": "8",
    }

    event_color = event_colors.get(lesson_type)
    if event_color is None:
        print(f"Ошибка — Тип предмета '{lesson_type}' не найден в словаре")

    return event_color


def format_event_as_string(event: Event):
    return f"{datetime.strftime(event.start, '%d.%m.%Y %H:%M')}, {event.summary}, {event.location}, {event.description}"


def get_event_hash(event: Event):
    return str(hash((event.summary, event.description, event.location, datetime.strftime(event.start, '%d.%m.%Y %H:%M'))))


# Main Code

def get_schedule_events(date_of_first_september_week: datetime, schedule_semester_id: int, schedule_type: int, student_group_or_teacher_id: int,
                        minutes_before_reminder_first_lesson: int, minutes_before_reminder: int):
    params = {
        "schedule_semestr_id": schedule_semester_id,
        "WhatShow": schedule_type,
        "weeks": 0,
    }

    if schedule_type == 1:
        params["student_group_id"] = student_group_or_teacher_id
    elif schedule_type == 2:
        params["teacher"] = student_group_or_teacher_id

    response = requests.get("https://isu.ugatu.su/api/new_schedule_api/", params)
    soup = BeautifulSoup(response.text, "html.parser")
    lesson_rows = soup.find("tbody").findAll("tr")

    schedule_events = {}

    day_of_week = ""
    first_lesson_of_the_day_number = {}
    for lesson_row in lesson_rows:
        lesson_columns = lesson_row.findAll("td")

        if "dayheader" in lesson_row["class"]:
            day_of_week = lesson_columns[0].text

        if "noinfo" in lesson_row["class"]:
            continue

        lesson_start_time, lesson_end_time = lesson_columns[1].text.split("-")
        lesson_weeks = lesson_columns[2].text.split()
        lesson_name = lesson_columns[3].text
        lesson_type = lesson_columns[4].text
        lesson_teacher_or_student_group = lesson_columns[5].text
        lesson_classroom = lesson_columns[6].text
        lesson_comment = lesson_columns[7].text

        for week in lesson_weeks:
            lesson_day_hash = str(hash((week, day_of_week)))
            lesson_number = get_lesson_number(lesson_start_time)

            lesson_start_date = get_date_from_schedule(date_of_first_september_week, int(week), day_of_week, lesson_start_time)
            lesson_end_date = get_date_from_schedule(date_of_first_september_week, int(week), day_of_week, lesson_end_time)

            schedule_event = Event(
                f"{lesson_number}. {lesson_name} — {lesson_type}",
                description=("Преподаватель" if schedule_type == 1 else "Группа") + f": {lesson_teacher_or_student_group}" +
                            (f"\nКомментарий: {lesson_comment}" if lesson_comment != "" else ""),
                reminders=[
                    Reminder("popup", (minutes_before_reminder_first_lesson
                                       if (lesson_day_hash not in first_lesson_of_the_day_number or first_lesson_of_the_day_number[lesson_day_hash] == lesson_number)
                                       else minutes_before_reminder)
                             ),
                ],
                color_id=get_event_color(lesson_type),
                location=lesson_classroom,
                timezone="Asia/Yekaterinburg",
                start=lesson_start_date,
                end=lesson_end_date
            )

            schedule_events[get_event_hash(schedule_event)] = schedule_event

            if lesson_day_hash not in first_lesson_of_the_day_number:
                first_lesson_of_the_day_number[lesson_day_hash] = lesson_number

    return schedule_events


def sync_calendar_with_schedule(gc: GoogleCalendar, settings: Settings):
    current_date = datetime.now(timezone("Asia/Yekaterinburg"))
    date_of_first_september_week = get_date_of_first_september_week(current_date)

    gc_events = list(gc.get_events(time_min=date_of_first_september_week, timezone="Asia/Yekaterinburg"))

    schedule_events = get_schedule_events(
        date_of_first_september_week,
        settings.schedule_semester_id,
        settings.schedule_type,
        settings.student_group_or_teacher_id,
        settings.minutes_before_reminder_first_lesson,
        settings.minutes_before_reminder
    )

    for gc_event in gc_events:
        if get_event_hash(gc_event) not in schedule_events:
            gc.delete_event(gc_event, send_updates="all")
            print(f"Занятие удаленно — {format_event_as_string(gc_event)}")
            continue

        schedule_event = schedule_events[get_event_hash(gc_event)]

        is_event_updated = (gc_event.summary != schedule_event.summary or gc_event.description != schedule_event.description or gc_event.location != schedule_event.location or
                            gc_event.reminders != schedule_event.reminders)

        if is_event_updated:
            schedule_event.event_id = gc_event.event_id
            gc.update_event(schedule_event, send_updates="all")
            print(f"Занятие обновлено — {format_event_as_string(schedule_event)}")

        schedule_events.pop(get_event_hash(gc_event))

    for schedule_event in schedule_events.values():
        gc.add_event(schedule_event, send_updates="all")
        print(f"Занятие добавлено — {format_event_as_string(schedule_event)}")


def main():
    settings = Settings()

    gc = GoogleCalendar(settings.default_calendar, credentials_path="client_secret.json")

    sync_calendar_with_schedule(gc, settings)

    if settings.task_scheduler_delay == 0:
        return

    every(settings.task_scheduler_delay, sync_calendar_with_schedule, (gc, settings))


if __name__ == "__main__":
    main()
