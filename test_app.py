# test_app.py
from fastapi import FastAPI
from sqlite_webpanel import mount_sqlite_panel

app = FastAPI()
mount_sqlite_panel(app, db_path="test.db")