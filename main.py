import requests
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


def parse_schedule(schedule_table, schedule_type: int):
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
        lesson_campus = lesson_classroom.split("-")[0]
        lesson_comment = lesson_columns[7].text

        for week in lesson_weeks:
            calendar_events.append(
                Event(
                    f'{get_lesson_num(lesson_start_end_time[0])}. {lesson_type} — {lesson_name}, {lesson_classroom}',
                    description=("<b>Преподаватель" if schedule_type == 1 else "<b>Группа") + f':</b> {lesson_teacher_or_student_group}\n' +
                                (f'<b>Комментарий:</b> {lesson_comment}\n' if lesson_comment != '' else '') +
                    f'<b>Дата добавления:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}',
                    minutes_before_popup_reminder=(60 if week + day_of_week in first_lesson else 20),
                    color_id=get_event_color(lesson_type),
                    location=(f'УГАТУ корпус {lesson_campus}' if lesson_campus.isnumeric() else ""),
                    timezone="Asia/Yekaterinburg",
                    start=get_date_from_schedule_api(int(week), day_of_week, lesson_start_end_time[0]),
                    end=get_date_from_schedule_api(int(week), day_of_week, lesson_start_end_time[1])
                )
            )
            first_lesson.add(week + day_of_week)

    return calendar_events


gc = GoogleCalendar('ПОЧТА', credentials_path="./client_secret.json")
gc.clear_calendar()

schedule_table = get_schedule_table(231, 1, student_group_id=2575)
schedule_events = parse_schedule(schedule_table, 1)

for schedule_event in schedule_events:
    gc.add_event(schedule_event)

