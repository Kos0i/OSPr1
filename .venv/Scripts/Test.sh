#!/bin/bash
echo "МЕГА-ТЕСТ ВСЕХ ЭТАПОВ"

# Создаем ГИГА VFS для тестирования
cat > final_test_vfs.json << 'JSON'
{
  "home": {
    "type": "directory",
    "children": {
      "user": {
        "type": "directory",
        "children": {
          "documents": {
            "type": "directory",
            "children": {
              "work": {
                "type": "directory",
                "children": {
                  "project1": {
                    "type": "directory",
                    "children": {
                      "src": {
                        "type": "directory",
                        "children": {
                          "main.py": {"content": "print('Hello World')"},
                          "utils.py": {"content": "def helper(): pass"}
                        }
                      },
                      "README.md": {"content": "# Project 1\nTest project"}
                    }
                  },
                  "empty_dir": {
                    "type": "directory",
                    "children": {}
                  }
                }
              },
              "file1.txt": {"content": "Document file 1"},
              "file2.txt": {"content": "Document file 2"}
            }
          },
          "downloads": {
            "type": "directory",
            "children": {
              "temp_file.tmp": {"content": "Temporary content"}
            }
          }
        }
      }
    }
  },
  "var": {
    "type": "directory",
    "children": {
      "log": {
        "type": "directory",
        "children": {
          "system.log": {"content": "System started\nUsers connected"}
        }
      }
    }
  },
  "tmp": {
    "type": "directory",
    "children": {
      "cache": {
        "type": "directory",
        "children": {}
      }
    }
  }
}
JSON

#Там вообще всё есть

echo "--- Тест всех команд с обработкой ошибок ---"
python3 Pr1.py --vfs-json final_test_vfs.json --vfs-name "final" --debug << 'EOF'
# Демонстрация всех этапов
echo "=== ЭТАП 1: Базовые команды ==="
pwd
ls
echo "Переменная HOME: $HOME"

echo -e "\n=== ЭТАП 2: Навигация по VFS ==="
cd home/user/documents
pwd
ls -la
cd work/project1/src
pwd
ls -l
cat main.py
cd ../../..

echo -e "\n=== ЭТАП 3: Команды date и who ==="
date
date +%Y-%m-%d
who

echo -e "\n=== ЭТАП 4: Работа с файлами ==="
cat file1.txt
cat file2.txt
cd /var/log
cat system.log

echo -e "\n=== ЭТАП 5: Управление директориями ==="
cd /tmp
ls
rmdir cache
ls
cd /home/user/documents/work
ls
rmdir empty_dir
ls
rmdir project1  # Должно не сработать - не пустая

echo -e "\n=== Тест обработки ошибок ==="
cd /nonexistent
ls invalid_path
cat missing_file.txt
rmdir /  # Нельзя удалить корень
rmdir /home/user/documents/work/project1  # Не пустая
rmdir missing_dir
unknown_command
date invalid_format

echo -e "\n=== Финальные проверки ==="
cd /
pwd
ls -l
echo "Тест завершен успешно!"
exit 0
EOF

# Очистка
rm -f final_test_vfs.json

echo -e "\nВСЕ ЭТАПЫ ЗАВЕРШЕНЫ"