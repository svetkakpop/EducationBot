import os
import logging
import random
from dotenv import load_dotenv
import telebot
from telebot import types
import psycopg2
import redis

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация бота
bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

# ID чата поддержки
SUPPORT_CHAT_ID = int(os.getenv('SUPPORT_CHAT_ID', 1132159425))

# Состояния пользователей
user_states = {}
user_menu_messages = {}
user_course_positions = {
    'regular': {},
    'recommended': {}
}
# Для хранения состояния опроса подбора курсов
user_survey_state = {}
# Для хранения состояния обратной связи
user_feedback_state = {}
# Для хранения состояния оценки
user_rating_state = {}
# Для хранения выбора курса перед оценкой
user_selected_course_for_rating = {}
# Для хранения ФИО преподавателя перед оценкой
user_selected_teacher_for_rating = {}

# Для отслеживания что сейчас пользователь пишет ФИО
user_typing_teacher_name = {}

# Для хранения пользователей, которые пишут вопрос
users_waiting_for_question = {}

# Для связи вопросов и пользователей
pending_questions = {}

# Данные для опроса
# Данные для опроса
survey_questions = [
    {
        'question': '🎓 Кем вы являетесь?',
        'options': ['Студент', 'АУП', 'Руководство', 'ППС'],
        'key': 'role'
    },
    {
        'question': '📚 Какое направление вас интересует?',
        'options': ['Финансы', 'Управление', 'Педагогика'],
        'key': 'direction'
    },
    {
        'question': '⏱ Сколько времени у вас есть на обучение?',
        'options': ['1-4 недели', '5-8 недель', 'Более 8 недель'],
        'key': 'time'
    },
    {
        'question': '💰 Какой бюджет вы рассматриваете?',
        'options': ['До 10 000 руб.', '10-20 000 руб.', 'Более 20 000 руб.'],
        'key': 'budget'
    }
]

# База данных FAQ (вопросы и ответы)
# База данных FAQ (вопросы и ответы)
faq_data = {
    "Оплата": [
        {"question": "Какие способы оплаты доступны?",
         "answer": "Мы принимаем оплату банковскими картами (Visa, Mastercard, МИР), а также через PayPal."},
        {"question": "Есть ли рассрочка?",
         "answer": "Да, мы предоставляем рассрочку на 3 месяца для всех курсов стоимостью от 20 000 руб."},
        {"question": "Как получить чек?",
         "answer": "Чек приходит на вашу электронную почту сразу после оплаты. Если письма нет, проверьте папку 'Спам'."}
    ],
    "Запись на курс": [
        {"question": "Как записаться на курс?",
         "answer": "Выберите курс в каталоге и нажмите кнопку 'Записаться'. Вам придет инструкция на почту."},
        {"question": "Нужны ли документы для записи?",
         "answer": "Для большинства курсов достаточно паспорта. Для программ с выдачей сертификата может потребоваться диплом."},
        {"question": "Можно ли записаться по телефону?",
         "answer": "Да, звоните по номеру +7 (XXX) XXX-XX-XX с 9:00 до 18:00."}
    ],
    "Сроки": [
        {"question": "Когда начинается курс?",
         "answer": "Ближайший старт - 15 числа каждого месяца. Точная дата указана на странице курса."},
        {"question": "Можно ли продлить доступ?",
         "answer": "Да, доступ можно продлить за дополнительную плату (10% от стоимости курса за месяц)."},
        {"question": "Сколько длится курс?",
         "answer": "Длительность указана на странице каждого курса. Обычно от 4 до 12 недель."}
    ],
    "Техподдержка": [
        {"question": "Не работает личный кабинет",
         "answer": "Очистите кеш браузера или попробуйте зайти с другого устройства. Если проблема сохраняется, напишите на support@example.com."},
        {"question": "Не приходят письма",
         "answer": "Проверьте папку 'Спам'. Добавьте наш email в контакты. Если проблема не решена, свяжитесь с техподдержкой."},
        {"question": "Как сменить пароль?",
         "answer": "На странице входа нажмите 'Забыли пароль?' и следуйте инструкциям."}
    ]
}

# Подключение к Redis
redis_conn = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=6379,
    db=0,
    decode_responses=True
)

def get_db_connection():
    """Устанавливает соединение с PostgreSQL"""
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST')
    )

def save_user(telegram_id, username, full_name, position=None):
    """Сохраняет пользователя в базу данных"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (telegram_id, username, full_name, position)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (telegram_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        full_name = EXCLUDED.full_name,
                        position = COALESCE(users.position, EXCLUDED.position),
                        last_activity = CURRENT_TIMESTAMP""",
                    (telegram_id, username, full_name, position)
                )
                conn.commit()
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")

