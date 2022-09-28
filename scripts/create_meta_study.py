from mmeds.database.database import Database

where = "ColumnA=357 and `5column` != 'farts' OR this_column >=65"

with Database(testing=True) as db:
    db.query_meta_analysis(where)
