import requests
import configparser
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar


def get_date_from_schedule_api(week: int, day_of_week: str, time: str):
    first_september = datetime(2023, 8, 28)
    index_day_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"].index(day_of_week)
    hours, minutes = map(int, time.split(':'))

    return first_september + timedelta(weeks=week - 1, days=index_day_of_week, hours=hours, minutes=minutes)


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

    return lesson_times.get(lesson_start_time, "Неизвестный номер пары")


def get_event_color(lesson_type: str):
    event_colors = {
        "Лекция": "3",
        "Практика (семинар)": "6",
        "Физвоспитание": "2",
        "Лабораторная работа": "9",
        "Военная подготовка": "10",
        "Мероприятие": "4"
    }

    return event_colors.get(lesson_type, "11")


def get_schedule_table(schedule_semester_id: int, schedule_type: int, student_group_id=0, teacher_id=0):
    params = {
        "schedule_semestr_id": schedule_semester_id,
        "WhatShow": schedule_type,
        "weeks": 0,
    }

    if schedule_type == 1:
        params["student_group_id"] = student_group_id
    elif schedule_type == 2:
        params["teacher"] = teacher_id

    response = requests.get("https://isu.ugatu.su/api/new_schedule_api/", params)
    soup = BeautifulSoup(response.text, "html.parser")

    return soup.find('tbody')


def parse_schedule(schedule_table, schedule_type: int, minutes_before_popup_reminder_first_lesson=60, minutes_before_popup_reminder=20):
    lesson_rows = schedule_table.findAll('tr')

    calendar_events = []

    day_of_week = ""
    first_lesson = set()
    for row in lesson_rows:
        lesson_columns = row.findAll('td')

        if 'dayheader' in row['class']:
            day_of_week = lesson_columns[0].text

        if 'noinfo' in row['class']:
            continue

        lesson_start_end_time = lesson_columns[1].text.split("-")
        lesson_weeks = lesson_columns[2].text.split()
        lesson_name = lesson_columns[3].text
        lesson_type = lesson_columns[4].text
        lesson_teacher_or_student_group = lesson_columns[5].text
        lesson_classroom = lesson_columns[6].text
        lesson_campus = lesson_classroom.split("-")
        lesson_comment = lesson_columns[7].text

        for week in lesson_weeks:
            calendar_events.append(
                Event(
                    f'{get_lesson_num(lesson_start_end_time[0])}. {lesson_name} — {lesson_type}, {lesson_classroom}',
                    description=("Преподаватель" if schedule_type == 1 else "Группа") + f': {lesson_teacher_or_student_group}\n' +
                                (f'Комментарий: {lesson_comment}\n' if lesson_comment != '' else '') +
                    f'Дата добавления: {datetime.now().strftime("%d.%m.%Y %H:%M")}',
                    minutes_before_popup_reminder=(minutes_before_popup_reminder if week + day_of_week in first_lesson else minutes_before_popup_reminder_first_lesson),
                    color_id=get_event_color(lesson_type),
                    location=(f'УГАТУ, Корпус {lesson_campus[0]}, Кабинет: {lesson_campus[1]}' if lesson_campus[0].isnumeric() else ""),
                    timezone="Asia/Yekaterinburg",
                    start=get_date_from_schedule_api(int(week), day_of_week, lesson_start_end_time[0]),
                    end=get_date_from_schedule_api(int(week), day_of_week, lesson_start_end_time[1])
                )
            )
            first_lesson.add(week + day_of_week)

    return calendar_events


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("settings.ini")

    gc = GoogleCalendar(config["Settings"]["default_calendar"], credentials_path="client_secret.json")
    gc.clear_calendar()

    schedule_table = get_schedule_table(
        int(config["Settings"]["schedule_semester_id"]),
        int(config["Settings"]["schedule_type"]),
        student_group_id=int(config["Settings"]["student_group_id"]),
        teacher_id=int(config["Settings"]["teacher_id"]),
    )
    schedule_events = parse_schedule(
        schedule_table,
        int(config["Settings"]["schedule_type"]),
        minutes_before_popup_reminder_first_lesson=int(config["Settings"]["minutes_before_popup_reminder_first_lesson"]),
        minutes_before_popup_reminder=int(config["Settings"]["minutes_before_popup_reminder"])
    )

    for schedule_event in schedule_events:
        gc.add_event(schedule_event)
