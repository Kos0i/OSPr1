#!/usr/bin/env python3
import os
import re
import shlex
import sys
import argparse
import json
import base64
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime


class VFSNode:
    #Узел виртуальной файловой системы, систему будем делать по классике: деревом

    def __init__(self, name: str, is_directory: bool = True, content: str = ""): #Замечательный нейминг конструктора в питоне
        self.name = name;
        self.is_directory = is_directory;
        self.content = content;
        self.children: Dict[str, 'VFSNode'] = {}
        self.parent = None;
        self.created = datetime.now();
        self.modified = datetime.now();
        self.permissions = "755" if is_directory else "644"; #Права на файлы и папки
        self.owner = "user";
        self.group = "users";
        self.size = len(content) if not is_directory else 4096; #Тернарник в питоне тоже весёлый

    def add_child(self, node: 'VFSNode'):
        #Добавляет дочерний узел
        if not self.is_directory:
            raise ValueError("Файл не может содержать дочерние элементы"); #Исключение
        node.parent = self;
        self.children[node.name] = node;
        self.modified = datetime.now();

    def remove_child(self, name: str):
        #Удаляет дочерний узел
        if name in self.children:
            del self.children[name];
            self.modified = datetime.now();

    def get_path(self):
        #Возвращает полный путь к узлу
        parts = [];
        current = self;
        while current and current.name:
            parts.append(current.name);
            current = current.parent;
        return '/' + '/'.join(reversed(parts)) if parts else '/'; #конкатенация с джойном

    def find_node(self, path: str) -> 'VFSNode':
        #Находит узел по пути
        if path == "/" or path == "":
            return self;

        parts = [p for p in path.split('/') if p];
        current = self;

        for part in parts:
            if part == "..":
                if current.parent:
                    current = current.parent;
            elif part == ".":
                continue;
            elif part in current.children:
                current = current.children[part];
            else:
                raise FileNotFoundError(f"Путь не найден: {path}");

        return current;

    def is_empty(self) -> bool:
        #Назначение очевидно
        return len(self.children) == 0;


class VFS:
    #Виртуальная файловая система

    def __init__(self):
        self.root = VFSNode("", True)
        self.current_node = self.root

    def load_from_json(self, json_path: str):
        #Загружает VFS из JSON файла
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f);

            self._build_tree(self.root, data);
            print(f"VFS загружена из {json_path}");

        except FileNotFoundError:
            raise FileNotFoundError(f"Файл VFS не найден: {json_path}");
        except json.JSONDecodeError:
            raise ValueError(f"Неверный формат JSON в файле: {json_path}");
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки VFS: {e}");

    def _build_tree(self, node: VFSNode, data: Dict):
        #Рекурсивно строит дерево VFS из данных JSON
        for name, item_data in data.items():
            if isinstance(item_data, dict) and item_data.get('type') == 'directory':
                # Создаем директорию
                child = VFSNode(name, True);
                node.add_child(child);
                # Рекурсивно обрабатываем детей
                self._build_tree(child, item_data.get('children', {}));
            else:
                # Создаем файл
                content = item_data;
                if isinstance(item_data, dict):
                    content = item_data.get('content', '');
                    if item_data.get('encoding') == 'base64':
                        content = base64.b64decode(content).decode('utf-8');

                child = VFSNode(name, False, str(content));
                node.add_child(child);


