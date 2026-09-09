# tests/test_admins.py
"""Тесты хранилища администраторов."""

from pathlib import Path

import pytest
import yaml

from src.admins import AdminStore, init_admins_yaml, get_admins, add_admin, remove_admin


class TestAdminStore:
    """Тесты класса AdminStore."""

    def test_init_creates_file_from_env(self, tmp_path: Path) -> None:
        """Если файл отсутствует, init создаёт его из env_admins."""
        yaml_path = tmp_path / "admins.yaml"
        store = AdminStore(yaml_path)
        store.init((111, 222, 333))

        assert yaml_path.exists()
        assert store.get_all() == {111, 222, 333}

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data == {"admins": [111, 222, 333]}

    def test_init_loads_existing_file(self, tmp_path: Path) -> None:
        """Если файл существует и не пуст, init загружает из него."""
        yaml_path = tmp_path / "admins.yaml"
        yaml_path.write_text("admins:\n- 555\n", encoding="utf-8")

        store = AdminStore(yaml_path)
        store.init((999,))

        assert store.get_all() == {555}

    def test_init_recreates_empty_file(self, tmp_path: Path) -> None:
        """Если файл пуст, init пересоздаёт из env_admins."""
        yaml_path = tmp_path / "admins.yaml"
        yaml_path.write_text("admins: []\n", encoding="utf-8")

        store = AdminStore(yaml_path)
        store.init((777,))

        assert store.get_all() == {777}

    def test_init_no_env_admins(self, tmp_path: Path) -> None:
        """Если env_admins пуст, файл не создаётся."""
        yaml_path = tmp_path / "admins.yaml"
        store = AdminStore(yaml_path)
        store.init(())

        assert not yaml_path.exists()
        assert store.get_all() == set()

    def test_add_admin(self, tmp_path: Path) -> None:
        """Добавление нового администратора."""
        yaml_path = tmp_path / "admins.yaml"
        store = AdminStore(yaml_path)
        store.init((1,))

        assert store.add(2) is True
        assert store.get_all() == {1, 2}

        # Повторное добавление не меняет состояние
        assert store.add(2) is False
        assert store.get_all() == {1, 2}

    def test_remove_admin(self, tmp_path: Path) -> None:
        """Удаление администратора."""
        yaml_path = tmp_path / "admins.yaml"
        store = AdminStore(yaml_path)
        store.init((1, 2))

        assert store.remove(1) is True
        assert store.get_all() == {2}

        # Удаление несуществующего не падает
        assert store.remove(999) is False
        assert store.get_all() == {2}

    def test_get_all_returns_copy(self, tmp_path: Path) -> None:
        """get_all() возвращает копию, чтобы внешний код не мог сломать состояние."""
        yaml_path = tmp_path / "admins.yaml"
        store = AdminStore(yaml_path)
        store.init((1,))

        copy = store.get_all()
        copy.add(999)

        assert store.get_all() == {1}


class TestBackwardCompatibleFunctions:
    """Тесты обратно-совместимых функций-обёрток."""

    def test_init_admins_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """init_admins_yaml() работает через синглтон."""
        yaml_path = tmp_path / "admins.yaml"
        monkeypatch.setattr("src.admins._store", AdminStore(yaml_path), raising=False)

        init_admins_yaml()
        assert get_admins() == {536284550}

    def test_add_and_remove(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """add_admin/remove_admin работают через синглтон."""
        yaml_path = tmp_path / "admins.yaml"
        monkeypatch.setattr("src.admins._store", AdminStore(yaml_path), raising=False)

        init_admins_yaml()
        assert add_admin(111) is True
        assert get_admins() == {536284550, 111}
        assert remove_admin(111) is True
        assert get_admins() == {536284550}
