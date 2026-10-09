"""SQLite: users (одна таблица, роль в поле role), tickets, comments, history.

Логин уникален. Повторно не создаётся открытое обращение с той же темой у того же автора.
"""

import hashlib
import os
import sqlite3
import sys
from datetime import datetime


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_db_path():
    root = _app_dir()
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "support.db")
    legacy = os.path.join(root, "support.db")
    if not os.path.exists(path) and os.path.exists(legacy):
        os.replace(legacy, path)
    return path


DB_PATH = _resolve_db_path()

ROLES = ("admin", "operator", "user")
CATEGORIES = ("hardware", "software", "network", "access", "other")
PRIORITIES = ("low", "normal", "high", "critical")
STATUSES = ("new", "in_progress", "resolved", "closed")

STATUS_RU = {
    "new": "Новое",
    "in_progress": "В работе",
    "resolved": "Решено",
    "closed": "Закрыто",
}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        salt_hex, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, bytes.fromhex(salt_hex)) == stored


def init_db():
    conn = connect()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                login       TEXT NOT NULL UNIQUE,
                password    TEXT NOT NULL,
                full_name   TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user'
                                CHECK (role IN ('admin', 'operator', 'user')),
                specialty   TEXT NOT NULL DEFAULT 'other',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                category     TEXT NOT NULL DEFAULT 'other',
                priority     TEXT NOT NULL DEFAULT 'normal',
                status       TEXT NOT NULL DEFAULT 'new',
                author_id    INTEGER NOT NULL REFERENCES users(id),
                operator_id  INTEGER REFERENCES users(id),
                created_at   TEXT NOT NULL,
                resolved_at  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
                user_id    INTEGER,
                action     TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_open_ticket
            ON tickets(author_id, title)
            WHERE status IN ('new', 'in_progress')
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
                user_id    INTEGER NOT NULL REFERENCES users(id),
                body       TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_tickets_author ON tickets(author_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_tickets_operator ON tickets(operator_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_comments_ticket ON comments(ticket_id)")
    _seed_admin(conn)
    _seed_demo(conn)
    conn.close()


def _seed_admin(conn):
    cur = conn.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] == 0:
        with conn:
            conn.execute(
                "INSERT INTO users (login, password, full_name, role, specialty, created_at)"
                " VALUES (?, ?, ?, 'admin', 'other', ?)",
                ("admin", hash_password("admin"), "Администратор", now()),
            )


def _seed_demo(conn):
    demo_users = (
        ("ivanov", "operator", "Иван Иванов", "operator", "hardware"),
        ("petrova", "operator", "Мария Петрова", "operator", "software"),
        ("sidorov", "operator", "Олег Сидоров", "operator", "network"),
        ("kozlova", "operator", "Анна Козлова", "operator", "other"),
        ("orlova", "operator", "Елена Орлова", "operator", "access"),
        ("smirnov", "user", "Алексей Смирнов", "user", "other"),
        ("volkova", "user", "Ольга Волкова", "user", "other"),
        ("morozov", "user", "Павел Морозов", "user", "other"),
    )
    demo_tickets = (
        ("smirnov", "Не печатает принтер в кабинете 204", "Картридж установлен, листы выходят пустые.", "hardware", "high", "in_progress", "ivanov"),
        ("smirnov", "Мерцает монитор", "Гаснет через несколько минут работы.", "hardware", "normal", "in_progress", "kozlova"),
        ("smirnov", "Сброс пароля доменной учётной записи", "Пользователь забыл пароль и не может войти.", "access", "high", "new", None),
        ("volkova", "1С закрывается при проведении", "Ошибка появилась после обновления платформы.", "software", "critical", "in_progress", "petrova"),
        ("volkova", "Не открывается корпоративная почта", "Клиент пишет, что сервер недоступен.", "software", "high", "resolved", "petrova"),
        ("volkova", "Не печатает документ из браузера", "Из редактора печатает, из браузера нет.", "software", "normal", "new", None),
        ("morozov", "Пропал интернет на третьем этаже", "Wi-Fi подключается, сайты не открываются.", "network", "critical", "in_progress", "sidorov"),
        ("morozov", "Не подключается VPN", "Соединение обрывается на авторизации.", "network", "normal", "in_progress", "sidorov"),
        ("morozov", "Нет доступа к общей папке", "Раньше папка открывалась без пароля.", "access", "normal", "closed", "orlova"),
        ("volkova", "Замена клавиатуры", "Не работают несколько клавиш.", "hardware", "low", "resolved", "ivanov"),
    )
    with conn:
        for login, password, full_name, role, specialty in demo_users:
            if conn.execute("SELECT 1 FROM users WHERE login = ?", (login,)).fetchone():
                continue
            conn.execute(
                "INSERT INTO users (login, password, full_name, role, specialty, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (login, hash_password(password), full_name, role, specialty, now()),
            )
        if conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]:
            return
        ids = {
            row["login"]: row["id"]
            for row in conn.execute("SELECT id, login FROM users").fetchall()
        }
        for author, title, description, category, priority, status, operator in demo_tickets:
            created = now()
            resolved = created if status in ("resolved", "closed") else None
            operator_id = ids[operator] if operator else None
            cur = conn.execute(
                "INSERT INTO tickets (title, description, category, priority, status, author_id, operator_id, created_at, resolved_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, description, category, priority, status, ids[author], operator_id, created, resolved),
            )
            ticket_id = cur.lastrowid
            _log(conn, ticket_id, ids[author], "Обращение создано")
            if operator_id:
                name = conn.execute(
                    "SELECT full_name FROM users WHERE id = ?",
                    (operator_id,),
                ).fetchone()["full_name"]
                _log(conn, ticket_id, None, f"Назначен оператор: {name}")
            if status in ("resolved", "closed"):
                _log(conn, ticket_id, operator_id, f"Статус: {STATUS_RU[status]}")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _open_duplicate(conn, author_id, title, exclude_id=None):
    key = title.strip().casefold()
    rows = conn.execute(
        "SELECT id, title FROM tickets"
        " WHERE author_id = ? AND status IN ('new', 'in_progress')",
        (author_id,),
    ).fetchall()
    for row in rows:
        if exclude_id is not None and row["id"] == exclude_id:
            continue
        if row["title"].strip().casefold() == key:
            return row["id"]
    return None


