from mmeds.database.database import Database
import mmeds.util as util
import mmeds.config as fig
import pandas as pd
import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-w', '--where', required=True, help="An SQL WHERE query")
def create_meta_study(where):

    with Database(testing=True) as db:
        entries, paths = db.query_meta_analysis(where)

    print(entries, paths)

    df = util.concatenate_metadata_subsets(entries, paths)
    subj_df, spec_df = util.split_metadata(df)

    print(subj_df)
    print(spec_df)


if __name__ == '__main__':
    create_meta_study()