def get_user_position(telegram_id):
    """Получает должность пользователя"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT position FROM users WHERE telegram_id = %s",
                    (telegram_id,)
                )
                result = cur.fetchone()
                return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка получения должности: {e}")
        return None

def get_courses_by_category(category_name):
    """Получает курсы по категории из базы данных"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Определяем тип запроса в зависимости от категории
                if category_name in ['finance', 'management', 'pedagogy']:
                    cur.execute("""
                        SELECT title, description, duration, price, url, access, 
                               direction as category, direction
                        FROM courses 
                        WHERE direction = %s
                        ORDER BY title
                    """, (category_name,))
                elif category_name in ['pps', 'aup', 'guide', 'students']:
                    role_map = {
                        'pps': 'ППС',
                        'aup': 'АУП',
                        'guide': 'Руководство',
                        'students': 'Студент'
                    }
                    cur.execute("""
                        SELECT title, description, duration, price, url, access, 
                               role as category, direction
                        FROM courses 
                        WHERE role = %s
                        ORDER BY title
                    """, (role_map[category_name],))
                elif category_name in ['open', 'limited']:
                    cur.execute("""
                        SELECT title, description, duration, price, url, access, 
                               access as category, direction
                        FROM courses 
                        WHERE access = %s
                        ORDER BY title
                    """, (category_name,))
                else:
                    return []
                
                courses = cur.fetchall()
                return [{
                    'title': c[0],
                    'description': c[1],
                    'duration': c[2],
                    'price': c[3],
                    'url': c[4],
                    'access': c[5],
                    'category': c[6],
                    'direction': c[7],
                    'week': f"{c[2]} недель" if c[2] else "Не указано"
                } for c in courses]
    except Exception as e:
        logger.error(f"Ошибка при получении курсов: {e}")
        return []
         
def get_all_courses():
    """Получает все курсы"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.title, c.description, c.duration, c.price, c.url, cc.name as category
                    FROM courses c
                    JOIN course_categories cc ON c.category_id = cc.category_id
                    ORDER BY c.title"""
                )
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения всех курсов: {e}")
        return []

def save_rating(user_id, rating_type, target, rating):
    """Сохраняет оценку в базу"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ratings (user_id, rating_type, target, rating)
                    VALUES (%s, %s, %s, %s)""",
                    (user_id, rating_type, target, rating)
                )
                conn.commit()
    except Exception as e:
        logger.error(f"Ошибка сохранения оценки: {e}")

def filter_courses_by_direction(direction):
    """Фильтрует курсы по направлению"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.title, c.description, c.duration, c.price, c.url, cc.name as category
                    FROM courses c
                    JOIN course_categories cc ON c.category_id = cc.category_id
                    WHERE cc.name = %s
                    ORDER BY c.title""",
                    (direction.lower(),)
                )
                courses = cur.fetchall()
                return [{
                    'title': c[0],
                    'description': c[1],
                    'duration': c[2],
                    'price': c[3],
                    'url': c[4],
                    'direction': direction.lower(),
                    'week': f"{c[2]} недель" if c[2] else "Не указано",
                    'access': 'open'  # По умолчанию, можно добавить поле в БД
                } for c in courses]
    except Exception as e:
        logger.error(f"Ошибка фильтрации курсов по направлению: {e}")
        return []

def filter_courses_by_access(access):
    """Фильтрует курсы по доступности"""
    try:
        # Временное решение, пока не добавлено поле доступности в БД
        all_courses = get_all_courses()
        return [{
            'title': c[0],
            'description': c[1],
            'duration': c[2],
            'price': c[3],
            'url': c[4],
            'access': 'open' if random.random() > 0.5 else 'limited',  # Временное решение
            'week': f"{c[2]} недель" if c[2] else "Не указано"
        } for c in all_courses if access == 'open' or random.random() > 0.7]  # Фильтрация
    except Exception as e:
        logger.error(f"Ошибка фильтрации курсов по доступности: {e}")
        return []
def show_main_menu(user_id, edit_message_id=None):
    """Показывает главное меню с кнопками в столбик"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Добавляем все кнопки по одной в столбик
    keyboard.add(types.InlineKeyboardButton('Каталог курсов', callback_data='catalog'))
    keyboard.add(types.InlineKeyboardButton('Частные вопросы', callback_data='questions'))
    keyboard.add(types.InlineKeyboardButton('Подобрать курс', callback_data='courses'))
    keyboard.add(types.InlineKeyboardButton('Обратная связь', callback_data='feedback'))
    
    try:
        if edit_message_id:
            msg = bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text='Выберите, что Вам нужно:',
                reply_markup=keyboard
            )
        else:
            msg = bot.send_message(
                user_id,
                text='Выберите, что Вам нужно:',
                reply_markup=keyboard
            )
        user_menu_messages[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка отображения главного меню: {e}")
        
def show_direction_menu(user_id, edit_message_id=None):
    """Показывает меню выбора направления (в столбик)"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Кнопки направлений (каждая в отдельный ряд)
    keyboard.add(types.InlineKeyboardButton('Финансы', callback_data='finance'))
    keyboard.add(types.InlineKeyboardButton('Управление', callback_data='management'))
    keyboard.add(types.InlineKeyboardButton('Педагогика', callback_data='pedagogy'))
    
    # Кнопки навигации
    keyboard.add(types.InlineKeyboardButton('🔙 Назад', callback_data='catalog'))
    keyboard.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
    
    send_or_edit_message(
        user_id=user_id,
        text="Выберите направление обучения:",
        reply_markup=keyboard,
        edit_message_id=edit_message_id
    )