# --- users ---

def create_user(login, password, full_name, role="user", specialty="other", is_active=1):
    login = login.strip().lower()
    full_name = full_name.strip()
    if len(login) < 3 or not full_name or len(password) < 4:
        return False, "Логин от 3 символов, пароль от 4, ФИО обязательно"
    if role not in ROLES:
        return False, "Неизвестная роль"
    if specialty not in CATEGORIES:
        return False, "Неизвестная специализация"
    conn = connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (login, password, full_name, role, specialty, is_active, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (login, hash_password(password), full_name, role, specialty, int(is_active), now()),
            )
        return True, "Пользователь создан"
    except sqlite3.IntegrityError:
        return False, "Логин уже занят"
    finally:
        conn.close()


def authenticate(login, password):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM users WHERE login = ?",
        (login.strip().lower(),),
    ).fetchone()
    conn.close()
    if not row or not verify_password(password, row["password"]):
        return None, "Неверный логин или пароль"
    if not row["is_active"]:
        return None, "Учётная запись отключена"
    user = dict(row)
    user.pop("password", None)
    return user, None


def get_user(user_id):
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users(role=None):
    conn = connect()
    if role:
        rows = conn.execute("SELECT * FROM users WHERE role = ? ORDER BY id", (role,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_operators(only_active=True):
    conn = connect()
    sql = "SELECT * FROM users WHERE role = 'operator'"
    if only_active:
        sql += " AND is_active = 1"
    sql += " ORDER BY id"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user(user_id, **fields):
    allowed = {"full_name", "role", "specialty", "is_active", "password"}
    values = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "password" in values:
        if not str(values["password"]):
            values.pop("password")
        else:
            if len(values["password"]) < 4:
                return False, "Пароль не короче 4 символов"
            values["password"] = hash_password(values["password"])
    if "full_name" in values:
        values["full_name"] = values["full_name"].strip()
        if not values["full_name"]:
            return False, "Укажите ФИО"
    if "role" in values and values["role"] not in ROLES:
        return False, "Неизвестная роль"
    if "specialty" in values and values["specialty"] not in CATEGORIES:
        return False, "Неизвестная специализация"
    if "is_active" in values:
        values["is_active"] = int(values["is_active"])
    if not values:
        return False, "Нет изменений"

    conn = connect()
    try:
        with conn:
            current = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not current:
                return False, "Пользователь не найден"
            new_role = values.get("role", current["role"])
            new_active = int(values.get("is_active", current["is_active"]))
            loses_admin = (
                current["role"] == "admin"
                and current["is_active"]
                and not (new_role == "admin" and new_active == 1)
            )
            if loses_admin:
                others = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
                    (user_id,),
                ).fetchone()[0]
                if others == 0:
                    return False, "Нельзя снять последнего активного администратора"
            assignments = ", ".join(f"{k} = ?" for k in values)
            conn.execute(
                f"UPDATE users SET {assignments} WHERE id = ?",
                (*values.values(), user_id),
            )
            released = 0
            was_operator = current["role"] == "operator" and current["is_active"]
            stays_operator = new_role == "operator" and new_active == 1
            if was_operator and not stays_operator:
                released = _release_operator_tickets(conn, user_id, user_id)
        if released:
            return True, f"Сохранено. В очередь возвращено: {released}"
        return True, "Сохранено"
    finally:
        conn.close()


# --- tickets ---

def create_ticket(title, description, category, priority, author_id):
    title = title.strip()
    description = description.strip()
    if not title:
        return None, "Укажите тему"
    if len(title) > 200:
        return None, "Тема слишком длинная"
    if category not in CATEGORIES:
        return None, "Неизвестная категория"
    if priority not in PRIORITIES:
        return None, "Неизвестный приоритет"
    conn = connect()
    try:
        with conn:
            if _open_duplicate(conn, author_id, title):
                return None, "Такое обращение уже открыто"
            cur = conn.execute(
                "INSERT INTO tickets (title, description, category, priority, status, author_id, created_at)"
                " VALUES (?, ?, ?, ?, 'new', ?, ?)",
                (title, description, category, priority, author_id, now()),
            )
            ticket_id = cur.lastrowid
            _log(conn, ticket_id, author_id, "Обращение создано")
        return ticket_id, None
    except sqlite3.IntegrityError:
        return None, "Такое обращение уже открыто"
    finally:
        conn.close()


def list_tickets(author_id=None, operator_id=None, status=None):
    conn = connect()
    sql = (
        "SELECT t.*, a.full_name AS author_name, o.full_name AS operator_name"
        " FROM tickets t"
        " JOIN users a ON a.id = t.author_id"
        " LEFT JOIN users o ON o.id = t.operator_id WHERE 1=1"
    )
    params = []
    if author_id is not None:
        sql += " AND t.author_id = ?"
        params.append(author_id)
    if operator_id is not None:
        sql += " AND t.operator_id = ?"
        params.append(operator_id)
    if status:
        sql += " AND t.status = ?"
        params.append(status)
    sql += " ORDER BY t.id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ticket(ticket_id):
    conn = connect()
    row = conn.execute(
        "SELECT t.*, a.full_name AS author_name, o.full_name AS operator_name"
        " FROM tickets t JOIN users a ON a.id = t.author_id"
        " LEFT JOIN users o ON o.id = t.operator_id WHERE t.id = ?",
        (ticket_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _release_operator_tickets(conn, operator_id, actor_id):
    rows = conn.execute(
        "SELECT id FROM tickets WHERE operator_id = ? AND status IN ('new', 'in_progress')",
        (operator_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE tickets SET operator_id = NULL, status = 'new', resolved_at = NULL WHERE id = ?",
            (row["id"],),
        )
        _log(conn, row["id"], actor_id, "Оператор снят, обращение возвращено в очередь")
    return len(rows)


def take_ticket(ticket_id, operator_id):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT operator_id, status FROM tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        user = conn.execute(
            "SELECT role, is_active FROM users WHERE id = ?",
            (operator_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return False, "Обращение не найдено"
    if not user or user["role"] != "operator" or not user["is_active"]:
        return False, "Взять заявку может только активный оператор"
    if row["status"] in ("resolved", "closed"):
        return False, "Обращение уже закрыто"
    if row["operator_id"] is not None:
        return False, "Обращение уже назначено"
    ok, message = assign_ticket(ticket_id, operator_id, operator_id, note="оператор взял сам")
    if ok:
        return True, "Заявка взята в работу"
    return False, message


def return_to_work(ticket_id, actor_id):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return False, "Обращение не найдено"
    if ticket["status"] != "resolved":
        return False, "Вернуть можно только решённое обращение"
    actor = get_user(actor_id)
    if not actor or (actor["id"] != ticket["author_id"] and actor["role"] != "admin"):
        return False, "Недостаточно прав"
    operator = get_user(ticket["operator_id"]) if ticket["operator_id"] else None
    if operator and operator["is_active"] and operator["role"] == "operator":
        return set_status(ticket_id, "in_progress", actor_id)
    conn = connect()
    try:
        with conn:
            conn.execute(
                "UPDATE tickets SET operator_id = NULL, status = 'new', resolved_at = NULL WHERE id = ?",
                (ticket_id,),
            )
            _log(conn, ticket_id, actor_id, "Обращение возвращено в очередь")
        return True, "Обращение снова в очереди"
    finally:
        conn.close()


def add_comment(ticket_id, user_id, body):
    body = body.strip()
    if not body:
        return False, "Введите текст"
    if len(body) > 2000:
        return False, "Комментарий слишком длинный"
    conn = connect()
    try:
        with conn:
            ticket = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if not ticket:
                return False, "Обращение не найдено"
            conn.execute(
                "INSERT INTO comments (ticket_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
                (ticket_id, user_id, body, now()),
            )
            _log(conn, ticket_id, user_id, "Добавлен комментарий")
        return True, "Комментарий добавлен"
    finally:
        conn.close()


def list_comments(ticket_id):
    conn = connect()
    rows = conn.execute(
        "SELECT c.*, u.full_name AS user_name FROM comments c"
        " JOIN users u ON u.id = c.user_id WHERE c.ticket_id = ? ORDER BY c.id",
        (ticket_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def assign_ticket(ticket_id, operator_id, actor_id=None, note=""):
    conn = connect()
    try:
        with conn:
            current = conn.execute(
                "SELECT operator_id, status, title, author_id FROM tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if not current:
                return False, "Обращение не найдено"
            if current["operator_id"] == operator_id and current["status"] == "in_progress":
                return True, "Уже назначено"
            if current["status"] not in ("new", "in_progress"):
                if _open_duplicate(conn, current["author_id"], current["title"], ticket_id):
                    return False, "Уже есть открытое обращение с такой темой"
            name_row = conn.execute(
                "SELECT full_name FROM users WHERE id = ?",
                (operator_id,),
            ).fetchone()
            if not name_row:
                return False, "Оператор не найден"
            conn.execute(
                "UPDATE tickets SET operator_id = ?, status = 'in_progress' WHERE id = ?",
                (operator_id, ticket_id),
            )
            action = f"Назначен оператор: {name_row['full_name']}"
            if note:
                action += f" ({note})"
            _log(conn, ticket_id, actor_id, action)
        return True, "Назначено"
    except sqlite3.IntegrityError:
        return False, "Нельзя открыть: уже есть такое обращение"
    finally:
        conn.close()


def set_status(ticket_id, status, actor_id=None):
    if status not in STATUSES:
        return False, "Неизвестный статус"
    conn = connect()
    try:
        with conn:
            current = conn.execute(
                "SELECT status, title, author_id FROM tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if not current:
                return False, "Обращение не найдено"
            if current["status"] == status:
                return True, "Без изменений"
            if status in ("new", "in_progress") and _open_duplicate(
                conn, current["author_id"], current["title"], ticket_id
            ):
                return False, "Уже есть открытое обращение с такой темой"
            resolved = now() if status in ("resolved", "closed") else None
            conn.execute(
                "UPDATE tickets SET status = ?, resolved_at = ? WHERE id = ?",
                (status, resolved, ticket_id),
            )
            _log(conn, ticket_id, actor_id, f"Статус: {STATUS_RU[status]}")
        return True, "Статус обновлён"
    except sqlite3.IntegrityError:
        return False, "Уже есть открытое обращение с такой темой"
    finally:
        conn.close()


def active_load(operator_id):
    conn = connect()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM tickets"
        " WHERE operator_id = ? AND status IN ('new', 'in_progress')",
        (operator_id,),
    ).fetchone()
    conn.close()
    return row["c"]


def ticket_history(ticket_id):
    conn = connect()
    rows = conn.execute(
        "SELECT h.*, u.full_name AS user_name FROM history h"
        " LEFT JOIN users u ON u.id = h.user_id WHERE h.ticket_id = ? ORDER BY h.id",
        (ticket_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _log(conn, ticket_id, user_id, action):
    conn.execute(
        "INSERT INTO history (ticket_id, user_id, action, created_at) VALUES (?, ?, ?, ?)",
        (ticket_id, user_id, action, now()),
    )


def stats():
    conn = connect()

    def scalar(sql, params=()):
        return conn.execute(sql, params).fetchone()[0]

    data = {
        "users": scalar("SELECT COUNT(*) FROM users"),
        "operators": scalar("SELECT COUNT(*) FROM users WHERE role='operator' AND is_active=1"),
        "tickets": scalar("SELECT COUNT(*) FROM tickets"),
        "new": scalar("SELECT COUNT(*) FROM tickets WHERE status='new'"),
        "in_progress": scalar("SELECT COUNT(*) FROM tickets WHERE status='in_progress'"),
        "resolved": scalar("SELECT COUNT(*) FROM tickets WHERE status IN ('resolved','closed')"),
        "unassigned": scalar(
            "SELECT COUNT(*) FROM tickets WHERE operator_id IS NULL AND status IN ('new','in_progress')"
        ),
    }
    conn.close()
    return data
