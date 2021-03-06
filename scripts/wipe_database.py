#!/usr/env python
from mmeds.database.database import Database
from sys import argv


def wipe_db():
    with Database(testing=len(argv) > 1) as db:
        db.delete_mongo_documents()

    with Database(testing=len(argv) > 1) as db:
        db.delete_sql_rows()


if __name__ == '__main__':
    wipe_db()
