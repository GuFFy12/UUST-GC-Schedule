<div align="center">

# UGATU-Google-Calendar-Schedule
  
<img src="https://media.discordapp.net/attachments/959412635814756402/1157606686173958256/IMG_4167.png?ex=651938bd&is=6517e73d&hm=b8cf69a6ff9d5a0d49157d4ee3917ce69f196eabcfdc0bfb393af5e216510783&=" alt="logo" width="45%" />
<br> <br>

## Интеграция расписания УГАТУ в Google Календарь

Этот проект позволяет интегрировать расписание Уфимского Государственного Авиационного Технического Университета (УГАТУ) в ваш Google Календарь. Таким образом, вы сможете использовать это расписание с Apple, Siri и другими сервисами, поддерживающими Google Calendar API.

## Установка

</div>

1. Создайте новый проект в [Google Cloud Platform (GCP)](https://console.cloud.google.com/projectcreate).

2. Включите [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) в настройках проекта GCP. Для этого перейдите в "Enabled APIs & Services", затем "ENABLE APIS AND SERVICES" и найдите "Google Calendar API". Активируйте его.

3. Создайте информацию о согласии [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent) для вашего проекта. Перейдя в раздел "Scopes" нажмите "ADD OR REMOVE SCOPES" и добавьте первые три пункта (.../auth/userinfo.email, .../auth/userinfo.profile, openid), а также поиском найдите и выберите "Google Calendar API". В разделе "Test users" добавьте свою почту.

4. Перейдите в [Credentials](https://console.cloud.google.com/apis/credentials/oauthclient) и создайте учетные данные (OAuth client ID) для веб-приложения (Web application). В поле "Authorized redirect URIs" добавьте и укажите `http://localhost:8080/`. Скачайте файл JSON с учетными данными выбрав "DOWNLOAD JSON". Переименуйте его в `client_secret.json` и поместите его в корневую папку проекта.

5. Настройте файл `settings.ini` следующим образом:
   - `task_scheduler_delay`: Время ожидания в секундах перед следующим запуском проверки расписания (0 — отключить).
   - `default_calendar`: Ваш адрес электронной почты / ID вторичного календаря.
   - `schedule_semester_id`: ID текущего семестра.
   - `schedule_type`: 1 для расписания группы, 2 для расписания преподавателя.
   - `student_group_or_teacher_id`: ID группы (если `schedule_type` равен 1) / ID преподавателя (если `schedule_type` равен 2).
   - `minutes_before_popup_reminder_first_lesson`: За сколько минут перед началом первой пары отправлять уведомление.
   - `minutes_before_popup_reminder`: За сколько минут перед началом каждой последующей пары отправлять уведомление.
   
   P.S. Параметры `schedule_semester_id`, `student_group_or_teacher_id` можно достать, выбрав на сайте расписания свою группу, и посмотрев на финальную ссылку (Прим. `https://isu.ugatu.su/api/new_schedule_api/?schedule_semestr_id=ID&WhatShow=1&student_group_id=ID&weeks=0`)

6. Установите зависимости через консольную команду `pip install -r requirements.txt`.

7. Запустите скрипт `main.py`. На странице авторизации Google подтвердите доступ к вашему календарю.

8. Для работы скрипта в фоновом режиме можете использовать pm2. Пример: `pm2 start main.py --name UGCS --interpreter python3`.