def show_post_menu(user_id, edit_message_id=None):
    """Показывает меню выбора должности (в столбик)"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Кнопки должностей (каждая в отдельный ряд)
    keyboard.add(types.InlineKeyboardButton('ППС', callback_data='pps'))
    keyboard.add(types.InlineKeyboardButton('АУП', callback_data='aup'))
    keyboard.add(types.InlineKeyboardButton('Руководство', callback_data='guide'))
    keyboard.add(types.InlineKeyboardButton('Студенты', callback_data='students'))
    
    # Кнопки навигации
    keyboard.add(types.InlineKeyboardButton('🔙 Назад', callback_data='catalog'))
    keyboard.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
    
    send_or_edit_message(
        user_id=user_id,
        text="Выберите вашу должность:",
        reply_markup=keyboard,
        edit_message_id=edit_message_id
    )

def send_or_edit_message(user_id, text, reply_markup, edit_message_id=None):
    """Универсальная функция для отправки/редактирования сообщения"""
    try:
        if edit_message_id:
            msg = bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text=text,
                reply_markup=reply_markup
            )
        else:
            msg = bot.send_message(
                user_id,
                text=text,
                reply_markup=reply_markup
            )
        user_menu_messages[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {str(e)}")
def show_course(user_id, course_type, course_index=0, edit_message_id=None):
    """Показывает курс с возможностью листания"""
    try:
        # Получаем курсы по типу (направление/должность/доступность)
        courses = get_courses_by_category(course_type)
        
        if not courses:
            bot.send_message(user_id, "😕 Курсы не найдены")
            return

        # Обеспечиваем корректный индекс (циклическая навигация)
        course_index = course_index % len(courses)
        course = courses[course_index]

        # Сохраняем текущую позицию для навигации
        if 'regular' not in user_course_positions:
            user_course_positions['regular'] = {}
        user_course_positions['regular'][user_id] = {
            'courses': courses,
            'position': course_index,
            'filter_value': course_type
        }

        # Формируем текст сообщения
        message_text = f"""<b>{course['title']}</b>

{course['description']}

📌 Категория: {course.get('category', 'Не указано')}
⏱ Длительность: {course.get('week', 'Не указано')}
💵 Стоимость: {course['price']:,} руб.
🔐 Доступность: {'Открытый' if course['access'] == 'open' else 'Закрытый'}"""

        # Создаем клавиатуру с кнопками навигации
        keyboard = types.InlineKeyboardMarkup()
        
        # Добавляем кнопки навигации только если курсов больше одного
        if len(courses) > 1:
            keyboard.row(
                types.InlineKeyboardButton("⬅️", callback_data=f'course_prev_{course_type}_{course_index}'),
                types.InlineKeyboardButton(f"{course_index + 1}/{len(courses)}", callback_data='none'),
                types.InlineKeyboardButton("➡️", callback_data=f'course_next_{course_type}_{course_index}')
            )

        # Добавляем кнопку для перехода на сайт курса (если есть URL)
        if course.get('url'):
            keyboard.add(types.InlineKeyboardButton("🌐 Перейти на сайт курса", url=course['url']))

        # Определяем действие для кнопки "Назад"
        back_action = {
            'finance': 'direction',
            'management': 'direction',
            'pedagogy': 'direction',
            'pps': 'post',
            'aup': 'post',
            'guide': 'post',
            'students': 'post',
            'open': 'availability',
            'limited': 'availability'
        }.get(course_type, 'catalog')

        # Добавляем кнопки навигации
        keyboard.row(
            types.InlineKeyboardButton("🔙 Назад", callback_data=back_action),
            types.InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')
        )

        # Отправляем или редактируем сообщение
        if edit_message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            msg = bot.send_message(
                user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            user_menu_messages[user_id] = msg.message_id

    except Exception as e:
        logger.error(f"Ошибка при показе курса: {e}")
        bot.send_message(user_id, "⚠️ Произошла ошибка при загрузке курса")

def show_availability_menu(user_id, edit_message_id=None):
    """Показывает меню выбора доступности (в столбик)"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Кнопки доступности
    keyboard.add(types.InlineKeyboardButton('Открытые программы', callback_data='open'))
    keyboard.add(types.InlineKeyboardButton('Ограниченные программы', callback_data='limited'))
    
    # Кнопки навигации
    keyboard.add(types.InlineKeyboardButton('🔙 Назад', callback_data='catalog'))
    keyboard.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
    
    send_or_edit_message(
        user_id=user_id,
        text="Программы какой доступности вас интересуют?",
        reply_markup=keyboard,
        edit_message_id=edit_message_id
    )

