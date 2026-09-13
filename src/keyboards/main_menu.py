# vk_bot/src/keyboards/main_menu.py
"""Главное меню бота (обычная клавиатура)."""

from vk_api.keyboard import VkKeyboard
from .types import COLOR_ACTION, COLOR_INFO, COLOR_DANGER


def get_main_menu_keyboard():
    """
    Возвращает JSON-строку главной клавиатуры с кнопками:
      - Мяу (основное действие)
      - Помощь (информация)
      - Контакты (опасное/важное)
    one_time=False — клавиатура остаётся после нажатия.
    """
    keyboard = VkKeyboard(one_time=False)

    # Первая строка: Мяу + Помощь
    keyboard.add_button("Мяу", color=COLOR_ACTION)
    keyboard.add_button("Помощь", color=COLOR_INFO)
    keyboard.add_line()

    # Вторая строка: Контакты
    keyboard.add_button("Контакты", color=COLOR_DANGER)

    return keyboard.get_keyboard()


__all__ = ["get_main_menu_keyboard"]
