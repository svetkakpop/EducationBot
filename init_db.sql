-- Удаляем старые таблицы
DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS course_availability;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS positions;
DROP TABLE IF EXISTS course_categories;
DROP TABLE IF EXISTS users;

-- Создаем таблицы
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT NOT NULL,
    position TEXT,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE course_categories (
    category_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES course_categories(category_id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    duration INTEGER,
    price INTEGER,
    url TEXT,
    access TEXT DEFAULT 'open' CHECK (access IN ('open', 'limited')),
    direction TEXT CHECK (direction IN ('finance', 'management', 'pedagogy')),
    role TEXT CHECK (role IN ('ППС', 'АУП', 'Руководство', 'Студент'))
);

CREATE TABLE ratings (
    rating_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    rating_type TEXT NOT NULL,
    target TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Заполняем данные
INSERT INTO course_categories (name, description) VALUES 
('Финансы', 'Курсы по финансовому учету'),
('Управление', 'Курсы по менеджменту'),
('Педагогика', 'Методики преподавания'),
('ППС', 'Для профессорско-преподавательского состава'),
('АУП', 'Для административно-управленческого персонала'),
('Руководство', 'Для руководящего состава'),
('Студенты', 'Для студентов'),
('Открытые программы', 'Доступные для всех'),
('Ограниченные программы', 'С ограниченным доступом');

-- Добавляем тестовые курсы (все курсы из ботяра.txt)
INSERT INTO courses (category_id, title, description, duration, price, url, access, direction, role) VALUES
-- Финансы ППС
(1, 'Финансовое управление научными проектами', 'Методы планирования и контроля бюджета научных исследований', 6, 22000, 'https://openedu.ru/course/research-finance', 'open', 'finance', 'ППС'),
(1, 'Грантовое финансирование в науке', 'Как получить и эффективно использовать грантовые средства', 5, 18000, 'https://openedu.ru/course/science-grants', 'limited', 'finance', 'ППС'),
(1, 'Академическое бюджетирование', 'Принципы формирования и исполнения бюджета кафедры/факультета', 4, 15000, 'https://openedu.ru/course/academic-budgeting', 'open', 'finance', 'ППС'),
(1, 'Экономика высшего образования', 'Финансовые модели и источники финансирования вузов', 7, 25000, 'https://openedu.ru/course/higher-ed-economics', 'limited', 'finance', 'ППС'),
(1, 'Финансовая аналитика для исследователей', 'Анализ финансовых данных в научной работе', 5, 19000, 'https://openedu.ru/course/research-analytics', 'open', 'finance', 'ППС'),

-- Управление ППС
(2, 'Академическое лидерство', 'Стратегии управления кафедрой и научным коллективом', 6, 22000, 'https://openedu.ru/course/academic-leadership', 'limited', 'management', 'ППС'),
(2, 'Управление образовательными программами', 'Разработка и администрирование учебных курсов нового поколения', 5, 18000, 'https://openedu.ru/course/edu-program-mgmt', 'open', 'management', 'ППС'),
(2, 'Управление изменениями в высшей школе', 'Методики внедрения инноваций в академической среде', 4, 15000, 'https://openedu.ru/course/uni-change-mgmt', 'open', 'management', 'ППС'),
(2, 'Управление научными коллективами', 'Эффективные практики руководства исследовательскими группами', 7, 25000, 'https://openedu.ru/course/research-team-mgmt', 'limited', 'management', 'ППС'),
(2, 'Менеджмент академической карьеры', 'Стратегическое планирование профессионального развития в науке', 5, 19000, 'https://openedu.ru/course/academic-career-mgmt', 'open', 'management', 'ППС'),

-- Педагогика ППС
(3, 'Современные методики преподавания в высшей школе', 'Инновационные подходы к организации учебного процесса в вузах', 6, 20000, 'https://openedu.ru/course/modern-teaching-methods', 'open', 'pedagogy', 'ППС'),
(3, 'Педагогическое проектирование', 'Разработка образовательных программ и учебных курсов нового поколения', 5, 18000, 'https://openedu.ru/course/educational-design', 'limited', 'pedagogy', 'ППС'),
(3, 'Когнитивные технологии в обучении', 'Применение достижений когнитивной науки в образовательном процессе', 4, 15000, 'https://openedu.ru/course/cognitive-technologies', 'open', 'pedagogy', 'ППС'),
(3, 'Цифровые инструменты в университетском преподавании', 'Использование современных технологий в академической деятельности', 7, 22000, 'https://openedu.ru/course/digital-teaching-tools', 'limited', 'pedagogy', 'ППС'),
(3, 'Интерактивные методы обучения', 'Технологии вовлечения студентов и активные формы преподавания', 5, 17000, 'https://openedu.ru/course/interactive-teaching', 'open', 'pedagogy', 'ППС'),
(3, 'Международные образовательные стандарты', 'Принципы и практики преподавания по международным стандартам', 6, 21000, 'https://openedu.ru/course/international-standards', 'limited', 'pedagogy', 'ППС'),

-- АУП курсы
(5, 'Бюджетирование подразделений', 'Планирование и контроль бюджетов административных отделов', 5, 18000, 'https://openedu.ru/aup/budgeting', 'open', 'finance', 'АУП'),
(5, 'Учет хозяйственной деятельности', 'Основы финансового учета для административных служб', 4, 15000, 'https://openedu.ru/aup/accounting', 'limited', 'finance', 'АУП'),
(5, 'Эффективный документооборот', 'Оптимизация административных процессов и workflow', 6, 20000, 'https://openedu.ru/aup/document-flow', 'open', 'management', 'АУП'),
(5, 'Управление ИТ-инфраструктурой', 'Организация работы технических служб вуза', 7, 25000, 'https://openedu.ru/aup/it-management', 'limited', 'management', 'АУП'),
(5, 'Администрирование учебного процесса', 'Организация расписания и контроль образовательных программ', 5, 17000, 'https://openedu.ru/aup/edu-admin', 'open', 'pedagogy', 'АУП'),

-- Руководство курсы
(6, 'Стратегическое финансовое планирование', 'Управление бюджетом организации на долгосрочную перспективу', 8, 35000, 'https://openedu.ru/guide/strategic-finance', 'limited', 'finance', 'Руководство'),
(6, 'Инвестиционная политика вуза', 'Управление эндаументами и инвестиционными портфелями', 6, 30000, 'https://openedu.ru/guide/investments', 'limited', 'finance', 'Руководство'),
(6, 'Корпоративное управление', 'Принципы управления советом директоров и акционерами', 9, 40000, 'https://openedu.ru/guide/corporate-governance', 'limited', 'management', 'Руководство'),
(6, 'Международное партнерство', 'Стратегии развития глобальных образовательных сетей', 7, 32000, 'https://openedu.ru/guide/international', 'open', 'management', 'Руководство'),
(6, 'Управление качеством образования', 'Системы аккредитации и международные стандарты', 8, 38000, 'https://openedu.ru/guide/quality-management', 'limited', 'pedagogy', 'Руководство'),
(6, 'Инновации в образовании', 'Внедрение EdTech и цифровых трансформаций', 6, 28000, 'https://openedu.ru/guide/innovation', 'open', 'pedagogy', 'Руководство'),

-- Студенты курсы
(7, 'Основы личных финансов', 'Управление бюджетом, накопления и базовое инвестирование для студентов', 4, 8000, 'https://openedu.ru/students/personal-finance', 'open', 'finance', 'Студент'),
(7, 'Инвестиции 101', 'Введение в мир инвестиций для начинающих', 6, 12000, 'https://openedu.ru/students/investing-101', 'open', 'finance', 'Студент'),
(7, 'Банковские продукты для молодежи', 'Как правильно выбирать и использовать финансовые услуги', 3, 5000, 'https://openedu.ru/students/banking', 'limited', 'finance', 'Студент'),
(7, 'Тайм-менеджмент для студентов', 'Эффективное планирование учебного и личного времени', 4, 6000, 'https://openedu.ru/students/time-management', 'open', 'management', 'Студент'),
(7, 'Основы лидерства', 'Развитие лидерских качеств и навыков работы в команде', 5, 9000, 'https://openedu.ru/students/leadership', 'open', 'management', 'Студент'),
(7, 'Управление студенческими проектами', 'Практические навыки организации мероприятий и проектов', 6, 10000, 'https://openedu.ru/students/project-management', 'limited', 'management', 'Студент'),
(7, 'Основы работы с детьми', 'Базовые навыки для начинающих вожатых и репетиторов', 4, 7000, 'https://openedu.ru/students/childcare', 'open', 'pedagogy', 'Студент'),
(7, 'Цифровые инструменты преподавания', 'Использование технологий в образовательной деятельности', 5, 8500, 'https://openedu.ru/students/digital-teaching', 'open', 'pedagogy', 'Студент'),
(7, 'Методика студенческого тьюторства', 'Подготовка кураторов для младших курсов', 6, 11000, 'https://openedu.ru/students/tutoring', 'limited', 'pedagogy', 'Студент');

-- Индексы
CREATE INDEX idx_users_telegram ON users(telegram_id);
CREATE INDEX idx_courses_category ON courses(category_id);
CREATE INDEX idx_courses_direction ON courses(direction);
CREATE INDEX idx_courses_role ON courses(role);
CREATE INDEX idx_ratings_user ON ratings(user_id);