def show_faq_topics(user_id, edit_message_id=None):
    """Показывает темы FAQ"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Добавляем кнопки для каждой темы FAQ
    for topic in faq_data.keys():
        keyboard.add(types.InlineKeyboardButton(text=topic, callback_data=f'faq_topic_{topic}'))
    
    keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data='main_menu'))

    try:
        if edit_message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text="Выберите тему вопроса:",
                reply_markup=keyboard
            )
        else:
            msg = bot.send_message(
                user_id,
                text="Выберите тему вопроса:",
                reply_markup=keyboard
            )
            user_menu_messages[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отображении тем FAQ: {e}")

def show_faq_questions(user_id, topic, edit_message_id=None):
    """Показывает вопросы по выбранной теме"""
    if topic not in faq_data:
        bot.send_message(user_id, "❌ Тема не найдена")
        return
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Добавляем кнопки для каждого вопроса в теме
    for i, item in enumerate(faq_data[topic]):
        keyboard.add(types.InlineKeyboardButton(
            text=item["question"],
            callback_data=f'faq_item_{topic}_{i}'
        ))
    
    # Кнопки навигации
    keyboard.row(
        types.InlineKeyboardButton(text="🔙 Назад к темам", callback_data='questions'),
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data='main_menu')
    )

    try:
        if edit_message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text=f"Вопросы по теме '{topic}':",
                reply_markup=keyboard
            )
        else:
            msg = bot.send_message(
                user_id,
                text=f"Вопросы по теме '{topic}':",
                reply_markup=keyboard
            )
            user_menu_messages[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отображении вопросов FAQ: {e}")

def show_faq_answer(user_id, topic, question_index, edit_message_id=None):
    """Показывает ответ на выбранный вопрос"""
    try:
        question_data = faq_data[topic][question_index]
    except (KeyError, IndexError):
        bot.send_message(user_id, "❌ Вопрос не найден")
        return
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data=f'faq_topic_{topic}'),
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data='main_menu')
    )

    answer_text = f"<b>Вопрос:</b> {question_data['question']}\n\n<b>Ответ:</b> {question_data['answer']}"

    try:
        if edit_message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text=answer_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            msg = bot.send_message(
                user_id,
                text=answer_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            user_menu_messages[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отображении ответа FAQ: {e}")

def start_course_survey(user_id):
    """Начинает опрос для подбора курса"""
    user_survey_state[user_id] = {
        'current_question': 0,
        'answers': {},
        'message_id': None
    }
    ask_survey_question(user_id)

def ask_survey_question(user_id):
    """Задает вопрос из опроса"""
    state = user_survey_state.get(user_id)
    if not state or state['current_question'] >= len(survey_questions):
        return

    question_data = survey_questions[state['current_question']]
    keyboard = types.InlineKeyboardMarkup()

    for option in question_data['options']:
        clean_option = option.replace(' ', '_').replace(',', '')
        callback_data = f"survey_{state['current_question']}_{clean_option}"
        keyboard.add(types.InlineKeyboardButton(text=option, callback_data=callback_data))

    row_buttons = []
    if state['current_question'] > 0:
        row_buttons.append(types.InlineKeyboardButton(text="🔙 Назад", callback_data="survey_back"))
    row_buttons.append(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="survey_main_menu"))
    keyboard.row(*row_buttons)

    try:
        if state['message_id']:
            msg = bot.edit_message_text(
                chat_id=user_id,
                message_id=state['message_id'],
                text=question_data['question'],
                reply_markup=keyboard
            )
        else:
            msg = bot.send_message(user_id, question_data['question'], reply_markup=keyboard)
            state['message_id'] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отправке вопроса: {e}")

def process_survey_answer(user_id, question_index, answer):
    """Обрабатывает ответ на вопрос опроса"""
    state = user_survey_state.get(user_id)
    if not state:
        return

    question_data = survey_questions[question_index]
    state['answers'][question_data['key']] = answer
    state['current_question'] += 1

    if state['current_question'] < len(survey_questions):
        ask_survey_question(user_id)
    else:
        try:
            bot.delete_message(user_id, state['message_id'])
        except:
            pass

        # Фильтрация курсов
        filtered_courses = []

        # Фильтр по роли
        role_map = {
            'Студент': 'students',
            'АУП': 'aup',
            'Руководство': 'guide',
            'ППС': 'pps'
        }
        role = role_map.get(state['answers'].get('role'))
        if role:
            role_courses = get_courses_by_category(role)
            filtered_courses.extend(role_courses)

        # Фильтр по направлению (если выбрано)
        selected_direction = state['answers'].get('direction')
        if selected_direction:
            # Преобразование выбранного направления в ключ курса
            direction_mapping = {
                'Финансы': 'finance',
                'Управление': 'management',
                'Педагогика': 'pedagogy'
            }
            target_direction = direction_mapping.get(selected_direction)
            # Фильтрация по полю direction в курсах
            filtered_courses = [c for c in filtered_courses if c.get('direction') == target_direction]

        # Фильтр по бюджету
        budget_filter = {
            'До 10 000 руб.': lambda x: x <= 10000,
            '10-20 000 руб.': lambda x: 10000 < x <= 20000,
            'Более 20 000 руб.': lambda x: x > 20000
        }
        budget_func = budget_filter.get(state['answers'].get('budget'), lambda x: True)
        filtered_courses = [c for c in filtered_courses if budget_func(c['price'])]

        # Фильтр по длительности
        duration_preference = state['answers'].get('time')
        duration_filter = {
            '1-4 недели': lambda x: x <= 4,
            '5-8 недель': lambda x: 5 <= x <= 8,
            'Более 8 недель': lambda x: x > 8
        }.get(duration_preference, lambda x: True)
        filtered_courses = [c for c in filtered_courses if duration_filter(c['duration'])]

        # Удаление дубликатов
        seen = set()
        unique_courses = []
        for c in filtered_courses:
            if c['title'] not in seen:
                seen.add(c['title'])
                unique_courses.append(c)

        # Сохраняем рекомендации
        user_course_positions['recommended'][user_id] = {
            'courses': unique_courses,
            'position': 0,
            'saved_answers': state['answers'].copy(),
            'saved_question': len(survey_questions) - 1
        }

        if unique_courses:
            show_recommended_course(user_id, course_index=0)
        else:
            bot.send_message(user_id, "😕 По вашим критериям не найдено подходящих курсов")
            show_main_menu(user_id)

        del user_survey_state[user_id]

def show_recommended_course(user_id, course_index, edit_message_id=None):
    """Показывает рекомендованный курс"""
    if user_id not in user_course_positions['recommended']:
        return

    current_state = user_course_positions['recommended'][user_id]
    courses = current_state['courses']
    total_courses = len(courses)

    # Обеспечиваем циклическую навигацию
    course_index = course_index % total_courses
    current_state['position'] = course_index
    course = courses[course_index]

    keyboard = types.InlineKeyboardMarkup()

    if total_courses > 1:
        keyboard.row(
            types.InlineKeyboardButton("⬅️", callback_data='recommended_prev'),
            types.InlineKeyboardButton(f"{course_index + 1}/{total_courses}", callback_data='none'),
            types.InlineKeyboardButton("➡️", callback_data='recommended_next')
        )

    if course.get('url'):
        keyboard.add(types.InlineKeyboardButton("🌐 Перейти на сайт курса", url=course['url']))

    # Кнопки навигации (в столбик)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад к опросу", callback_data='recommended_back'))
    keyboard.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu'))

    message_text = f"""🎉 <b>Рекомендованный курс</b> 🎉

