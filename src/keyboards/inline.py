# vk_bot/src/keyboards/inline.py
"""Инлайн-клавиатуры (встроенные в сообщение)."""

from vk_api.keyboard import VkKeyboard


def get_admin_help_inline_keyboard():
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(label="/health", payload={"command": "/health"})
    keyboard.add_button(label="/stats", payload={"command": "/stats"})
    keyboard.add_line()
    keyboard.add_button(label="/admins", payload={"command": "/admins"})
    keyboard.add_line()
    keyboard.add_button(label="/stop", payload={"command": "/stop"})
    keyboard.add_line()
    keyboard.add_button(label="/restart", payload={"command": "/restart"})
    return keyboard.get_keyboard()


__all__ = ["get_admin_help_inline_keyboard"]
