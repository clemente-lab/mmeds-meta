from mmeds.database.database import Database
import mmeds.util as util
import mmeds.config as fig
import pandas as pd
import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-w', '--where', required=True, help="An SQL WHERE query")
@click.option('-n', '--study-name', required=True, help="Name for the new study")
@click.option('-os', '--out-specimen', help="Output for specimen tsv, prints to stdout if none given")
@click.option('-ou', '--out-subject', help="Output for subject tsv, prints to stdout if none given")
def create_meta_study(where, study_name, out_specimen, out_subject):
    """ Script that takes in an SQL where clause, queries it to the database,
    gets back a list of studies and sample ids, creates new subject and specimen files
    from those, and writes to disk or stdout """
    with Database(testing=fig.TESTING) as db:
        entries, paths = db.query_meta_analysis(where)

    df = util.concatenate_metadata_subsets(entries, paths)
    subj_df, spec_df = util.split_metadata(df, new_study_name=study_name)

    if out_specimen and out_subject:
        subj_df.to_csv(out_subject, sep='\t', index=False)
        spec_df.to_csv(out_specimen, sep='\t', index=False)
    else:
        print(subj_df)
        print(spec_df)


if __name__ == '__main__':
    create_meta_study()
