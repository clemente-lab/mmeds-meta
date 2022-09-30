from mmeds.database.database import Database

where = "Height > 4"

with Database(testing=True) as db:
    db.query_meta_analysis(where)
