import os
import uuid
import secrets
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from geopy.distance import geodesic
from flask_login import login_required, current_user, login_user, logout_user, LoginManager
from online_restaurant_db import Menu, Session, Users, Orders, Reservation
from sqlalchemy import or_
MARGANETS_COORDS = (47.6382, 34.6346)  
KYIV_RADIUS_KM = 50  

TABLE_NUM = {
    "2": 10, 
    "4": 5,   
    "6": 2    
}

app = Flask(__name__)
app.config['SECRET_KEY'] = '#cv)3v7w$*s3fk;5c!@y0?:?№3"9#'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    with Session() as session_db:
        return session_db.query(Users).filter_by(id=user_id).first()

@app.before_request
def generate_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)

@app.after_request
def apply_csp(response):
    nonce = getattr(g, 'csp_nonce', secrets.token_urlsafe(16))
    csp = (
        f"default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com https://images.unsplash.com; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        f"font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.set_cookie('nonce', nonce)
    return response

@app.context_processor
def inject_variables():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    
    nonce = getattr(g, 'csp_nonce', '')
    return dict(
        csrf_token=session["csrf_token"],
        csp_nonce=lambda: nonce
    )

def setup_test_data():
    menu_dir = os.path.join('static', 'menu')
    if not os.path.exists(menu_dir):
        os.makedirs(menu_dir, exist_ok=True)

    images_to_download = {
        "burger.jpg": "https://images.silpo.ua/v2/products/1000x1000/webp/031b8ba9-01db-4135-bd9e-6128feac00eb.png",
        "pizza.jpg": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=500&q=80",
        "milkshake.jpg": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRGss0Uq7YHsjFRaS3nQcQlXyV-EO_CCs83ng&s"
    }

    for filename, url in images_to_download.items():
        file_path = os.path.join(menu_dir, filename)
        if not os.path.exists(file_path):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(file_path, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception:
                pass

    with Session() as db:
        burger_exists = db.query(Menu).filter(Menu.name.ilike('%Бургер Чізмікс%')).first()
        if not burger_exists:
            test_burger = Menu(
                name="Бургер Чізмікс",
                ingredients="Булка з кунжутом, соковита котлета, подвійний сир чеддер, маринований огірок, фірмовий соус BBQ",
                description="Соковита яловича котлета, подвійний чеддер, маринована цибуля та хрусткі огірочки у ніжній булці з BBQ соусом.",
                price="145",
                weight="320",
                file_name="burger.jpg",
                active=True
            )
            db.add(test_burger)
            
        pizza_exists = db.query(Menu).filter(Menu.name.ilike('%Піца Пепероні%')).first()
        if not pizza_exists:
            test_pizza = Menu(
                name="Піца Пепероні",
                ingredients="Італійське тісто, томатний соус, гостра пепероні, подвійна моцарела, орегано",
                description="Моцарела, гостра італійська пепероні та фірмовий томатний соус на тонкому хрусткому тісті.",
                price="195",
                weight="450",
                file_name="pizza.jpg",
                active=True
            )
            db.add(test_pizza)

        milk_exists = db.query(Menu).filter(Menu.name.ilike('%Полуничний Мілкшейк%')).first()
        if not milk_exists:
            test_milkshake = Menu(
                name="Полуничний Мілкшейк",
                ingredients="Молоко, вершкове морозиво, свіжа полуниця, збиті вершки",
                description="Класичний освіжаючий густий мілкшейк зі смаком стиглої полуниці та ніжною шапкою зі збитих вершків.",
                price="75",
                weight="400",
                file_name="milkshake.jpg",
                active=True
            )
            db.add(test_milkshake)
            
        db.commit()

@app.route('/')
@app.route('/home')
def home():
    with Session() as session_db:
        all_positions = session_db.query(Menu).all()
    return render_template('home.html', all_positions=all_positions)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        email = request.form['email']
        password = request.form['password']

        with Session() as cursor:
            if cursor.query(Users).filter((Users.email==email) | (Users.nickname==nickname)).first():
                flash('Користувач з таким email або нікнеймом вже існує!', 'danger')
                return render_template('register.html')

            new_user = Users(nickname=nickname, email=email)
            new_user.set_password(password)
            cursor.add(new_user)
            cursor.commit()
            cursor.refresh(new_user)
            login_user(new_user)
            return redirect(url_for('home'))

    return render_template('register.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        password = request.form['password']

        with Session() as cursor:
            user = cursor.query(Users).filter_by(nickname=nickname).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('home'))

            flash('Неправильний nickname або пароль!', 'danger')

    return render_template('login.html')

@app.route("/add_pos", methods=['GET', 'POST'])
@login_required
def add_position():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        name = request.form['name']
        file = request.files.get('img')
        ingredients = request.form['ingredients']
        description = request.form['description']
        price = request.form['price']
        weight = request.form['weight']

        if not file or not file.filename:
            return 'Файл не вибрано або завантаження не вдалося'

        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        output_path = os.path.join('static/menu', unique_filename)

        with open(output_path, 'wb') as f:
            f.write(file.read())

        with Session() as cursor:
            new_position = Menu(name=name, ingredients=ingredients, description=description,
                                price=price, weight=weight, file_name=unique_filename, active=True)
            cursor.add(new_position)
            cursor.commit()

        flash('Позицію додано успішно!')

    return render_template('add_pos.html')

@app.route('/menu')
def menu():
    category = request.args.get('category', '').strip().lower()

    category_mapping = {
        'pizza': ['піца', 'пицца', 'пепероні', 'pizza'],
        'burgers': ['бургер', 'чізбургер', 'burger', 'чізмікс', 'котлета'],
        'potatoes': ['картопля', 'картошка', 'фрі', 'potato', 'селянськ'], 
        'drinks': ['напої', 'сік', 'кола', 'мілкшейк', 'коктейль', 'drink', 'шейк']
    }

    with Session() as session_db:
        if category in category_mapping:
            search_terms = category_mapping[category]
            conditions = []
            for term in search_terms:
                conditions.append(Menu.name.ilike(f"%{term}%"))
                conditions.append(Menu.ingredients.ilike(f"%{term}%"))
                conditions.append(Menu.description.ilike(f"%{term}%")) 
            
            all_positions = session_db.query(Menu).filter_by(active=True).filter(or_(*conditions)).all()
        elif category:
            all_positions = session_db.query(Menu).filter_by(active=True).filter(
                or_(
                    Menu.name.ilike(f"%{category}%"), 
                    Menu.ingredients.ilike(f"%{category}%"),
                    Menu.description.ilike(f"%{category}%")
                )
            ).all()
        else:
            all_positions = session_db.query(Menu).filter_by(active=True).all()
            
    return render_template('menu.html', all_positions=all_positions)
@app.route('/position/<name>', methods=['GET', 'POST'])
def position(name):
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        position_name = request.form.get('name')
        position_num = request.form.get('num')
        
        try:
            position_num = int(position_num)
        except (TypeError, ValueError):
            position_num = 1

        basket = session.get('basket', {})
        basket[position_name] = position_num
        session['basket'] = basket
        session.modified = True  

        flash('Позицію додано у кошик!')
        return redirect(request.referrer or url_for('menu'))

    with Session() as cursor:
        us_position = cursor.query(Menu).filter_by(active=True, name=name).first()
    return render_template('position.html', position=us_position)

@app.route('/remove_from_basket/<string:name>', methods=['POST'])
def remove_from_basket(name):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    basket = session.get('basket', {})
    if name in basket:
        basket.pop(name)
        session['basket'] = basket
        session.modified = True
        flash(f'"{name}" видалено з кошика!')

    return redirect(url_for('test_basket'))

@app.route('/test_basket')
def test_basket():
    basket = session.get('basket', {})
    return render_template("basket.html", basket=basket)


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/search')
def search():
    raw_query = request.args.get('query', '').strip()
    query = raw_query.replace('+', ' ')
    
    with Session() as cursor:
        if query:
            words = query.split()
            conditions = []
            
            for word in words:
                if not word.strip():
                    continue
                w_low = word.lower()
                w_cap = word.capitalize()
                
                conditions.append(Menu.name.ilike(f"%{w_low}%"))
                conditions.append(Menu.name.ilike(f"%{w_cap}%"))
                conditions.append(Menu.ingredients.ilike(f"%{w_low}%"))
                conditions.append(Menu.ingredients.ilike(f"%{w_cap}%"))
            
            if conditions:
                results = cursor.query(Menu).filter_by(active=True).filter(or_(*conditions)).all()
            else:
                results = cursor.query(Menu).filter_by(active=True).all()
        else:
            results = cursor.query(Menu).filter_by(active=True).all()
            
    return render_template('menu.html', all_positions=results)

@app.route("/account")
def account():
    return render_template('account.html')

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    basket = session.get('basket')
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        if not current_user.is_authenticated:
            flash("Для оформлення замовлення необхідно бути зареєстрованим")
        else:
            if not basket:
                flash("Ваш кошик порожній")
            else:
                with Session() as cursor:
                    new_order = Orders(order_list=basket, order_time=datetime.now(), user_id=current_user.id)
                    cursor.add(new_order)
                    cursor.commit()
                    session.pop('basket', None)
                    cursor.refresh(new_order)
                    return redirect(f"/my_order/{new_order.id}")

    return render_template('create_order.html', basket=basket)

@app.route('/my_orders')
@login_required
def my_orders():
    with Session() as cursor:
        us_orders = cursor.query(Orders).filter_by(user_id=current_user.id).all()
    return render_template('my_orders.html', us_orders=us_orders)

@app.route("/my_order/<int:id>")
@login_required
def my_order(id):
    with Session() as cursor:
        us_order = cursor.query(Orders).filter_by(id=id).first()
        total_price = sum(int(cursor.query(Menu).filter_by(name=i).first().price) * int(cnt) for i, cnt in us_order.order_list.items())
    return render_template('my_order.html', order=us_order, total_price=total_price)

@app.route('/cancel_order/<int:id>', methods=['POST'])
@login_required
def cancel_order(id):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403
    with Session() as cursor:
        order = cursor.query(Orders).filter_by(id=id, user_id=current_user.id).first()
        if not order:
            flash("Замовлення не знайдено", 'danger')
            return redirect(url_for('my_orders'))

        if order.user_id != current_user.id:
            flash("Ви не можете скасувати це замовлення", 'danger')
            return redirect(url_for('my_orders'))
        
        cursor.delete(order)
        cursor.commit()
        flash("Замовлення успішно скасовано", 'success')
    return redirect(url_for('my_orders'))

CHERNIVTSI_COORDS = (48.2917, 25.9352)
CHERNIVTSI_RADIUS_KM = 50.0

@app.route('/reserved', methods=['GET', 'POST'])
@login_required
def reserved():
    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        raw_table_type = str(request.form['table_type'])
        time_raw = request.form['time']

        if raw_table_type == "1-2":
            table_type = "2"
        elif raw_table_type == "3-4":
            table_type = "4"
        else:
            table_type = "6"

        try:
            reserved_time_start = datetime.strptime(time_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            return "Некоректний формат дати та часу", 400
            
        user_latitude = request.form['latitude']
        user_longitude = request.form['longitude']

        if not user_longitude or not user_latitude:
            return render_template('reserved.html', message='Ви не надали інформацію про своє місцезнаходження', csrf_token=session["csrf_token"])

        user_cords = (float(user_latitude), float(user_longitude))
        distance = geodesic(CHERNIVTSI_COORDS, user_cords).km
        if distance > CHERNIVTSI_RADIUS_KM:
            return "Ви знаходитеся в зоні, недоступній для бронювання"

        with Session() as cursor:
            user_reserved_check = cursor.query(Reservation).filter_by(user_id=current_user.id).first()
            if user_reserved_check:
                message = 'Можна мати лише одну активну бронь!'
                return render_template('reserved.html', message=message, csrf_token=session["csrf_token"])

            reserved_check = cursor.query(Reservation).filter_by(type_table=table_type).count()
            max_tables = TABLE_NUM.get(table_type, 0)

            if reserved_check < max_tables:
                new_reserved = Reservation(type_table=table_type, time_start=reserved_time_start, user_id=current_user.id)
                cursor.add(new_reserved)
                cursor.commit()
                message = f'Бронь на {reserved_time_start} столика успішно створено!'
            else:
                if max_tables == 0:
                    message = f'Помилка: тип стола "{table_type}" не підтримується закладом.'
                else:
                    message = f'На жаль, усі столи на цю кількість осіб наразі зайняті.'

            return render_template('reserved.html', message=message, csrf_token=session["csrf_token"])

    return render_template('reserved.html', csrf_token=session.get("csrf_token"))

@app.route('/reservations_check', methods=['GET', 'POST'])
@login_required
def reservations_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        reserv_id = request.form['reserv_id']
        with Session() as cursor:
            reservation = cursor.query(Reservation).filter_by(id=reserv_id).first()
            cursor.delete(reservation)
            cursor.commit()

    with Session() as cursor:
        all_reservations = cursor.query(Reservation).all()
        return render_template('reservations_check.html', all_reservations=all_reservations, csrf_token=session["csrf_token"])

@app.route('/check_menu', methods=['GET', 'POST'])
@login_required
def menu_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == 'POST':
        if request.form.get("csrf_token") != session['csrf_token']:
            return "Запит заблоковано!", 403

        position_id = request.form['pos_id']
        with Session() as cursor:
            position_obj = cursor.query(Menu).filter_by(id=position_id).first()
            if 'change_status' in request.form:
                position_obj.active = not position_obj.active
            elif 'delete_position' in request.form:
                cursor.delete(position_obj)
            cursor.commit()

    with Session() as cursor:
        all_positions = cursor.query(Menu).all()
    return render_template('check_menu.html', all_positions=all_positions, csrf_token=session["csrf_token"])

@app.route('/all_users')
@login_required
def all_users():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    with Session() as cursor:
        all_users = cursor.query(Users).with_entities(Users.id, Users.nickname, Users.email).all()
    return render_template('all_users.html', all_users=all_users)

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    with Session() as cursor:
        all_positions = cursor.query(Menu).all()
        all_reservations = cursor.query(Reservation).all()
        all_users = cursor.query(Users).all()

    return render_template('admin_dashboard.html',
                            all_positions=all_positions,
                            all_reservations=all_reservations,
                            all_users=all_users,
                            csrf_token=session["csrf_token"])

if __name__ == '__main__':
    setup_test_data()
    app.run(debug=True)