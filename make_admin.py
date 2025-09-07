import sqlite3

USERNAME = "bbnnng"  # имя пользователя, которому назначаем роль админа

with sqlite3.connect("database.db") as conn:
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        conn.commit()
        print("Колонка 'role' добавлена.")
    except Exception as e:
        print("Колонка уже существует или ошибка:", e)

    c.execute("SELECT id, username, role FROM users WHERE username=?", (USERNAME,))
    user = c.fetchone()

    if not user:
        print(f"Пользователь с username='{USERNAME}' не найден.")
    else:
        c.execute("UPDATE users SET role='admin' WHERE username=?", (USERNAME,))
        conn.commit()
        print(f"Пользователь {USERNAME} теперь админ!")

        c.execute("SELECT id, username, role FROM users WHERE username=?", (USERNAME,))
        print("Обновлённые данные:", c.fetchone())
