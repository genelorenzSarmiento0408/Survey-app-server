"""The file is the server for our application named "Survey App"."""
import os
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
from dotenv import load_dotenv
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# from jwt import encode
load_dotenv()

hasher = PasswordHasher()
app = FastAPI(title="Survey App", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class User(BaseModel):
    """Class that contains a basic information about a user.

    Attributes
    ----------
    username: str
        It is the username of the user

    password: str
        It is the encrypted string password of the user
    """

    username: str
    password: str


class Form(BaseModel):
    """Class that contains the basic information in a form, provided by the user.

    Attributes
    ----------
    author: str
        The username of the author of the Form

    name: str
        The name of the form

    description: str | None
        The description of the form
    """

    author: str
    name: str
    description: str | None


class Question(BaseModel):
    """A class the contains the basic information in a question.

    Attributes
    ----------
    username: str
        The username of the author that has created the username

    form_id: str
        The ID of the form to be connected to the question

    name: str
        The name of the question

    answers: list
        The answers to that question

    required: bool
        The question is required or not
    """

    username: str
    form_id: str
    name: str
    answers: list | None


CONNECTION_STRING = os.getenv("DB_URL")


def get_db():
    """Get the database named "pollingpairDB"."""
    client = MongoClient(CONNECTION_STRING)
    return client["pollingpairDB"]


users_collection = get_db()["Users"]
forms_collection = get_db()["Forms"]


def find_user(username: str):
    """Find user function finds the user via the username.

    Parameters
    ----------
    username: str
        The username that the function will find.

    Returns
    -------
    pymongo.collection.Collection | None
        Returns a collection if a user has found in the database.
    """
    return users_collection.find_one({"username": username})


@app.get("/")
def root():
    """Redirect documentation, for now."""
    return RedirectResponse("/docs")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(exc: RequestValidationError):
    """It will return another attribute named "error"."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "error": "One or more of the information filled up is blank",
        },
    )


@app.post("/register")
def register_user(user: User):
    """Register the user via the User Object, then, it will add it in the DB.

    Parameters
    ----------
    user: User
        The information of the user

    Returns
    -------
    dict
        If registering was succesful, it returns a dictionary.
    """
    user_founded = find_user(user.username)
    if user_founded:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "The username has been found, please try another username"
            },
        )
    password = hasher.hash(user.password)
    data = {"username": user.username, "password": password}
    users_collection.insert_one(data)
    data["_id"] = str(data["_id"])
    return data


@app.post("/login")
def login_user(user: User):
    """Logins the user if the user exists.

    Parameters
    ----------
    user: User
        The information of the user

    Returns
    -------
    dict
    """
    user_founded = find_user(user.username)
    if user_founded is None:
        return JSONResponse(
            status_code=400, content={"error": "User not found, please register"}
        )
    user_founded["_id"] = str(user_founded["_id"])
    user_founded["user_id"] = str(user_founded["_id"])
    try:
        hasher.verify(user_founded["password"], user.password)
    except VerifyMismatchError:
        return JSONResponse(
            status_code=400,
            content={"error": "The username and password doesn't match"},
        )
    return {"status": "OK"}


@app.get("/forms/{username}")
def get_user(username: str):
    """Returns the forms created by the user.

    Parameters
    ----------
    username: str
        The username parameter is used to find the forms created by the user
    """
    username_found = find_user(username)
    if username_found is None:
        return JSONResponse(status_code=400, content={"error": "Username not found"})
    forms_found = forms_collection.find({"username": username})
    if forms_found is None:
        return []
    forms = []
    for form_found in forms_found:
        form_found["_id"] = str(form_found["_id"])
        forms.append(form_found)
    print(forms)
    return forms


@app.post("/form")
def post_form(form: Form):
    """Create a form using the form parameter and store it in a database.

    Parameters
    ----------
    form: Form
        The form to be stored in the database
    Return
    ------

    """
    user_founded = find_user(form.author)
    print(user_founded)
    if user_founded is None:
        return JSONResponse(status_code=400, content={"error": "User not found"})
    if form.name == "":
        return JSONResponse(
            status_code=400,
            content={"error": "The name of the form is blank, please try again"},
        )
    data = {
        "author": user_founded["username"],
        "name": form.name,
        "description": form.description or "",
    }
    forms_collection.insert_one(data)
    data["_id"] = str(data["_id"])
    forms_collection.find_one_and_update(
        {"_id": data["_id"]},
        {"$set": {"id": str(data["_id"])}},
    )
    return data


@app.post("/question")
def add_question(question: Question):
    """The function will add the question provided in the database.

    Parameters
    ----------
    question: Question
        The question to be stored in the database
    """
    if question.form_id == "":
        return JSONResponse(
            status_code=400,
            content={
                "error": "The form id is blank, please try again with the form form id"
            },
        )
    form_founded = forms_collection.find_one({"id": question.form_id})
    if form_founded is None:
        return JSONResponse(status_code=400, content={"error": "The form is not found"})
    print(form_founded)
    questions_founded = form_founded["questions"]
    for question_founded in questions_founded:
        if question_founded["name"] == question.name:
            return JSONResponse(
                status_code=400,
                content={
                    "error": """Another question exists,
                    please try again with another question"""
                },
            )
    questions_founded.append(
        {
            "name": question.name,
        }
    )
    forms_collection.update_one(
        {"id": question.form_id}, {"$set": {"questions": questions_founded}}
    )
    form_founded["_id"] = str(form_founded["_id"])
    return form_founded


@app.post("/answer/{form_id}")
def answer_form(form_id, answers: list):
    """The function take the form id, then insert the answer in the answers.

    Parameters
    ----------
    form_id
        The ID of the form that will insert the answer

    answers: list
        The answers that the user gave
    """
    form_founded = forms_collection.find_one({"id": form_id})

    questions = form_founded["questions"]

    if form_founded is None:
        return JSONResponse(status_code=400, content={"error": "The form is not found"})
    if not answers:
        return JSONResponse(status_code=400, content={"error": "The answers are blank"})
    for answer in answers:
        if type(answer) is not dict:
            return JSONResponse(
                status_code=400,
                content={"error": "The answer should be in a dictionary/JSON"},
            )
        try:
            if not answer["question"] or not answer["answer"]:
                return JSONResponse(
                    status_code=400,
                    content={"error": "The question or the answer is blank"},
                )
            question_names = []
            for question in questions:
                question_names.append(question["name"])
            if not question_names:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": """The user haven't created a question in the form yet,
                        please try again"""
                    },
                )
            for i, question_name in enumerate(question_names):
                if answer["question"] not in question_names:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "The question is not in the form"},
                    )
                answers_found = form_founded["questions"][i]["answers"]
                if answer["question"] == question_name:
                    answers_found.append(answer["answer"])
                    forms_collection.update_one(
                        {"id": form_id},
                        {"$set": {f"questions.{i}.answers": answers_found}},
                    )
                    form_founded["_id"] = str(form_founded["_id"])
                    return form_founded
        except KeyError:
            return JSONResponse(
                status_code=400,
                content={"error": "The question or the answer is blank"},
            )
