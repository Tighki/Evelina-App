"""Интеллектуальное распределение обращений.

Выбирает оператора по многокритериальной оценке:
    * соответствие специализации категории обращения;
    * текущая загрузка (балансировка нагрузки);
    * доступность (активен);
    * приоритет обращения (перегрузка штрафуется сильнее для срочных заявок).
"""

from evelina import db

SPECIALTY_BONUS = 40
UNIVERSAL_BONUS = 12
MAX_ACTIVE = 5
LOAD_WEIGHT = {          # вес штрафа за каждое активное обращение
    "low": 3,
    "normal": 5,
    "high": 8,
    "critical": 12,
}


def score_operator(operator, category, priority, load):
    """Возвращает (score, reasons). Чем больше score — тем лучше кандидат."""
    reasons = []
    score = 0.0

    if operator["specialty"] == category:
        score += SPECIALTY_BONUS
        reasons.append(f"специализация совпадает +{SPECIALTY_BONUS}")
    elif operator["specialty"] == "other":
        score += UNIVERSAL_BONUS
        reasons.append(f"универсальный оператор +{UNIVERSAL_BONUS}")
    else:
        reasons.append("специализация не совпадает")

    penalty = load * LOAD_WEIGHT.get(priority, 5)
    score -= penalty
    reasons.append(f"загрузка {load} (−{penalty})")
    if load >= MAX_ACTIVE:
        reasons.append(f"предел {MAX_ACTIVE} заявок")

    return score, reasons


def pick_operator(category, priority="normal"):
    """Возвращает (operator, debug) либо (None, debug) если операторов нет."""
    operators = db.list_operators(only_active=True)
    under, over = [], []
    for op in operators:
        load = db.active_load(op["id"])
        score, reasons = score_operator(op, category, priority, load)
        item = (score, load, op, reasons)
        (over if load >= MAX_ACTIVE else under).append(item)

    pool = under or over
    if not pool:
        return None, ["нет активных операторов"]

    pool.sort(key=lambda item: (-item[0], item[1], item[2]["id"]))
    best_score, _best_load, best_op, best_reasons = pool[0]
    debug = [f"{op['full_name']}: {score:.1f}" for score, _, op, _ in pool]
    summary = f"Назначен {best_op['full_name']} (оценка {best_score:.1f})"
    if not under:
        summary += f". Все на пределе {MAX_ACTIVE}, выбран с меньшей загрузкой"
    elif over:
        skipped = ", ".join(op["full_name"] for _, _, op, _ in over)
        debug.append(f"Сверх предела {MAX_ACTIVE}: {skipped}")
    debug.insert(0, summary)
    debug[1:1] = best_reasons
    return best_op, debug


def distribute(ticket_id, category, priority, actor_id=None):
    """Автоматически назначает оператора на обращение. Возвращает (operator, debug)."""
    operator, debug = pick_operator(category, priority)
    if not operator:
        return None, debug
    load = db.active_load(operator["id"])
    _, reasons = score_operator(operator, category, priority, load)
    ok, message = db.assign_ticket(ticket_id, operator["id"], actor_id, note="; ".join(reasons))
    if not ok:
        return None, [message, *debug]
    return operator, debug
