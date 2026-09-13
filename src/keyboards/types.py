# vk_bot/src/keyboards/types.py
"""Цвета кнопок клавиатуры VK."""

from vk_api.keyboard import VkKeyboardColor

COLOR_ACTION = VkKeyboardColor.POSITIVE      # Основное действие (яркое)
COLOR_INFO = VkKeyboardColor.SECONDARY       # Вспомогательная информация (серое)
COLOR_DANGER = VkKeyboardColor.NEGATIVE       # Опасное/важное действие (красное)
COLOR_DEFAULT = VkKeyboardColor.PRIMARY       # Нейтральный (вместо несуществующего DEFAULT)

__all__ = ["COLOR_ACTION", "COLOR_INFO", "COLOR_DANGER", "COLOR_DEFAULT"]
