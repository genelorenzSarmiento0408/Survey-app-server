"""The file is the server for our application named ""Survey App"""
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
    username: str
        The username of the author of the Form

    name: str
        The name of the form

    description: str | None
        The description of the form

    questions: list | None
        The questions in the form
    """

    username: str
    name: str
    description: str | None
    questions: list | None


types_of_input = [
    "checkbox",
    "radio",
    "text"
]


class Question(BaseModel):
    """A class the contains the basic information in a question.

    Attributes
    ----------
    username: str
        The username of the author that has created the username

    form_id: str
        The ID of the form to be connected to the question

    question: str
        The question itself

    type_of_input: str
        The type of input box that user should fill up

    possible_answers: list | None
        The possible answers that the user can answer

    answers: list
        The answers to that question
    """

    username: str
    form_id: str
    question: str
    type_of_input: str
    possible_answers: list | None
    answers: list | None


CONNECTION_STRING = os.getenv("CONNECTION_STRING")


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
    return users_collection.find_one({
        "username": username
    })


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
            "error": "One or more of the information filled up is blank"
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
                "error":
                "The username has been found, please try another username"
            }
        )
    password = hasher.hash(user.password)
    data = {
        "username": user.username,
        "password": password,
        "forms": []
    }
    forms_collection.insert_one(data)
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
            status_code=200,
            content={"error": "User not found, please register"}
        )
    user_founded["_id"] = str(user_founded["_id"])
    user_founded["user_id"] = str(user_founded["_id"])
    try:
        hasher.verify(user_founded["password"], user.password)
    except VerifyMismatchError:
        return JSONResponse(
            status_code=400,
            content={"error": "The username and password doesn't match"}
        )
    return user_founded


@app.get("/users/{username}")
def get_user(username: str):
    """Returns the forms created by the user.

    Parameters
    ----------
    username: str
        The username parameter is used to find the forms created by the user
    """
    username_found = find_user(username)
    if username_found is None:
        return JSONResponse(
            status_code=400,
            content={"error": "Username not found"}
        )
    forms_found = forms_collection.find({
        "username": username
    })
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
    user_founded = find_user(form.username)
    print(user_founded)
    if user_founded is None:
        return JSONResponse(
            status_code=400,
            content={"error": "User not found"}
        )
    if form.name == "":
        return JSONResponse(
            status_code=400,
            content={
                "error":
                "The name of the form is blank, please try again"
            }
        )
    if form.questions is None:
        questions = []
    if form.description is None:
        description = ""
    data = {
        "username": user_founded["username"],
        "name": form.name,
        "description": description,
        "questions": questions
    }
    forms_collection.insert_one(data)
    forms_collection.find_one_and_update(
        {"_id": data["_id"]},
        {"$set": {
            "id": str(data["_id"])
        }},
    )
    data["_id"] = str(data["_id"])
    data["id"] = str(data["_id"])
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
                "error":
                "The form id is blank, please try again with the form form id"
            }
        )
    form_founded = forms_collection.find_one({
        "id": question.form_id
    })
    print(form_founded)
