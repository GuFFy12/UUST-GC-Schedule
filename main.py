import requests
import configparser
import pytz
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar

# Utilities

def get_first_day_of_first_september_week(current_date: datetime):
    first_september = pytz.timezone('Asia/Yekaterinburg').localize(datetime(current_date.year, 9, 1))

    if current_date < first_september:  # Если следующий учебный год не наступил, то считаем что сейчас предыдущий год.
        first_september = datetime(current_date.year - 1, 9, 1)

    day_of_week = first_september.weekday()

    return first_september - timedelta(days=day_of_week)


def get_date_from_schedule(first_day_of_first_september_week: datetime, week: int, day_of_week: str, time: str):
    index_day_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"].index(day_of_week)
    hours, minutes = map(int, time.split(':'))

    return first_day_of_first_september_week + timedelta(weeks=week - 1, days=index_day_of_week, hours=hours, minutes=minutes)


def get_lesson_num(lesson_start_time: str):
    lesson_times = {
        "08:00": "1",
        "09:35": "2",
        "11:35": "3",
        "13:10": "4",
        "15:10": "5",
        "16:45": "6",
        "18:20": "7",
        "19:55": "8",
        "21:25": "9",
        "22:55": "10"
    }

    return lesson_times.get(lesson_start_time)


def get_event_color(lesson_type: str):
    event_colors = {
        'Лекция': '3',
        'Практика (семинар)': '6',
        'Лабораторная работа': '9',
        'Физвоспитание': '2',
        'Военная подготовка': '10',
        'Лекция + практика': '4',
        'Консультация': '7',
        'Экзамен': '11',
        'Консультация экзамена': '11',
        'Ликвидация задолженостей': '11',
        'Зачёт с оценкой': '11',
        'Зачёт': '11',
        'Защита (Курсовой/РГР/Лабораторной)': '11',
        'Лекция + практика + лабораторная работа': '1',
        'Мероприятие': '5',
        'Кураторский час': '5',
        'Прочее': '8',
    }

    return event_colors.get(lesson_type)


# Main Code

def get_schedule_events(schedule_semester_id: int, schedule_type: int, student_group_or_teacher_id: int,
                        minutes_before_popup_reminder_first_lesson=60, minutes_before_popup_reminder=10):
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
    lesson_rows = soup.find('tbody').findAll('tr')

    schedule_events = {}

    current_date = datetime.now(pytz.timezone('Asia/Yekaterinburg'))
    first_day_of_first_september_week = get_first_day_of_first_september_week(current_date)

    day_of_week = ""
    first_lesson = set()
    for lesson_row in lesson_rows:
        lesson_columns = lesson_row.findAll('td')

        if 'dayheader' in lesson_row['class']:
            day_of_week = lesson_columns[0].text

        if 'noinfo' in lesson_row['class']:
            continue

        lesson_start_time, lesson_end_time = lesson_columns[1].text.split("-")
        lesson_weeks = lesson_columns[2].text.split()
        lesson_name = lesson_columns[3].text
        lesson_type = lesson_columns[4].text
        lesson_teacher_or_student_group = lesson_columns[5].text
        lesson_classroom = lesson_columns[6].text
        lesson_comment = lesson_columns[7].text

        for week in lesson_weeks:
            lesson_end_date = get_date_from_schedule(first_day_of_first_september_week, int(week), day_of_week, lesson_end_time)
            if current_date > lesson_end_date:  # Не добавляем уже прошедшие занятия.
                first_lesson.add(week + day_of_week)
                continue

            lesson_start_date = get_date_from_schedule(first_day_of_first_september_week, int(week), day_of_week, lesson_start_time)

            schedule_events[lesson_start_date] = Event(
                    f'{get_lesson_num(lesson_start_time)}. {lesson_name} — {lesson_type}',
                    description=("Преподаватель" if schedule_type == 1 else "Группа") + f': {lesson_teacher_or_student_group}\n' +
                                (f'Комментарий: {lesson_comment}\n' if lesson_comment != '' else ''),
                    minutes_before_popup_reminder=(minutes_before_popup_reminder if week + day_of_week in first_lesson else minutes_before_popup_reminder_first_lesson),
                    color_id=get_event_color(lesson_type),
                    location=lesson_classroom,
                    timezone="Asia/Yekaterinburg",
                    start=lesson_start_date,
                    end=lesson_end_date
            )

            first_lesson.add(week + day_of_week)

    return schedule_events


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("settings.ini")

    gc = GoogleCalendar(config["Settings"]["default_calendar"], credentials_path="client_secret.json")
    gc_events = list(gc.get_events(timezone='Asia/Yekaterinburg'))

    schedule_events = get_schedule_events(
        int(config["Settings"]["schedule_semester_id"]),
        int(config["Settings"]["schedule_type"]),
        student_group_or_teacher_id=int(config["Settings"]["student_group_or_teacher_id"]),
        minutes_before_popup_reminder_first_lesson=int(config["Settings"]["minutes_before_popup_reminder_first_lesson"]),
        minutes_before_popup_reminder=int(config["Settings"]["minutes_before_popup_reminder"])
    )

    for gc_event in gc_events:
        if gc_event.start not in schedule_events:  # Если в календаре есть начало занятия, а в расписании нет, то считаем что пара удалена.
            gc.delete_event(gc_event, send_updates="all")
            print("Удалён —", gc_event)
            continue

        schedule_event = schedule_events[gc_event.start]

        is_event_updated = (gc_event.summary != schedule_event.summary or gc_event.description != schedule_event.description or gc_event.location != schedule_event.location or
                            gc_event.reminders != schedule_event.reminders)

        if is_event_updated:  # Если есть различия в расписании и календаре, обновляем событие.
            schedule_event.event_id = gc_event.event_id
            gc.update_event(schedule_event, send_updates="all")
            print("Обновлён —", gc_event, schedule_event)

        schedule_events.pop(gc_event.start)  # Обязательно удаляем из списка расписания занятия, которые уже были в календаре.

    for schedule_event in schedule_events.values():
        gc.add_event(schedule_event, send_updates="all")
        print("Добавлен —", schedule_event)
