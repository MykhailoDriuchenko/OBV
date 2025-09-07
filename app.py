import os
import sqlite3
from flask import Flask, jsonify, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "O>cf#pR?*#p#m/NCYy(ju~FCG4CDA&>rwp,V);X99fL–FRNo}y"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ===== DB INIT =====
def init_db():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # Пользователи
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        role TEXT DEFAULT 'user'
                    )""")
        # Объявления
        c.execute("""CREATE TABLE IF NOT EXISTS ads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        title TEXT,
                        description TEXT,
                        price INTEGER,
                        image TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )""")
        # Избранное
        c.execute("""CREATE TABLE IF NOT EXISTS favorites (
                        user_id INTEGER,
                        ad_id INTEGER,
                        PRIMARY KEY(user_id, ad_id),
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(ad_id) REFERENCES ads(id)
                    )""")
        conn.commit()

# ===== HELPERS =====

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_db():
    return sqlite3.connect("database.db")

def current_user():
    if "user_id" in session:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
            return c.fetchone()
    return None

def is_admin():
    user = current_user()
    return user and user[3] == "admin"

# ===== ROUTES =====
@app.route("/")
def index():
    category = request.args.get("category")
    q = request.args.get("q", "")
    sort = request.args.get("sort")
    user = current_user()

    with get_db() as conn:
        c = conn.cursor()
        query = "SELECT * FROM ads WHERE 1=1"
        params = []

        if category:
            query += " AND category=?"
            params.append(category)
        if q:
            query += " AND title LIKE ?"
            params.append(f"%{q}%")

        # Сортировка по числовому значению price
        if sort == "asc":
            query += " ORDER BY CAST(price AS INTEGER) ASC"
        elif sort == "desc":
            query += " ORDER BY CAST(price AS INTEGER) DESC"

        c.execute(query, tuple(params))
        ads = c.fetchall()

        fav_ids = []
        if user:
            c.execute("SELECT ad_id FROM favorites WHERE user_id=?", (user[0],))
            fav_ids = [row[0] for row in c.fetchall()]

    return render_template("index.html", ads=ads, user=user, fav_ids=fav_ids)


@app.route("/search_suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()

    if query:
        cursor.execute(
            "SELECT title FROM ads WHERE LOWER(title) LIKE ? LIMIT 10",
            (f"%{query}%",)
        )
        results = [row["title"] for row in cursor.fetchall()]
    else:
        results = []

    conn.close()
    return jsonify(results)

# --- Страница поиска ---
@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    if q:
        cursor.execute(
            "SELECT * FROM ads WHERE title LIKE ? OR description LIKE ?",
            (f"%{q}%", f"%{q}%")
        )
        ads = cursor.fetchall()
    else:
        ads = []

    conn.close()
    return render_template("index.html", ads=ads, user=session.get("user"), title="Результаты поиска")

@app.route("/api/ads")
def api_ads():
    q = request.args.get("q", "")
    sort = request.args.get("sort")
    user = current_user()
    with get_db() as conn:
        c = conn.cursor()
        query = "SELECT * FROM ads WHERE 1=1"
        params = []

        if q:
            query += " AND title LIKE ?"
            params.append(f"%{q}%")

        if sort == "asc":
            query += " ORDER BY price ASC"
        elif sort == "desc":
            query += " ORDER BY price DESC"

        c.execute(query, tuple(params))
        ads = c.fetchall()

        # Преобразуем для JSON
        result = []
        fav_ids = []
        if user:
            c.execute("SELECT ad_id FROM favorites WHERE user_id=?", (user[0],))
            fav_ids = [row[0] for row in c.fetchall()]

        for ad in ads:
            result.append({
                "id": ad[0],
                "title": ad[2],
                "description": ad[3],
                "price": ad[4],
                "image": ad[5],
                "is_fav": ad[0] in fav_ids
            })

    return result


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        try:
            with get_db() as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                          (username, password, "user"))
                conn.commit()
            flash("Регистрация успешна! Войдите.")
            return redirect("/login")
        except:
            flash("Имя пользователя занято.")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            user = c.fetchone()
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            return redirect("/")
        flash("Неверные данные.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")

@app.route("/add", methods=["POST"])
def add_ad():
    if not is_admin():
        flash("Только администраторы могут добавлять объявления.")
        return redirect("/")
    title = request.form["title"]
    description = request.form["description"]
    price = int(request.form["price"])  # цена как целое число

    image_file = request.files.get("image")
    filename = None
    if image_file and image_file.filename.strip():
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image_file.save(image_path)

    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO ads (user_id, title, description, price, image) VALUES (?, ?, ?, ?, ?)",
                  (session["user_id"], title, description, price, filename))
        conn.commit()
    return redirect("/")

@app.route("/edit/<int:ad_id>", methods=["GET", "POST"])
def edit_ad(ad_id):
    if not is_admin():
        flash("Редактировать может только администратор.")
        return redirect("/")
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM ads WHERE id=?", (ad_id,))
        ad = c.fetchone()
    if not ad:
        return redirect("/")

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        price = int(request.form["price"])

        image_file = request.files.get("image")
        filename = ad[5]  # старое фото по умолчанию
        if image_file and image_file.filename.strip():
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(image_path)

        with get_db() as conn:
            c = conn.cursor()
            c.execute("UPDATE ads SET title=?, description=?, price=?, image=? WHERE id=?",
                      (title, description, price, filename, ad_id))
            conn.commit()
        return redirect("/")

    return render_template("edit.html", ad=ad)

@app.route("/delete/<int:ad_id>", methods=["POST"])
def delete_ad(ad_id):
    if not is_admin():
        flash("Удалять объявления может только администратор.")
        return redirect("/")
    
    with get_db() as conn:
        c = conn.cursor()
        # Получаем имя файла изображения перед удалением
        c.execute("SELECT image FROM ads WHERE id=?", (ad_id,))
        ad = c.fetchone()
        if ad and ad[0]:  # если есть изображение
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], ad[0])
            if os.path.exists(image_path):
                os.remove(image_path)  # удаляем файл
        # Удаляем объявление из базы
        c.execute("DELETE FROM ads WHERE id=?", (ad_id,))
        conn.commit()
    
    flash("Объявление удалено")
    return redirect("/")



@app.route("/ad/<int:ad_id>")
def view_ad(ad_id):
    user = current_user()
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT ads.*, users.username FROM ads JOIN users ON ads.user_id = users.id WHERE ads.id=?", (ad_id,))
        ad = c.fetchone()
        fav_ids = []
        if user:
            c.execute("SELECT ad_id FROM favorites WHERE user_id=?", (user[0],))
            fav_ids = [row[0] for row in c.fetchall()]
    if not ad:
        return "Объявление не найдено", 404
    return render_template("ad.html", ad=ad, user=user, fav_ids=fav_ids)

# ===== Избранное =====
@app.route("/favorite/<int:ad_id>", methods=["POST"])
def favorite_ad(ad_id):
    user = current_user()
    if not user:
        flash("Сначала войдите в систему")
        return redirect("/login")
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM favorites WHERE user_id=? AND ad_id=?", (user[0], ad_id))
        if c.fetchone():
            c.execute("DELETE FROM favorites WHERE user_id=? AND ad_id=?", (user[0], ad_id))
            conn.commit()
            flash("Удалено из избранного")
        else:
            c.execute("INSERT INTO favorites(user_id, ad_id) VALUES(?, ?)", (user[0], ad_id))
            conn.commit()
            flash("Добавлено в избранное")
    return redirect(request.referrer or "/")




@app.route("/favorites")
def favorites():
    user = current_user()
    if not user:
        flash("Сначала войдите в систему")
        return redirect("/login")

    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")

    query = """
        SELECT ads.* FROM ads
        JOIN favorites ON ads.id = favorites.ad_id
        WHERE favorites.user_id=?
    """
    params = [user[0]]

    if min_price:
        query += " AND price>=?"
        params.append(float(min_price))

    if max_price:
        query += " AND price<=?"
        params.append(float(max_price))

    with get_db() as conn:
        c = conn.cursor()
        c.execute(query, tuple(params))
        ads = c.fetchall()

        # список избранного для активных сердечек
        c.execute("SELECT ad_id FROM favorites WHERE user_id=?", (user[0],))
        fav_ids = [row[0] for row in c.fetchall()]

    return render_template("favorites.html", ads=ads, user=user, fav_ids=fav_ids)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
