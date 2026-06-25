# from online_restaurant_db import Session, Users

# session = Session()

# user = session.query(Users).filter_by(nickname="kosh").first()

# if user:
#     user.is_admin = True
#     session.commit()
#     print(f"Користувач {user.nickname} тепер є АДМІНІСТРАТОРОМ!")
# else:
#     print("Користувача з таким нікнеймом не знайдено. Спочатку зареєструй його на сайті.")

# session.close()