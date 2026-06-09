from flask import Blueprint, render_template

page_bp = Blueprint("pages", __name__)

@page_bp.route("/")
@page_bp.route("/index.html")
def index():
    return render_template("index.html")

@page_bp.route("/login.html")
@page_bp.route("/cadastro.html")
def login():
    return render_template("login.html")

@page_bp.route("/dashboard.html")
def dashboard():
    return render_template("dashboard.html")

@page_bp.route("/criar-acervo.html")
def criar_acervo():
    return render_template("criar-acervo.html")

@page_bp.route("/404.html")
def not_found_page():
    return render_template("404.html")