class ShellEmulator:
    def __init__(self, vfs_name: str = "myvfs", vfs_path: str = None,
                 vfs_json: str = None, debug: bool = False):
        self.vfs_name = vfs_name;
        self.vfs = VFS();
        self.debug = debug;

        # Загружаем VFS если указан JSON файл
        if vfs_json:
            try:
                self.vfs.load_from_json(vfs_json);
            except Exception as e:
                print(f"Ошибка: {e}");
                sys.exit(1);

        self.commands = {
            "ls": self._cmd_ls,
            "cd": self._cmd_cd,
            "pwd": self._cmd_pwd,
            "echo": self._cmd_echo,
            "cat": self._cmd_cat,
            "date": self._cmd_date,
            "who": self._cmd_who,
            "rmdir": self._cmd_rmdir,
            "exit": self._cmd_exit,
        }

        if self.debug:
            print(f"[DEBUG] Инициализация эмулятора:");
            print(f"[DEBUG]   VFS имя: {self.vfs_name}");
            print(f"[DEBUG]   VFS JSON: {vfs_json or 'не указан'}");

    def expand_variables(self, text: str) -> str:
        #Раскрывает переменные окружения

        def replace_var(match):
            var_name = match.group(1) or match.group(2);
            return os.environ.get(var_name, match.group(0));

        pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)|\$\{([^}]+)\}'; #пожалуйста помогите
        return re.sub(pattern, replace_var, text);

    def parse_input(self, input_line: str) -> List[str]:
        #Парсит ввод пользователя
        if not input_line.strip():
            return [];

        expanded_line = self.expand_variables(input_line);

        try:
            return shlex.split(expanded_line);
        except ValueError as e:
            print(f"Ошибка парсинга: {e}");
            return [];

    def _format_permissions(self, node: VFSNode) -> str:
        #Форматирует права доступа в стиле UNIX
        if node.is_directory:
            perm_str = "d";
        else:
            perm_str = "-";

        permissions = node.permissions;
        for i in range(3):
            digit = int(permissions[i]);
            perm_str += "r" if digit & 4 else "-";
            perm_str += "w" if digit & 2 else "-";
            perm_str += "x" if digit & 1 else "-";

        return perm_str;

    def _cmd_ls(self, args: List[str]) -> bool:
        #Команда ls с поддержкой флага -l
        long_format = False;
        show_all = False;
        target_path = ".";

        # Парсинг аргументов
        i = 0;
        while i < len(args) and args[i].startswith('-'):
            if args[i] == '-l':
                long_format = True;
            elif args[i] == '-a':
                show_all = True;
            elif args[i] == '-la' or args[i] == '-al':
                long_format = True;
                show_all = True;
            i += 1;

        if i < len(args):
            target_path = args[i];

        try:
            target_node = self.vfs.current_node.find_node(target_path);

            if not target_node.is_directory:
                print(f"ls: {target_path}: Не является директорией");
                return True;

            items = list(target_node.children.keys());
            if not show_all:
                items = [item for item in items if not item.startswith('.')];

            items.sort();

            if long_format:
                # Вывод в длинном формате
                total_blocks = sum(1 for _ in items);
                print(f"итого {total_blocks}");

                for item in items:
                    node = target_node.children[item];
                    permissions = self._format_permissions(node);
                    size = node.size;
                    owner = node.owner;
                    group = node.group;
                    mtime = node.modified.strftime("%b %d %H:%M");
                    name = item;
                    if node.is_directory:
                        name = f"\033[94m{name}/\033[0m";

                    print(f"{permissions} {owner:>8} {group:>8} {size:>8} {mtime} {name}");
            else:
                # Простой вывод
                for item in items:
                    node = target_node.children[item];
                    if node.is_directory:
                        print(f"\033[94m{item}/\033[0m");
                    else:
                        print(item);

        except FileNotFoundError as e:
            print(f"ls: {e}");

        return True;

    def _cmd_cd(self, args: List[str]) -> bool:
        #Команда cd
        if len(args) > 1:
            print("cd: слишком много аргументов");
            return True;

        target_path = args[0] if args else "/";

        try:
            new_node = self.vfs.current_node.find_node(target_path);
            if not new_node.is_directory:
                print(f"cd: {target_path}: Не является директорией");
            else:
                self.vfs.current_node = new_node;
                if self.debug:
                    print(f"[DEBUG] Смена директории на: {new_node.get_path()}");

        except FileNotFoundError as e:
            print(f"cd: {e}");

        return True;

    def _cmd_pwd(self, args: List[str]) -> bool:
        #Команда pwd
        print(self.vfs.current_node.get_path());
        return True;

    def _cmd_echo(self, args: List[str]) -> bool:
        #Команда echo
        print(' '.join(args));
        return True;

    def _cmd_cat(self, args: List[str]) -> bool:
        #Команда cat
        if not args:
            print("cat: отсутствуют аргументы");
            return True;

        for filename in args:
            try:
                node = self.vfs.current_node.find_node(filename);
                if node.is_directory:
                    print(f"cat: {filename}: Это каталог");
                else:
                    print(node.content);
            except FileNotFoundError:
                print(f"cat: {filename}: Нет такого файла или каталога");

        return True;

    def _cmd_date(self, args: List[str]) -> bool:
        #Команда date - вывод текущей даты и времени
        now = datetime.now();
        if args and args[0] == '+%Y-%m-%d':
            print(now.strftime("%Y-%m-%d"));
        elif args and args[0] == '+%H:%M:%S':
            print(now.strftime("%H:%M:%S"));
        else:
            print(now.strftime("%a %b %d %H:%M:%S %Y"));
        return True;

    def _cmd_who(self, args: List[str]) -> bool:
        #Команда who - вывод информации о пользователях
        current_user = os.environ.get('USER', 'user');
        hostname = os.environ.get('HOSTNAME', 'localhost');
        now = datetime.now();

        print(f"{current_user} pts/0 {now.strftime('%Y-%m-%d %H:%M')} ({hostname})");
        print(f"{current_user} pts/1 {now.strftime('%Y-%m-%d %H:%M')} ({hostname})");
        return True;

    def _cmd_rmdir(self, args: List[str]) -> bool:
        #Команда rmdir - удаление пустых директорий
        if not args:
            print("rmdir: отсутствуют операнды");
            return True;

        for dirname in args:
            try:
                # Находим узел для удаления
                target_node = self.vfs.current_node.find_node(dirname);

                if not target_node.is_directory:
                    print(f"rmdir: удаление '{dirname}' не выполнено: Не является директорией");
                    continue;

                if not target_node.is_empty():
                    print(f"rmdir: удаление '{dirname}' не выполнено: Директория не пуста");
                    continue;

                if target_node == self.vfs.root:
                    print(f"rmdir: удаление '{dirname}' не выполнено: Невозможно удалить корневую директорию");
                    continue;

                if target_node == self.vfs.current_node:
                    print(f"rmdir: удаление '{dirname}' не выполнено: Невозможно удалить текущую директорию");
                    continue;

                # Удаляем директорию из родительского узла
                parent_node = target_node.parent;
                parent_node.remove_child(target_node.name);
                print(f"rmdir: удалена директория '{dirname}'");

            except FileNotFoundError:
                print(f"rmdir: удаление '{dirname}' не выполнено: Нет такого файла или каталога");
            except Exception as e:
                print(f"rmdir: ошибка при удалении '{dirname}': {e}");

        return True;

    def _cmd_exit(self, args: List[str]) -> bool:
        #Команда exit
        exit_code = 0;
        if args:
            try:
                exit_code = int(args[0]);
            except ValueError:
                print(f"exit: {args[0]}: необходим числовой аргумент");
                return True;

        sys.exit(exit_code);

    def execute_command(self, command: str, args: List[str]) -> bool:
        #Выполняет команду
        if command.startswith("#"):
            return True;

        if command not in self.commands:
            print(f"{command}: команда не найдена");
            return True;

        try:
            return self.commands[command](args);
        except Exception as e:
            print(f"Ошибка выполнения команды {command}: {e}");
            return True;

    def get_prompt(self) -> str:
        #Возвращает строку приглашения
        current_path = self.vfs.current_node.get_path();
        if current_path == "/":
            display_path = "/";
        else:
            display_path = current_path;

        return f"\033[92m{self.vfs_name}\033[0m:\033[94m{display_path}\033[0m$ ";

    def execute_script(self, script_path: str):
        #Выполняет команды из скрипта
        script_file = Path(script_path);

        if not script_file.exists():
            print(f"Ошибка: скрипт '{script_path}' не найден");
            return;

        if self.debug:
            print(f"[DEBUG] Выполнение скрипта: {script_path}");

        try:
            with open(script_file, 'r', encoding='utf-8') as f:
                lines = f.readlines();

            for line_num, line in enumerate(lines, 1):
                line = line.strip();
                if not line or line.startswith("#"):
                    continue;

                print(f"{self.get_prompt()}{line}");

                parts = self.parse_input(line);
                if not parts:
                    continue;

                command = parts[0];
                args = parts[1:];

                try:
                    self.execute_command(command, args);
                except SystemExit:
                    break;
                except Exception as e:
                    print(f"Ошибка в строке {line_num}: {e}");
                    continue;

        except Exception as e:
            print(f"Ошибка выполнения скрипта '{script_path}': {e}");

    def run(self, script_path: str = None):
        #Основной цикл REPL или выполнение скрипта
        if script_path:
            self.execute_script(script_path);
            return;

        print(f"Добро пожаловать в эмулятор командной строки с VFS!");
        print("Доступные команды: ls, cd, pwd, echo, cat, date, who, rmdir, exit");
        print("-" * 50);

        running = True;
        while running:
            try:
                user_input = input(self.get_prompt()).strip();
                parts = self.parse_input(user_input);
                if not parts:
                    continue;

                command = parts[0];
                args = parts[1:];
                running = self.execute_command(command, args);

            except KeyboardInterrupt:
                print("\nДля выхода используйте команду 'exit'");
            except EOFError:
                print("\nВыход из эмулятора");
                break
            except Exception as e:
                print(f"Неожиданная ошибка: {e}");


parser = argparse.ArgumentParser(description='Эмулятор командной строки с VFS');
parser.add_argument('--vfs-json', type=str, help='Путь к JSON файлу VFS');
parser.add_argument('--script', type=str, help='Путь к стартовому скрипту');
parser.add_argument('--vfs-name', type=str, default='myvfs', help='Имя VFS');
parser.add_argument('--debug', action='store_true', help='Включить режим отладки');

args = parser.parse_args();

print("=== ПАРАМЕТРЫ ЗАПУСКА ЭМУЛЯТОРА ===");
print(f"VFS имя: {args.vfs_name}");
print(f"VFS JSON: {args.vfs_json or 'не указан'}");
print(f"Скрипт: {args.script or 'не указан'}");
print(f"Режим отладки: {'включен' if args.debug else 'выключен'}");
print("=" * 40);

shell = ShellEmulator(
    vfs_name=args.vfs_name,
    vfs_json=args.vfs_json,
    debug=args.debug
)

shell.run(script_path=args.script);