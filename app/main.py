from typing import Annotated
import copy

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import starlette.status as status
import psycopg


app = FastAPI()

# Подключение директории шаблонов
templates = Jinja2Templates(directory="./templates")


def open_session(func):
    """
    Декоратор для получения сессии к БД.
    """
    def wrapper(*args, **kwargs):
        with psycopg.connect(host="localhost",
                             port=5433,
                             dbname="categoryes",
                             user="root_user",
                             password="root_password") as connection:
            with connection.cursor() as cursor:
                data = func(*args, session=cursor, **kwargs)
                return data
            connection.commit()
    return wrapper


def convert_to_dict(category: tuple) -> dict:
    """
    Сформировать словарь категории из кортежа.
    """
    if category is not None:
        category_dict = {
                    "id": category[0],
                    "name": category[1],
                    "parent_id": category[2]
        }
        return category_dict
    else:
        return None


def get_category_as_tree(tree: dict,
                         categoryes: tuple,
                         parent=None) -> dict:
    """
    Сформировать дерево из списка категорий.
    Рекурсивная функция, выполняющая запись словаря в родительский элемент.
    @tree: пустой словарь для построения дерева.
    @categoryes: кортеж с категорями из БД

    @parent: идентификатор родительской категории.
    При пустом словаре идентификатор указывает
    на несуществующий элемент родителя.
    """
    count = 0
    while count < len(categoryes):
        category = convert_to_dict(categoryes[count])
        if category["parent_id"] is parent:
            # Добавляем родительские категории
            tree[category["id"]] = category
            categoryes.pop(count)
            continue
        elif category["parent_id"] in tree:
            if "childrens" not in tree[category["parent_id"]]:
                tree[category["parent_id"]]["childrens"] = {}
            tree[category["parent_id"]]["childrens"] = get_category_as_tree(
                                    tree[category["parent_id"]]["childrens"],
                                    categoryes,
                                    parent=category["parent_id"])
            continue
        count += 1
    return tree


@open_session
def get_all_categoryes(session=None) -> tuple:
    """
    Получить все категории из БД.
    """
    session.execute("SELECT id, name, parent_id FROM category "
                    "ORDER BY parent_id is not null, parent_id, name asc;")
    categoryes = session.fetchall()
    return categoryes


@open_session
def get_category_by_id(id: int, session=None) -> dict:
    """
    Получить категорию по переданному идентификатору.
    @id: идентификатор категории
    """
    session.execute("SELECT id, name, parent_id FROM category "
                    f"WHERE category.id = {id}")
    categoryes = session.fetchone()
    return convert_to_dict(categoryes)


@open_session
def save_category(name: str,
                  parent_id: int,
                  session=None) -> int:
    """
    Сохранить категорию.
    @name: название категории
    @parent_id: идентификатор родительской категории
    Возвращает идентификатор сохраненной категории.
    """
    session.execute("INSERT INTO category(name, parent_id) "
                    f"VALUES('{str(name)}', {parent_id}) RETURNING id")
    return session.fetchone()[0]


@open_session
def delete_category(id: int, session=None) -> int:
    """
    Удаление категории по идентификатору
    """
    session.execute(f"""DELETE FROM category WHERE id = {id}""")
    return 0


@open_session
def update_category(id: int, name: str, session=None) -> int:
    """
    Обновление названия категории по идентификатору категории.
    """
    session.execute(f"""UPDATE category SET name = '{name}' WHERE id = {id}""")
    return 0


@open_session
def get_parent_categoryes(id: int, session=None) -> tuple:
    """
    Рекурсивный запрос для получения категории и всех родительских.
    """
    session.execute("WITH RECURSIVE vc AS ("
                    "SELECT id, name, parent_id "
                    "FROM category "
                    f"WHERE id = {id} "
                    "UNION "
                    "SELECT c.id, c.name, c.parent_id "
                    "FROM category c "
                    "INNER JOIN vc vc1 ON c.id = vc1.parent_id "
                    ") SELECT * FROM vc "
                    "ORDER BY parent_id is not null, parent_id;")
    return session.fetchall()


@app.get("/", response_class=HTMLResponse)
def get_all_category_view(request: Request):
    """
    Представление для отображения главной
    страницы со всеми категориями.
    """
    categoryes = get_all_categoryes()
    category_tree = get_category_as_tree({}, copy.deepcopy(categoryes))
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"category_tree": category_tree, "categoryes": categoryes})


@app.get("/category/{category_id}", response_class=HTMLResponse)
def get_category_view(category_id: int,
                      request: Request):
    """
    Представление для отображения категории.
    """
    bread_crumps = get_parent_categoryes(category_id)
    category = get_category_by_id(category_id)
    if category is not None:
        return templates.TemplateResponse(
            request=request,
            name="category_page.html",
            context={"category": category, "bread_crumps": bread_crumps})
    else:
        raise HTTPException(status_code=404,
                            detail="Категории не существует")


@app.post("/new_category", response_class=HTMLResponse)
def save_category_view(parent: Annotated[str, Form()],
                       name: Annotated[str, Form()],
                       request: Request):
    """
    Эндпоинт для сохранения новой категории.
    """
    parent_id = "NULL" if parent == "None" else int(parent)
    name = name.strip()
    if len(name) > 0 and len(name) < 51:
        id = save_category(name, parent_id)
        return RedirectResponse(
                    f"/category/{id}",
                    status_code=status.HTTP_302_FOUND)
    else:
        raise HTTPException(
            status_code=400,
            detail="Длина названия категории должно быть"
                   "больше 0 и не больше 50 символов"
        )


@app.get("/category/delete/{category_id}", response_class=RedirectResponse)
def delete_category_view(category_id: int):
    """
    Endpoint для удаления категории по идентфикатору.
    """
    code = delete_category(category_id)
    if code == 0:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    else:
        raise HTTPException(
            status_code=500,
            detail="Что-то пошло не так."
        )


@app.post("/category/update/{category_id}")
def update_category_view(category_id: int,
                         name: Annotated[str, Form()]):
    """
    Endpoint для сохранения изменений категории.
    """
    code = update_category(category_id, name)
    if code == 0:
        return RedirectResponse(f"/category/{category_id}",
                                status_code=status.HTTP_302_FOUND)
    else:
        raise HTTPException(status_code=500,
                            detail="Что-то пошло не так.")
