#!/usr/bin/env python3
"""Окно приложения: вход, роли и панели."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GObject, Gtk, Pango

from evelina import db, distribution

ROLE_LABEL = {
    "admin": "Администратор",
    "operator": "Оператор",
    "user": "Пользователь",
}
CATEGORY_LABEL = {
    "hardware": "Оборудование",
    "software": "Программы",
    "network": "Сеть",
    "access": "Доступ",
    "other": "Прочее",
}
PRIORITY_LABEL = {
    "low": "Низкий",
    "normal": "Обычный",
    "high": "Высокий",
    "critical": "Критический",
}
ROLE_ORDER = ("admin", "operator", "user")

SAMPLE_OPERATORS = (
    ("ivanov", "Иван Иванов", "hardware"),
    ("petrova", "Мария Петрова", "software"),
    ("sidorov", "Олег Сидоров", "network"),
    ("kozlova", "Анна Козлова", "other"),
)

CSS = """
.error-text { color: @destructive_color; font-weight: 600; }
.side-pane { background-color: @sidebar_bg_color; }
.stat-card { padding: 14px 16px; }
"""


def alert(parent, heading, body=""):
    dialog = Adw.AlertDialog(heading=heading)
    if body:
        dialog.set_body(body)
        dialog.set_prefer_wide_layout(True)
    dialog.add_response("ok", "Понятно")
    dialog.set_default_response("ok")
    dialog.present(parent)


class TableRow(GObject.Object):
    __gtype_name__ = "SupportTableRow"

    def __init__(self, values):
        super().__init__()
        self.values = tuple(values)


def selected_value(selection, column=0):
    item = selection.get_selected_item()
    if item is None:
        return None
    return item.values[column]


def make_table(headers):
    store = Gio.ListStore.new(TableRow)
    selection = Gtk.SingleSelection(model=store)
    view = Gtk.ColumnView(model=selection)
    view.set_hexpand(True)
    view.set_vexpand(True)
    for index, (title, expand, width) in enumerate(headers):
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, item):
            label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
            label.set_margin_start(8)
            label.set_margin_end(8)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            item.set_child(label)

        def bind(_factory, item, col=index):
            row = item.get_item()
            item.get_child().set_label("" if row is None else str(row.values[col]))

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        column = Gtk.ColumnViewColumn(title=title, factory=factory)
        column.set_expand(expand)
        column.set_resizable(True)
        if not expand:
            column.set_fixed_width(width)
        view.append_column(column)
    fixed = sum(width for _title, expand, width in headers if not expand)
    view.set_size_request(fixed + 260, -1)
    return view, store, selection


def scrolled(child):
    widget = Gtk.ScrolledWindow()
    widget.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    widget.set_vexpand(True)
    widget.set_hexpand(True)
    widget.set_child(child)
    return widget


def field_label(text):
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("dim-label")
    return label


class UserDialog(Adw.Window):
    def __init__(self, parent, user_id, on_saved):
        super().__init__(transient_for=parent, modal=True, destroy_with_parent=True)
        self.parent_window = parent
        self.user_id = user_id
        self.on_saved = on_saved
        self.set_default_size(440, 560)
        self.set_title("Пользователь")

        record = db.get_user(user_id) if user_id else None
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Новый пользователь" if record is None else record["full_name"],
                subtitle="Учётная запись",
            )
        )
        save = Gtk.Button(label="Сохранить")
        save.add_css_class("suggested-action")
        save.connect("clicked", lambda *_: self._save())
        header.pack_end(save)
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()
        account = Adw.PreferencesGroup(title="Учётная запись")
        self.name = Adw.EntryRow(title="ФИО")
        self.login = Adw.EntryRow(title="Логин")
        self.password = Adw.PasswordEntryRow(
            title="Пароль" if record is None else "Новый пароль"
        )
        account.add(self.name)
        account.add(self.login)
        account.add(self.password)
        page.add(account)

        access = Adw.PreferencesGroup(
            title="Доступ",
            description="Специализация учитывается при автоматическом назначении оператора.",
        )
        self.role = Adw.ComboRow(title="Роль")
        self.role.set_model(Gtk.StringList.new([ROLE_LABEL[item] for item in ROLE_ORDER]))
        self.specialty = Adw.ComboRow(title="Специализация")
        self.specialty.set_model(
            Gtk.StringList.new([CATEGORY_LABEL[item] for item in db.CATEGORIES])
        )
        self.active = Adw.SwitchRow(title="Активен", active=True)
        access.add(self.role)
        access.add(self.specialty)
        access.add(self.active)
        page.add(access)
        toolbar.set_content(page)
        self.set_content(toolbar)

        if record:
            self.name.set_text(record["full_name"])
            self.login.set_text(record["login"])
            self.login.set_sensitive(False)
            self.role.set_selected(ROLE_ORDER.index(record["role"]))
            self.specialty.set_selected(db.CATEGORIES.index(record["specialty"]))
            self.active.set_active(bool(record["is_active"]))
        else:
            self.role.set_selected(ROLE_ORDER.index("user"))
            self.specialty.set_selected(db.CATEGORIES.index("other"))

    def _save(self):
        full_name = self.name.get_text().strip()
        role = ROLE_ORDER[self.role.get_selected()]
        specialty = db.CATEGORIES[self.specialty.get_selected()]
        is_active = self.active.get_active()
        password = self.password.get_text()
        session_id = self.parent_window.user["id"]

        if self.user_id == session_id and not is_active:
            alert(self, "Нельзя отключить свою учётную запись")
            return

        if self.user_id is None:
            ok, message = db.create_user(
                self.login.get_text(),
                password,
                full_name,
                role=role,
                specialty=specialty,
                is_active=1 if is_active else 0,
            )
        else:
            fields = {
                "full_name": full_name,
                "role": role,
                "specialty": specialty,
                "is_active": 1 if is_active else 0,
            }
            if password:
                fields["password"] = password
            ok, message = db.update_user(self.user_id, **fields)

        if not ok:
            alert(self, "Не сохранено", message)
            return
        self.close()
        self.on_saved(self.user_id, message)


def clear_box(box):
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


class TicketDialog(Adw.Window):
    def __init__(self, parent, ticket_id, on_changed):
        super().__init__(transient_for=parent, modal=True, destroy_with_parent=True)
        self.parent_window = parent
        self.ticket_id = ticket_id
        self.on_changed = on_changed
        self.ready = False
        self.set_default_size(720, 680)
        ticket = db.get_ticket(ticket_id)
        if not ticket or not self._can_view(ticket):
            return
        self.ready = True
        self._build()
        self.reload()

    def _can_view(self, ticket):
        user = self.parent_window.user
        if user["role"] == "admin":
            return True
        if user["role"] == "operator" and (
            ticket["operator_id"] in (None, user["id"])
        ):
            return True
        return ticket["author_id"] == user["id"]

    def _can_manage(self, ticket):
        user = self.parent_window.user
        if user["role"] == "admin":
            return True
        return user["role"] == "operator" and ticket["operator_id"] == user["id"]

    def _build(self):
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.heading = Adw.WindowTitle(title="Обращение", subtitle="")
        header.set_title_widget(self.heading)
        toolbar.add_top_bar(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.set_margin_start(16)
        body.set_margin_end(16)
        body.set_margin_top(12)
        body.set_margin_bottom(16)

        self.meta_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        body.append(self.meta_label)
        self.desc_label = Gtk.Label(xalign=0, yalign=0, wrap=True, selectable=True)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("card")
        card.add_css_class("stat-card")
        card.append(self.desc_label)
        body.append(card)

        self.status_box = Gtk.Box(spacing=8)
        self.status_buttons = {}
        for status, caption in (
            ("in_progress", "В работу"),
            ("resolved", "Решено"),
            ("closed", "Закрыть"),
        ):
            button = Gtk.Button(label=caption)
            if status == "resolved":
                button.add_css_class("suggested-action")
            button.connect("clicked", lambda _, value=status: self._set_status(value))
            self.status_buttons[status] = button
            self.status_box.append(button)
        body.append(self.status_box)

        self.take_btn = Gtk.Button(label="Взять в работу")
        self.take_btn.add_css_class("suggested-action")
        self.take_btn.connect("clicked", lambda *_: self._take())
        body.append(self.take_btn)

        self.return_btn = Gtk.Button(label="Вернуть в работу")
        self.return_btn.connect("clicked", lambda *_: self._return())
        body.append(self.return_btn)

        self.admin_box = Gtk.Box(spacing=8)
        operators = db.list_operators(only_active=True)
        if operators:
            self.operator_drop = LabeledDrop(
                [(item["id"], f"{item['full_name']} · {CATEGORY_LABEL[item['specialty']]}") for item in operators]
            )
            self.operator_drop.set_hexpand(True)
            manual = Gtk.Button(label="Назначить")
            manual.connect("clicked", lambda *_: self._assign_manual())
            self.admin_box.append(self.operator_drop)
            self.admin_box.append(manual)
        else:
            self.operator_drop = None
        auto = Gtk.Button(label="Распределить автоматически")
        auto.connect("clicked", lambda *_: self._assign_auto())
        self.admin_box.append(auto)
        body.append(self.admin_box)

        self.comments_group = Adw.PreferencesGroup(title="Комментарии")
        self.comments_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.comments_group.add(self.comments_box)
        self.comment_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        self.comment_view.set_left_margin(8)
        self.comment_view.set_right_margin(8)
        self.comment_view.set_top_margin(6)
        self.comment_view.set_bottom_margin(6)
        comment_scroll = Gtk.ScrolledWindow(min_content_height=72)
        comment_scroll.set_child(self.comment_view)
        comment_scroll.add_css_class("card")
        send = Gtk.Button(label="Отправить комментарий")
        send.connect("clicked", lambda *_: self._send_comment())
        comment_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        comment_wrap.append(field_label("Текст комментария"))
        comment_wrap.append(comment_scroll)
        comment_wrap.append(send)
        self.comments_group.add(comment_wrap)
        body.append(self.comments_group)

        self.history = Adw.PreferencesGroup(title="Журнал")
        self.history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.history.add(self.history_box)
        body.append(self.history)

        toolbar.set_content(scrolled(body))
        self.set_content(toolbar)

    def reload(self):
        ticket = db.get_ticket(self.ticket_id)
        if not ticket:
            self.close()
            return False
        user = self.parent_window.user
        self.heading.set_title(f"№{ticket['id']} · {ticket['title']}")
        self.heading.set_subtitle(db.STATUS_RU[ticket["status"]])
        self.set_title(ticket["title"])
        operator = ticket["operator_name"] or "не назначен"
        meta = (
            f"{CATEGORY_LABEL[ticket['category']]} · {PRIORITY_LABEL[ticket['priority']]}\n"
            f"Автор: {ticket['author_name']} · Оператор: {operator}\n"
            f"Создано: {ticket['created_at']}"
        )
        if ticket["resolved_at"]:
            meta += f" · Завершено: {ticket['resolved_at']}"
        self.meta_label.set_text(meta)
        self.desc_label.set_text(ticket["description"] or "Без описания")

        manage = self._can_manage(ticket)
        self.status_box.set_visible(manage)
        for status, button in self.status_buttons.items():
            button.set_sensitive(ticket["status"] != status)
        self.take_btn.set_visible(
            user["role"] == "operator"
            and ticket["operator_id"] is None
            and ticket["status"] in ("new", "in_progress")
        )
        self.return_btn.set_visible(ticket["author_id"] == user["id"] and ticket["status"] == "resolved")
        self.admin_box.set_visible(user["role"] == "admin")
        if self.operator_drop is not None and ticket["operator_id"] is not None:
            self.operator_drop.set_value(ticket["operator_id"])

        self._show_comments()
        self._show_history()
        return False

    def _show_comments(self):
        clear_box(self.comments_box)
        comments = db.list_comments(self.ticket_id)
        if not comments:
            empty = Gtk.Label(label="Пока нет комментариев", xalign=0)
            empty.add_css_class("dim-label")
            self.comments_box.append(empty)
            return
        for comment in comments:
            block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            block.add_css_class("card")
            block.add_css_class("stat-card")
            who = Gtk.Label(label=f"{comment['user_name']} · {comment['created_at']}", xalign=0)
            who.add_css_class("dim-label")
            text = Gtk.Label(label=comment["body"], xalign=0, wrap=True, selectable=True)
            block.append(who)
            block.append(text)
            self.comments_box.append(block)

    def _show_history(self):
        clear_box(self.history_box)
        events = db.ticket_history(self.ticket_id)
        if not events:
            empty = Gtk.Label(label="Пока пусто", xalign=0)
            empty.add_css_class("dim-label")
            self.history_box.append(empty)
            return
        for event in events:
            who = event["user_name"] or "система"
            row = Adw.ActionRow(title=event["action"], subtitle=f"{event['created_at']} · {who}")
            self.history_box.append(row)

    def _comment_text(self):
        buffer = self.comment_view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def _finish(self, message):
        self.reload()
        self.on_changed()
        if message:
            self.parent_window.notify(message)

    def _set_status(self, status):
        ok, message = db.set_status(self.ticket_id, status, self.parent_window.user["id"])
        if not ok:
            alert(self, "Не удалось", message)
            return
        self._finish(message)

    def _assign_manual(self):
        if self.operator_drop is None:
            alert(self, "Нет активных операторов")
            return
        ok, message = db.assign_ticket(
            self.ticket_id,
            self.operator_drop.value(),
            self.parent_window.user["id"],
            note="вручную",
        )
        if not ok:
            alert(self, "Не удалось", message)
            return
        self._finish("Оператор назначен")

    def _assign_auto(self):
        ticket = db.get_ticket(self.ticket_id)
        operator, debug = distribution.distribute(
            ticket["id"], ticket["category"], ticket["priority"], self.parent_window.user["id"]
        )
        self._finish("Оператор назначен" if operator else "Не назначено")
        alert(self, "Распределение", "\n".join(debug))

    def _take(self):
        ok, message = db.take_ticket(self.ticket_id, self.parent_window.user["id"])
        if not ok:
            alert(self, "Не удалось", message)
            return
        self._finish(message)

    def _return(self):
        ok, message = db.return_to_work(self.ticket_id, self.parent_window.user["id"])
        if not ok:
            alert(self, "Не удалось", message)
            return
        self._finish(message)

    def _send_comment(self):
        ok, message = db.add_comment(self.ticket_id, self.parent_window.user["id"], self._comment_text())
        if not ok:
            alert(self, "Не отправлено", message)
            return
        self.comment_view.get_buffer().set_text("")
        self._finish(message)


class LabeledDrop(Gtk.DropDown):
    def __init__(self, pairs):
        self._ids = [key for key, _label in pairs]
        labels = [label for _key, label in pairs]
        super().__init__(model=Gtk.StringList.new(labels))
        self.set_selected(0)

    def value(self):
        index = self.get_selected()
        if index is None or int(index) >= len(self._ids):
            return self._ids[0]
        return self._ids[int(index)]

    def set_value(self, key):
        if key in self._ids:
            self.set_selected(self._ids.index(key))


class OverviewPage(Gtk.ScrolledWindow):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.box.set_margin_start(20)
        self.box.set_margin_end(20)
        self.box.set_margin_top(16)
        self.box.set_margin_bottom(20)
        self.stats = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            max_children_per_line=4,
            min_children_per_line=2,
            column_spacing=8,
            row_spacing=8,
        )
        self.box.append(self.stats)
        about = Gtk.Label(
            xalign=0,
            wrap=True,
            label=(
                "Новое обращение само уходит оператору: выше балл у совпавшей специализации "
                "и у меньшей текущей загрузки. Срочный приоритет сильнее штрафует перегруженных."
            ),
        )
        about.add_css_class("dim-label")
        self.box.append(about)

        actions = Gtk.Box(spacing=8)
        distribute = Gtk.Button(label="Распределить ожидающие")
        distribute.add_css_class("suggested-action")
        distribute.connect("clicked", lambda *_: self._distribute_pending())
        sample = Gtk.Button(label="Добавить операторов для примера")
        sample.connect("clicked", lambda *_: self._seed_operators())
        actions.append(distribute)
        actions.append(sample)
        self.box.append(actions)

        self.loads = Adw.PreferencesGroup(title="Загрузка операторов")
        self.box.append(self.loads)
        self.set_child(self.box)
        self._cards = {}
        self._load_rows = []

    def reload(self):
        data = db.stats()
        captions = (
            ("users", "Пользователи"),
            ("operators", "Операторы"),
            ("unassigned", "Без оператора"),
            ("new", "Новые"),
            ("in_progress", "В работе"),
            ("resolved", "Завершённые"),
        )
        if not self._cards:
            for key, caption in captions:
                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                card.add_css_class("card")
                card.add_css_class("stat-card")
                title = Gtk.Label(label=caption, xalign=0)
                title.add_css_class("dim-label")
                value = Gtk.Label(label="0", xalign=0)
                value.add_css_class("title-1")
                card.append(title)
                card.append(value)
                self.stats.append(card)
                self._cards[key] = value
        for key, _caption in captions:
            self._cards[key].set_text(str(data[key]))

        for row in self._load_rows:
            self.loads.remove(row)
        self._load_rows.clear()
        operators = db.list_operators(only_active=False)
        if not operators:
            self.loads.set_description("Активных операторов нет. Добавьте их в разделе «Пользователи».")
            return
        self.loads.set_description("")
        for operator in operators:
            load = db.active_load(operator["id"])
            state = "активен" if operator["is_active"] else "отключён"
            row = Adw.ActionRow(
                title=operator["full_name"],
                subtitle=f"{CATEGORY_LABEL[operator['specialty']]} · {state}",
            )
            mark = Gtk.Label(label=f"{load} в работе")
            mark.add_css_class("dim-label")
            row.add_suffix(mark)
            self.loads.add(row)
            self._load_rows.append(row)

    def _distribute_pending(self):
        pending = [
            ticket
            for ticket in db.list_tickets()
            if ticket["operator_id"] is None and ticket["status"] in ("new", "in_progress")
        ]
        if not pending:
            self.window.notify("Ожидающих обращений нет")
            self.reload()
            return
        lines = []
        for ticket in pending:
            operator, _debug = distribution.distribute(
                ticket["id"], ticket["category"], ticket["priority"], self.window.user["id"]
            )
            target = operator["full_name"] if operator else "нет оператора"
            lines.append(f"№{ticket['id']} {ticket['title']} → {target}")
        self.reload()
        alert(self.window, "Распределение", "\n".join(lines))

    def _seed_operators(self):
        created = []
        skipped = []
        for login, full_name, specialty in SAMPLE_OPERATORS:
            ok, _message = db.create_user(
                login, "operator", full_name, role="operator", specialty=specialty
            )
            (created if ok else skipped).append(login)
        self.reload()
        text = f"Добавлены: {', '.join(created) or '—'}\nУже были: {', '.join(skipped) or '—'}\nПароль новых: operator"
        alert(self.window, "Операторы", text)


class UsersPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.window = window
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(12)
        self.set_margin_bottom(12)

        bar = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text="Поиск по имени или логину")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda *_: self.reload())
        add = Gtk.Button(label="Добавить")
        add.add_css_class("suggested-action")
        add.connect("clicked", lambda *_: UserDialog(self.window, None, self._saved).present())
        edit = Gtk.Button(label="Изменить")
        edit.connect("clicked", lambda *_: self._edit_selected())
        toggle = Gtk.Button(label="Вкл / выкл")
        toggle.connect("clicked", lambda *_: self._toggle())
        bar.append(self.search)
        bar.append(add)
        bar.append(edit)
        bar.append(toggle)
        self.append(bar)

        self.view, self.store, self.selection = make_table(
            (
                ("№", False, 44),
                ("Логин", False, 100),
                ("ФИО", True, 180),
                ("Роль", False, 168),
                ("Специализация", False, 140),
                ("Состояние", False, 112),
            )
        )
        self.view.connect("activate", lambda *_: self._edit_selected())
        self.append(scrolled(self.view))
        self.count = Gtk.Label(xalign=0)
        self.count.add_css_class("dim-label")
        self.append(self.count)

    def reload(self, keep=None):
        query = self.search.get_text().strip().casefold()
        self.store.remove_all()
        shown = 0
        keep_at = None
        for user in db.list_users():
            blob = f"{user['login']} {user['full_name']}".casefold()
            if query and query not in blob:
                continue
            self.store.append(
                TableRow(
                    (
                        user["id"],
                        user["login"],
                        user["full_name"],
                        ROLE_LABEL[user["role"]],
                        CATEGORY_LABEL[user["specialty"]],
                        "активен" if user["is_active"] else "отключён",
                    )
                )
            )
            if keep == user["id"]:
                keep_at = shown
            shown += 1
        if keep_at is not None:
            self.selection.set_selected(keep_at)
        self.count.set_text(f"Показано: {shown}" if shown else "Никого не найдено")

    def _edit_selected(self):
        user_id = selected_value(self.selection)
        if user_id is None:
            alert(self.window, "Выберите пользователя")
            return
        UserDialog(self.window, user_id, self._saved).present()

    def _saved(self, user_id, message="Пользователь сохранён"):
        if user_id == self.window.user["id"]:
            self.window.refresh_session()
        else:
            self.reload(keep=user_id)
        self.window.notify(message)

    def _toggle(self):
        user_id = selected_value(self.selection)
        if user_id is None:
            alert(self.window, "Выберите пользователя")
            return
        record = db.get_user(user_id)
        if user_id == self.window.user["id"] and record["is_active"]:
            alert(self.window, "Нельзя отключить свою учётную запись")
            return
        ok, message = db.update_user(user_id, is_active=0 if record["is_active"] else 1)
        if not ok:
            alert(self.window, "Не удалось", message)
            return
        self.reload(keep=user_id)
        self.window.notify(message)


class TicketsPage(Gtk.Box):
    def __init__(self, window, scope):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.window = window
        self.scope = scope
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(12)
        self.set_margin_bottom(12)

        filters = [("all", "Все"), ("new", "Новые"), ("in_progress", "В работе"),
                   ("resolved", "Решённые"), ("closed", "Закрытые")]
        if scope == "all":
            filters.append(("unassigned", "Без оператора"))
        self.filter = LabeledDrop(filters)
        self.filter.connect("notify::selected", lambda *_: self.reload())
        self.search = Gtk.SearchEntry(placeholder_text="Поиск по теме, автору, оператору")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda *_: self.reload())
        open_btn = Gtk.Button(label="Открыть")
        open_btn.connect("clicked", lambda *_: self._open_selected())

        bar = Gtk.Box(spacing=8)
        bar.append(self.filter)
        bar.append(self.search)
        bar.append(open_btn)
        if scope == "free":
            take = Gtk.Button(label="Взять в работу")
            take.add_css_class("suggested-action")
            take.connect("clicked", lambda *_: self._take_selected())
            bar.append(take)
        self.append(bar)

        self.view, self.store, self.selection = make_table(
            (
                ("№", False, 64),
                ("Тема", True, 260),
                ("Категория", False, 140),
                ("Приоритет", False, 120),
                ("Статус", False, 110),
                ("Автор", False, 150),
                ("Оператор", False, 150),
            )
        )
        self.view.connect("activate", lambda *_: self._open_selected())
        self.append(scrolled(self.view))
        self.count = Gtk.Label(xalign=0)
        self.count.add_css_class("dim-label")
        self.append(self.count)
        self._ready = True

    def reload(self):
        if not getattr(self, "_ready", False):
            return
        mode = self.filter.value()
        query = self.search.get_text().strip().casefold()
        user = self.window.user
        if self.scope == "mine":
            rows = db.list_tickets(author_id=user["id"])
        elif self.scope == "queue":
            rows = db.list_tickets(operator_id=user["id"])
        elif self.scope == "free":
            rows = [
                ticket
                for ticket in db.list_tickets()
                if ticket["operator_id"] is None and ticket["status"] in ("new", "in_progress")
            ]
        else:
            rows = db.list_tickets()
        self.store.remove_all()
        shown = 0
        for ticket in rows:
            if mode == "unassigned" and ticket["operator_id"] is not None:
                continue
            if mode not in ("all", "unassigned") and ticket["status"] != mode:
                continue
            blob = " ".join(
                (
                    ticket["title"],
                    ticket["author_name"] or "",
                    ticket["operator_name"] or "",
                )
            ).casefold()
            if query and query not in blob:
                continue
            self.store.append(
                TableRow(
                    (
                        ticket["id"],
                        ticket["title"],
                        CATEGORY_LABEL[ticket["category"]],
                        PRIORITY_LABEL[ticket["priority"]],
                        db.STATUS_RU[ticket["status"]],
                        ticket["author_name"],
                        ticket["operator_name"] or "—",
                    )
                )
            )
            shown += 1
        self.count.set_text(f"Показано: {shown}" if shown else "Показано: 0 — ничего не найдено")

    def _open_selected(self):
        ticket_id = selected_value(self.selection)
        if ticket_id is None:
            alert(self.window, "Выберите обращение")
            return
        dialog = TicketDialog(self.window, ticket_id, self.reload)
        if not dialog.ready:
            dialog.close()
            return
        dialog.present()

    def _take_selected(self):
        ticket_id = selected_value(self.selection)
        if ticket_id is None:
            alert(self.window, "Выберите обращение")
            return
        ok, message = db.take_ticket(ticket_id, self.window.user["id"])
        if not ok:
            alert(self.window, "Не удалось", message)
            return
        self.window.notify(message)
        self.reload()


class NewTicketPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.set_valign(Gtk.Align.START)
        self.set_vexpand(True)
        clamp = Adw.Clamp(maximum_size=640, tightening_threshold=640)
        clamp.set_margin_top(20)
        clamp.set_margin_bottom(20)
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        form.set_margin_start(16)
        form.set_margin_end(16)

        intro = Gtk.Label(
            xalign=0,
            wrap=True,
            label="После создания обращение сразу назначается свободному оператору подходящего профиля.",
        )
        intro.add_css_class("dim-label")
        form.append(intro)

        group = Adw.PreferencesGroup(title="Новое обращение")
        self.title = Adw.EntryRow(title="Тема")
        group.add(self.title)
        form.append(group)

        form.append(field_label("Описание"))
        self.description = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        self.description.set_left_margin(8)
        self.description.set_right_margin(8)
        self.description.set_top_margin(6)
        self.description.set_bottom_margin(6)
        desc_scroll = Gtk.ScrolledWindow(min_content_height=140)
        desc_scroll.set_child(self.description)
        desc_scroll.add_css_class("card")
        form.append(desc_scroll)

        picks = Gtk.Box(spacing=12)
        category_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        priority_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.category = LabeledDrop(list(CATEGORY_LABEL.items()))
        self.priority = LabeledDrop(list(PRIORITY_LABEL.items()))
        self.priority.set_value("normal")
        category_box.append(field_label("Категория"))
        category_box.append(self.category)
        priority_box.append(field_label("Приоритет"))
        priority_box.append(self.priority)
        picks.append(category_box)
        picks.append(priority_box)
        form.append(picks)

        self.error = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.error.add_css_class("error-text")
        form.append(self.error)

        submit = Gtk.Button(label="Создать и распределить")
        submit.add_css_class("suggested-action")
        submit.add_css_class("pill")
        submit.connect("clicked", lambda *_: self._submit())
        self.submit = submit
        form.append(submit)
        clamp.set_child(form)
        self.append(clamp)

    def reload(self):
        return

    def _text(self):
        buffer = self.description.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def _submit(self):
        self.submit.set_sensitive(False)
        try:
            ticket_id, error = db.create_ticket(
                self.title.get_text(),
                self._text(),
                self.category.value(),
                self.priority.value(),
                self.window.user["id"],
            )
            if error:
                self.error.set_text(error)
                self.error.set_visible(True)
                return
            operator, debug = distribution.distribute(
                ticket_id,
                self.category.value(),
                self.priority.value(),
                self.window.user["id"],
            )
            self.error.set_visible(False)
            self.title.set_text("")
            self.description.get_buffer().set_text("")
            heading = f"Обращение №{ticket_id}"
            if operator:
                heading += f" → {operator['full_name']}"
            else:
                heading += " ждёт оператора"
            alert(self.window, heading, "\n".join(debug))
            self.window.notify(heading)
        finally:
            self.submit.set_sensitive(True)


class ShellView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.window = window
        user = window.user

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        side.add_css_class("side-pane")
        side.set_size_request(220, -1)
        brand = Gtk.Label(label="Поддержка", xalign=0)
        brand.add_css_class("title-3")
        brand.set_margin_top(16)
        brand.set_margin_start(16)
        brand.set_margin_bottom(8)
        side.append(brand)

        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        self.sidebar.add_css_class("navigation-sidebar")
        self.sidebar.connect("row-selected", self._on_select)
        nav_scroll = Gtk.ScrolledWindow()
        nav_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nav_scroll.set_vexpand(True)
        nav_scroll.set_child(self.sidebar)
        side.append(nav_scroll)

        foot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        foot.set_margin_start(12)
        foot.set_margin_end(12)
        foot.set_margin_bottom(12)
        self.name_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.name_label.add_css_class("heading")
        self.meta_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.meta_label.add_css_class("dim-label")
        logout = Gtk.Button(label="Выйти")
        logout.connect("clicked", lambda *_: window.show_login())
        foot.append(Gtk.Separator())
        foot.append(self.name_label)
        foot.append(self.meta_label)
        foot.append(logout)
        side.append(foot)
        self.sync_identity()

        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.pages = {}

        items = self._menu(user["role"])
        for key, title, icon, factory in items:
            page = factory()
            self.pages[key] = page
            self.stack.add_named(page, key)
            self.sidebar.append(self._nav(key, title, icon))

        self.append(side)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.append(self.stack)
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))

    def _menu(self, role):
        window = self.window
        if role == "admin":
            return (
                ("overview", "Обзор", "view-grid-symbolic", lambda: OverviewPage(window)),
                ("users", "Пользователи", "system-users-symbolic", lambda: UsersPage(window)),
                ("tickets", "Обращения", "folder-symbolic", lambda: TicketsPage(window, "all")),
            )
        if role == "operator":
            return (
                ("free", "Свободные", "mail-unread-symbolic", lambda: TicketsPage(window, "free")),
                ("queue", "Мои заявки", "view-list-symbolic", lambda: TicketsPage(window, "queue")),
            )
        return (
            ("mine", "Мои обращения", "folder-symbolic", lambda: TicketsPage(window, "mine")),
            ("new", "Новое обращение", "document-new-symbolic", lambda: NewTicketPage(window)),
        )

    def _nav(self, key, title, icon):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(Gtk.Image.new_from_icon_name(icon))
        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        box.append(label)
        row.set_child(box)
        row.page_key = key
        row.page_title = title
        return row

    def sync_identity(self):
        user = self.window.user
        self.name_label.set_text(user["full_name"])
        self.meta_label.set_text(f"{user['login']} · {ROLE_LABEL[user['role']]}")

    def _on_select(self, _box, row):
        if row is None:
            return
        self.stack.set_visible_child_name(row.page_key)
        self.window.set_heading(row.page_title, ROLE_LABEL[self.window.user["role"]])
        page = self.pages.get(row.page_key)
        if page is not None:
            page.reload()

    def reload_visible(self):
        page = self.stack.get_visible_child()
        if page is not None:
            page.reload()


class LoginView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True, vexpand=True)
        self.window = window
        clamp = Adw.Clamp(maximum_size=460, tightening_threshold=460)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(28)

        title = Gtk.Label(label="Техническая поддержка")
        title.add_css_class("title-1")
        subtitle = Gtk.Label(label="Вход для сотрудников и пользователей")
        subtitle.add_css_class("dim-label")
        card.append(title)
        card.append(subtitle)

        self.stack = Adw.ViewStack()
        self.stack.add_titled_with_icon(self._login_form(), "login", "Вход", "dialog-password-symbolic")
        self.stack.add_titled_with_icon(
            self._register_form(), "register", "Регистрация", "contact-new-symbolic"
        )
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        switcher.set_halign(Gtk.Align.CENTER)
        card.append(switcher)
        card.append(self.stack)
        clamp.set_child(card)
        self.append(clamp)

    def _login_form(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group = Adw.PreferencesGroup()
        self.login = Adw.EntryRow(title="Логин")
        self.password = Adw.PasswordEntryRow(title="Пароль")
        self.login.connect("entry-activated", lambda *_: self.password.grab_focus())
        self.password.connect("entry-activated", lambda *_: self._login())
        group.add(self.login)
        group.add(self.password)
        box.append(group)
        self.login_error = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.login_error.add_css_class("error-text")
        box.append(self.login_error)
        button = Gtk.Button(label="Войти")
        button.add_css_class("suggested-action")
        button.add_css_class("pill")
        button.connect("clicked", lambda *_: self._login())
        box.append(button)
        hint = Gtk.Label(
            label=(
                "admin / admin\n"
                "Операторы: ivanov, petrova, sidorov, kozlova, orlova — пароль operator\n"
                "Пользователи: smirnov, volkova, morozov — пароль user"
            ),
            xalign=0,
            wrap=True,
        )
        hint.add_css_class("dim-label")
        box.append(hint)
        return box

    def _register_form(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group = Adw.PreferencesGroup(description="Новая учётная запись получает роль «Пользователь».")
        self.reg_name = Adw.EntryRow(title="ФИО")
        self.reg_login = Adw.EntryRow(title="Логин")
        self.reg_password = Adw.PasswordEntryRow(title="Пароль")
        self.reg_repeat = Adw.PasswordEntryRow(title="Пароль ещё раз")
        self.reg_repeat.connect("entry-activated", lambda *_: self._register())
        group.add(self.reg_name)
        group.add(self.reg_login)
        group.add(self.reg_password)
        group.add(self.reg_repeat)
        box.append(group)
        self.reg_error = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.reg_error.add_css_class("error-text")
        box.append(self.reg_error)
        button = Gtk.Button(label="Зарегистрироваться")
        button.add_css_class("suggested-action")
        button.add_css_class("pill")
        button.connect("clicked", lambda *_: self._register())
        box.append(button)
        return box

    def _login(self):
        user, error = db.authenticate(self.login.get_text(), self.password.get_text())
        if error:
            self.login_error.set_text(error)
            self.login_error.set_visible(True)
            return
        self.window.show_shell(user)

    def _register(self):
        if self.reg_password.get_text() != self.reg_repeat.get_text():
            self.reg_error.set_text("Пароли не совпадают")
            self.reg_error.set_visible(True)
            return
        ok, message = db.create_user(
            self.reg_login.get_text(),
            self.reg_password.get_text(),
            self.reg_name.get_text(),
            role="user",
        )
        if not ok:
            self.reg_error.set_text(message)
            self.reg_error.set_visible(True)
            return
        user, error = db.authenticate(self.reg_login.get_text(), self.reg_password.get_text())
        if error:
            self.reg_error.set_text(error)
            self.reg_error.set_visible(True)
            return
        self.window.show_shell(user)
        self.window.notify("Учётная запись создана")


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_title("Служба технической поддержки")
        self.set_default_size(1180, 760)
        self.user = None
        self.shell = None
        self.toast = Adw.ToastOverlay()
        self.toolbar = Adw.ToolbarView()
        self.heading = Adw.WindowTitle(title="Служба технической поддержки", subtitle="Вход")
        header = Adw.HeaderBar()
        header.set_title_widget(self.heading)
        self.toolbar.add_top_bar(header)
        self.toast.set_child(self.toolbar)
        self.set_content(self.toast)
        self.show_login()

    def set_heading(self, title, subtitle=""):
        self.heading.set_title(title)
        self.heading.set_subtitle(subtitle)

    def notify(self, text):
        self.toast.add_toast(Adw.Toast(title=text))

    def show_login(self):
        self.user = None
        self.shell = None
        self.set_heading("Служба технической поддержки", "Вход")
        self.toolbar.set_content(LoginView(self))

    def show_shell(self, user):
        self.user = user
        self.shell = ShellView(self)
        self.toolbar.set_content(self.shell)

    def refresh_session(self):
        fresh = db.get_user(self.user["id"])
        if not fresh or not fresh["is_active"]:
            self.notify("Сессия завершена")
            self.show_login()
            return
        fresh.pop("password", None)
        role_changed = fresh["role"] != self.user["role"]
        self.user = fresh
        if role_changed or self.shell is None:
            self.show_shell(fresh)
            self.notify("Роль изменена, меню обновлено")
            return
        self.shell.sync_identity()
        self.shell.reload_visible()
        self.notify("Профиль обновлён")


class SupportApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="ru.evelina.SupportDesk")
        self.connect("activate", self._activate)

    def _activate(self, _app):
        if getattr(self, "win", None) is not None:
            self.win.present()
            return
        db.init_db()
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.win = MainWindow(self)
        self.win.present()


def main():
    app = SupportApp()
    return app.run(None)