<b>{course['title']}</b>
{course['description']}

⏱ Длительность: {course.get('week', 'Не указано')}
💵 Стоимость: {course.get('price', 0):,} руб.
🔐 Доступность: {'Открытый' if course.get('access') == 'open' else 'Закрытый'}"""

    try:
        if edit_message_id:
            msg = bot.edit_message_text(
                chat_id=user_id,
                message_id=edit_message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            msg = bot.send_message(
                user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            current_state['message_id'] = msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отображении курса: {e}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Обработчик команды /start"""
    user = message.from_user
    save_user(user.id, user.username, f"{user.first_name} {user.last_name or ''}")
    bot.send_message(message.chat.id, "Напишите 'Привет' для начала работы с ботом")

@bot.callback_query_handler(func=lambda call: call.data.startswith('course_prev_'))
def handle_course_prev(call):
    """Обрабатывает кнопку 'Назад' в листании курсов"""
    try:
        parts = call.data.split('_')
        if len(parts) >= 4:
            course_type = parts[2]
            current_index = int(parts[3])
            show_course(call.from_user.id, course_type, current_index - 1, call.message.message_id)
    except Exception as e:
        logger.error(f"Ошибка в обработке course_prev: {e}")
    finally:
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'catalog')
def handle_catalog(call):
    """Показывает меню каталога (в столбик)"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Кнопки фильтрации (каждая в отдельный ряд)
    keyboard.add(types.InlineKeyboardButton('Направление обучения', callback_data='direction'))
    keyboard.add(types.InlineKeyboardButton('Должность', callback_data='post'))
    keyboard.add(types.InlineKeyboardButton('Доступность', callback_data='availability'))
    
    # Кнопка главного меню
    keyboard.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
    
    try:
        bot.edit_message_text(
            chat_id=call.from_user.id,
            message_id=call.message.message_id,
            text="Выберите критерий для подбора курсов:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка отображения каталога: {e}")
    finally:
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ['direction', 'post', 'availability'])
def handle_back_to_menus(call):
    """Обрабатывает кнопки возврата в меню"""
    if call.data == 'direction':
        show_direction_menu(call.from_user.id, call.message.message_id)
    elif call.data == 'post':
        show_post_menu(call.from_user.id, call.message.message_id)
    elif call.data == 'availability':
        show_availability_menu(call.from_user.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('course_next_'))
def handle_course_next(call):
    """Обрабатывает кнопку 'Вперед' в листании курсов"""
    try:
        parts = call.data.split('_')
        if len(parts) >= 4:
            course_type = parts[2]
            current_index = int(parts[3])
            show_course(call.from_user.id, course_type, current_index + 1, call.message.message_id)
    except Exception as e:
        logger.error(f"Ошибка в обработке course_next: {e}")
    finally:
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('faq_topic_'))
def handle_faq_topic(call):
    """Обрабатывает выбор темы FAQ"""
    topic = call.data.split('_', 2)[2]  # Получаем тему из callback_data
    show_faq_questions(call.from_user.id, topic, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('faq_item_'))
def handle_faq_item(call):
    """Обрабатывает выбор конкретного вопроса FAQ"""
    parts = call.data.split('_')
    if len(parts) == 4:  # faq_item_{topic}_{index}
        topic = parts[2]
        question_index = int(parts[3])
        show_faq_answer(call.from_user.id, topic, question_index, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "questions")
def handle_questions_callback(call):
    """Обрабатывает нажатие на кнопку 'Частные вопросы'"""
    show_faq_topics(call.from_user.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'main_menu')
def handle_main_menu(call):
    """Обрабатывает кнопку 'Главное меню'"""
    try:
        # Очищаем состояние опроса, если есть
        if call.from_user.id in user_survey_state:
            del user_survey_state[call.from_user.id]
        
        # Очищаем состояние рекомендованных курсов
        if call.from_user.id in user_course_positions['recommended']:
            del user_course_positions['recommended'][call.from_user.id]
        
        show_main_menu(call.from_user.id)
    except Exception as e:
        logger.error(f"Ошибка обработки главного меню: {e}")
    finally:
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: users_waiting_for_question.get(message.chat.id))
def handle_user_question(message):
    """Обрабатывает вопрос пользователя"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text

    users_waiting_for_question.pop(chat_id, None)

    sent = bot.send_message(
        SUPPORT_CHAT_ID,
        f"📩 Новый вопрос от пользователя @{message.from_user.username or 'Без ника'} :\n\n{text}\n\n"
        f"Ответьте на это сообщение для ответа пользователю."
    )

    pending_questions[sent.message_id] = {
        "chat_id": chat_id,
        "question_text": text
    }

    bot.send_message(chat_id, "✅ Ваш вопрос отправлен. Спасибо! Мы скоро ответим вам.")
    show_main_menu(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "courses")
