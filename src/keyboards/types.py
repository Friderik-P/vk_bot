# vk_bot/src/keyboards/types.py
"""Цвета кнопок клавиатуры VK."""

from vk_api.keyboard import VkKeyboardColor

COLOR_ACTION = VkKeyboardColor.POSITIVE  # Основное действие (яркое)
COLOR_INFO = VkKeyboardColor.SECONDARY  # Вспомогательная информация (серое)
COLOR_DANGER = VkKeyboardColor.NEGATIVE  # Опасное/важное действие (красное)

__all__ = ["COLOR_ACTION", "COLOR_DANGER", "COLOR_INFO"]
