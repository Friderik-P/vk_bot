# vk_bot/src/keyboards/inline.py
"""Инлайн-клавиатуры (встроенные в сообщение)."""

from vk_api.keyboard import VkKeyboard


def get_inline_keyboard():
    """
    Возвращает JSON-строку инлайн-клавиатуры с одной кнопкой.
    Используется для callback-событий (нажатий без отправки текста).
    """
    keyboard = VkKeyboard(inline=True)
    # payload — это callback_data для VK
    keyboard.add_callback_button(label="Нажми меня", payload={"command": "test"})
    return keyboard.get_keyboard()


def get_admin_help_inline_keyboard():
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(label="/health", payload={"command": "/health"})
    keyboard.add_button(label="/stats", payload={"command": "/stats"})
    keyboard.add_line()
    keyboard.add_button(label="/admins", payload={"command": "/admins"})
    keyboard.add_button(label="/admin_add", payload={"command": "/admin_add"})
    keyboard.add_button(label="/admin_del", payload={"command": "/admin_del"})
    keyboard.add_line()
    keyboard.add_button(label="/stop", payload={"command": "/stop"})
    keyboard.add_line()
    keyboard.add_button(label="/restart", payload={"command": "/restart"})
    return keyboard.get_keyboard()


__all__ = ["get_inline_keyboard", "get_admin_help_inline_keyboard"]