def handle_courses_callback(call):
    """Обрабатывает нажатие на кнопку 'Подобрать курс'"""
    start_course_survey(call.from_user.id)

@bot.message_handler(func=lambda message: message.reply_to_message is not None and message.chat.id == SUPPORT_CHAT_ID)
def handle_support_response(message):
    """Обрабатывает ответ поддержки"""
    reply_to = message.reply_to_message

    if reply_to and reply_to.message_id in pending_questions:
        user_data = pending_questions[reply_to.message_id]
        user_chat_id = user_data["chat_id"]
        original_question = user_data["question_text"]

        # Отправляем ответ пользователю
        bot.send_message(
            user_chat_id,
            f"🔔 Ответ от поддержки:\n\n<b>{message.text}</b>\n\n"
            f"На ваш вопрос:\n<b>{original_question}</b>",
            parse_mode="HTML"
        )

        show_main_menu(user_chat_id)

        bot.send_message(SUPPORT_CHAT_ID, "✅ Ответ отправлен пользователю.")
        pending_questions.pop(reply_to.message_id, None)
    else:
        bot.send_message(SUPPORT_CHAT_ID, "❌ Не удалось определить пользователя для ответа.")

@bot.message_handler(func=lambda message: user_typing_teacher_name.get(message.chat.id))
def handle_teacher_name_input(message):
    """Обрабатывает ввод ФИО преподавателя"""
    chat_id = message.chat.id
    full_name = message.text.strip()

    if not full_name:
        bot.send_message(chat_id, "❗ Пожалуйста, введите корректное имя.")
        return

    user_selected_teacher_for_rating[chat_id] = full_name
    user_typing_teacher_name.pop(chat_id, None)

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(text="⭐ 1", callback_data="rating_teacher_1"),
        types.InlineKeyboardButton(text="⭐ 2", callback_data="rating_teacher_2"),
        types.InlineKeyboardButton(text="⭐ 3", callback_data="rating_teacher_3"),
        types.InlineKeyboardButton(text="⭐ 4", callback_data="rating_teacher_4"),
        types.InlineKeyboardButton(text="⭐ 5", callback_data="rating_teacher_5")
    )
    keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

    bot.send_message(
        chat_id,
        f"Теперь поставьте оценку преподавателю:\n<b>{full_name}</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    """Обрабатывает текстовые сообщения"""
    if message.text.lower() == "привет":
        user = message.from_user
        save_user(user.id, user.username, f"{user.first_name} {user.last_name or ''}")
        bot.send_message(message.from_user.id, "Привет! Я Учёный помощник, помогу тебе разобраться с обучением.")
        show_main_menu(message.from_user.id)
    elif message.text == "/help":
        bot.send_message(message.from_user.id, "Напиши Привет")
    else:
        bot.send_message(message.from_user.id, "Привет! Я Учёный помощник, помогу тебе разобраться с обучением.")
        show_main_menu(message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == 'none')
def handle_none(call):
    """Обрабатывает пустые callback'и"""
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('recommended_'))
def handle_recommended_navigation(call):
    """Обрабатывает навигацию по рекомендованным курсам"""
    user_id = call.from_user.id
    if user_id not in user_course_positions['recommended']:
        bot.answer_callback_query(call.id)
        return

    action = call.data.split('_')[1]
    current_state = user_course_positions['recommended'][user_id]

    if action == 'back':
        # Восстанавливаем состояние опроса
        state = {
            'answers': current_state.get('saved_answers', {}),
            'current_question': current_state.get('saved_question', 0),
            'message_id': call.message.message_id
        }
        user_survey_state[user_id] = state

        # Возвращаемся к опросу
        ask_survey_question(user_id)
    else:
        # Обработка навигации по курсам
        current_pos = current_state['position']
        total = len(current_state['courses'])

        if action == 'prev':
            new_pos = (current_pos - 1) % total
        elif action == 'next':
            new_pos = (current_pos + 1) % total
        else:
            bot.answer_callback_query(call.id)
            return

        show_recommended_course(user_id, new_pos, call.message.message_id)

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    """Обработчик callback-запросов"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    logger.info(f"Received callback: {call.data}")

    if call.data == "main_menu":
        show_main_menu(chat_id, user_menu_messages.get(chat_id))

    elif call.data == "questions":
        show_faq_topics(chat_id, message_id)

    elif call.data.startswith("faq_answer_"):
        parts = call.data.split('_')
        topic = parts[2]
        question_index = int(parts[3])
        show_faq_answer(chat_id, topic, question_index, message_id)

    elif call.data == "courses":
        start_course_survey(chat_id)

    elif call.data == "survey_back":
        state = user_survey_state.get(chat_id)
        if state and state['current_question'] > 0:
            state['current_question'] -= 1
            prev_question_key = survey_questions[state['current_question']]['key']

            if prev_question_key in state['answers']:
                del state['answers'][prev_question_key]

            ask_survey_question(chat_id)

    elif call.data == "survey_main_menu":
        if chat_id in user_survey_state:
            try:
                bot.delete_message(chat_id, user_survey_state[chat_id]['message_id'])
            except:
                pass

            del user_survey_state[chat_id]
        show_main_menu(chat_id)

    elif call.data.startswith("survey_"):
        parts = call.data.split('_')
        if len(parts) >= 3 and parts[0] == "survey":
            try:
                question_index = int(parts[1])
                answer = '_'.join(parts[2:]).replace('_', ' ')
                process_survey_answer(chat_id, question_index, answer)
            except ValueError:
                pass

    elif call.data == "catalog":
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton('Направление обучения', callback_data='direction'),
            types.InlineKeyboardButton('Должность', callback_data='post'),
            types.InlineKeyboardButton('Доступность', callback_data='availability'),
            types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu')
        )

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Выберите по какому критерию фильтровать доступные курсы:",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Выберите по какому критерию фильтровать доступные курсы:", reply_markup=keyboard)

    elif call.data == "availability":
        show_availability_menu(chat_id, message_id)
        
    elif call.data == "direction":
        keyboard = types.InlineKeyboardMarkup()
        key_finance = types.InlineKeyboardButton(text='Финансы', callback_data='finance')
        key_management = types.InlineKeyboardButton(text='Управление', callback_data='management')
        key_pedagogy = types.InlineKeyboardButton(text='Педагогика', callback_data='pedagogy')
        key_back = types.InlineKeyboardButton(text='🔙 Назад', callback_data='catalog')
        key_main = types.InlineKeyboardButton(text='Главное меню', callback_data='main_menu')

        keyboard.add(key_finance)
        keyboard.add(key_management)
        keyboard.add(key_pedagogy)
        keyboard.add(key_back)
        keyboard.add(key_main)

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Какое направление обучения Вас интересует?",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Какое направление обучения Вас интересует?", reply_markup=keyboard)

    elif call.data == "post":
        keyboard = types.InlineKeyboardMarkup()
        key_pps = types.InlineKeyboardButton(text='ППС', callback_data='pps')
        key_aup = types.InlineKeyboardButton(text='АУП', callback_data='aup')
        key_guide = types.InlineKeyboardButton(text='Руководство', callback_data='guide')
        key_students = types.InlineKeyboardButton(text='Студенты', callback_data='students')
        key_back = types.InlineKeyboardButton(text='🔙 Назад', callback_data='catalog')
        key_main = types.InlineKeyboardButton(text='Главное меню', callback_data='main_menu')

        keyboard.add(key_pps)
        keyboard.add(key_aup)
        keyboard.add(key_guide)
        keyboard.add(key_students)
        keyboard.add(key_back)
        keyboard.add(key_main)

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Какая должность Вас интересует?",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Какая должность Вас интересует?", reply_markup=keyboard)

    elif call.data == "availability":
        keyboard = types.InlineKeyboardMarkup()
        key_open_programs = types.InlineKeyboardButton(text='Открытые программы', callback_data='open')
        key_limited_programs = types.InlineKeyboardButton(text='Ограниченные программы', callback_data='limited')
        key_back = types.InlineKeyboardButton(text='🔙 Назад', callback_data='catalog')
        key_main = types.InlineKeyboardButton(text='Главное меню', callback_data='main_menu')

        keyboard.add(key_open_programs)
        keyboard.add(key_limited_programs)
        keyboard.add(key_back)
        keyboard.add(key_main)

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Программы какой доступности Вас интересуют?",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Программы какой доступности Вас интересуют?", reply_markup=keyboard)

    elif call.data in ['finance', 'management', 'pedagogy', 'pps', 'aup', 'guide', 'students', 'open', 'limited']:
        show_course(chat_id, call.data, edit_message_id=message_id)

    elif call.data == "feedback":
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="✍️ Контактные данные кураторов", callback_data="contact_information"))
        keyboard.add(types.InlineKeyboardButton(text="⭐ Оценить курсы и преподавателей", callback_data="rate"))
        keyboard.add(types.InlineKeyboardButton(text="✍️ Задать вопрос", callback_data="ask_question"))
        keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
        
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Свяжитесь с кураторами или задайте свой вопрос:",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Свяжитесь с кураторами или задайте свой вопрос:", reply_markup=keyboard)

    elif call.data == "ask_question":
        users_waiting_for_question[chat_id] = True
        bot.send_message(chat_id, "✍️ Пожалуйста, напишите свой вопрос. Мы ответим как можно скорее!")

    elif call.data == "rate":
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="📚 Оценить курс", callback_data="rate_course"))
        keyboard.add(types.InlineKeyboardButton(text="🎓 Оценить преподавателя", callback_data="rate_teacher"))
        keyboard.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="feedback"))
        keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Что вы хотите оценить?",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Что вы хотите оценить?", reply_markup=keyboard)

    elif call.data == "rate_course":
        all_courses = get_all_courses()
        keyboard = types.InlineKeyboardMarkup()

        for idx, course in enumerate(all_courses[:10]):  # Ограничиваем показ первыми 10 курсами
            keyboard.add(types.InlineKeyboardButton(text=course[0], callback_data=f"select_course_{idx}"))

        keyboard.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="rate"))
        keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Выберите курс для оценки:",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Выберите курс для оценки:", reply_markup=keyboard)

    elif call.data.startswith("select_course_"):
        course_idx = int(call.data.split("_")[2])
        all_courses = get_all_courses()
        selected_course = all_courses[course_idx]
        user_selected_course_for_rating[chat_id] = selected_course[0]

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(text="⭐ 1", callback_data="rating_course_1"),
            types.InlineKeyboardButton(text="⭐ 2", callback_data="rating_course_2"),
            types.InlineKeyboardButton(text="⭐ 3", callback_data="rating_course_3"),
            types.InlineKeyboardButton(text="⭐ 4", callback_data="rating_course_4"),
            types.InlineKeyboardButton(text="⭐ 5", callback_data="rating_course_5")
        )
        keyboard.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="rate_course"))
        keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Вы выбрали курс:\n<b>{selected_course[0]}</b>\n\nТеперь поставьте ему оценку:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except:
            bot.send_message(
                chat_id,
                f"Вы выбрали курс:\n<b>{selected_course[0]}</b>\n\nТеперь поставьте ему оценку:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    elif call.data.startswith("rating_course_"):
        rating = int(call.data.split("_")[2])
        course_title = user_selected_course_for_rating.get(chat_id, "Неизвестный курс")

        # Сохраняем оценку в базу данных
        save_rating(chat_id, 'course', course_title, rating)

        bot.send_message(chat_id, "✅ Спасибо за вашу оценку!")
        user_selected_course_for_rating.pop(chat_id, None)
        show_main_menu(chat_id)

    elif call.data == "rate_teacher":
        user_typing_teacher_name[chat_id] = True
        bot.send_message(chat_id, "✍️ Пожалуйста, введите ФИО преподавателя, которого хотите оценить:")

    elif call.data.startswith("rating_teacher_"):
        rating = int(call.data.split("_")[2])
        full_name = user_selected_teacher_for_rating.get(chat_id, "Неизвестный преподаватель")

        # Сохраняем оценку в базу данных
        save_rating(chat_id, 'teacher', full_name, rating)

        bot.send_message(chat_id, "✅ Спасибо за вашу оценку!")
        user_selected_teacher_for_rating.pop(chat_id, None)
        show_main_menu(chat_id)

    elif call.data == "contact_information":
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="📞 Куратор Полина", url="https://t.me/polina_morik"))
        keyboard.add(types.InlineKeyboardButton(text="📞 Куратор Виктория", url="https://t.me/vikkaaa1"))
        keyboard.add(types.InlineKeyboardButton(text="📞 Куратор Анастасия", url="https://t.me/nestty2"))
        keyboard.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="feedback"))
        keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Контактные данные кураторов:",
                reply_markup=keyboard
            )
        except:
            bot.send_message(chat_id, "Контактные данные кураторов:", reply_markup=keyboard)

    elif call.data in ['course_prev', 'course_next']:
        user_id = call.from_user.id
        state = user_course_positions['regular'].get(user_id)

        if not state or not state.get('courses'):
            bot.answer_callback_query(call.id, "🌀 Обновите фильтр")
            return

        try:
            current_index = state['position']
            total = len(state['courses'])

            new_index = current_index - 1 if call.data == 'course_prev' else current_index + 1
            new_index %= total  # Циклическая навигация

            user_course_positions['regular'][user_id]['position'] = new_index

            show_course(
                user_id=user_id,
                course_type=state['filter_value'],
                course_index=new_index,
                edit_message_id=call.message.message_id
            )
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Ошибка навигации: {e}")
            bot.answer_callback_query(call.id, "⚠️ Ошибка обновления")

    bot.answer_callback_query(call.id)

if __name__ == '__main__':
    logger.info("Бот запущен")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}")