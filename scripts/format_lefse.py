import pandas as pd
import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--i-table', required=True, help='TSV extracted from a Qiime2 FeatureTable')
@click.option('-m', '--metadata-file', required=True, help='Qiime2 formatted mapping file')
@click.option('-c', '--metadata-column-class', required=True, help='Main metadata column on which to perform LEfSe analyis')
@click.option('-s', '--metadata-column-subclass', required=False, help='Subclass on which to perform LEfSe analysis')
@click.option('-u', '--metadata-column-subjects', required=False, help='If provided, column values will replace the given SampleIDs')
@click.option('-o', '--o-table', required=True, help='Output TSV ready for LEfSe\'s "format_input.py"')
def format_table(i_table, metadata_file, metadata_column_class, metadata_column_subclass, metadata_column_subjects, o_table):
    path_df = pd.read_csv(i_table, sep='\t', header=None, low_memory=False)
    mdf = pd.read_csv(metadata_file, sep='\t', header=[0, 1])

    categories = {}
    for i, cell in enumerate(mdf['#SampleID']['#q2:types']):
        if cell not in categories:
            categories[cell] = {}
        categories[cell][metadata_column_class] = mdf[metadata_column_class]['categorical'][i]

        if metadata_column_subclass:
            categories[cell][metadata_column_subclass] = mdf[metadata_column_class]['categorical'][i]

        if metadata_column_subjects:
            categories[cell][metadata_column_subjects] = mdf[metadata_column_subjects]['categorical'][i]


    t = [metadata_column_class]
    for i, cell in enumerate(path_df.loc[0]):
        if i == 0:
            continue
        t.append(categories[cell][metadata_column_class])
    path_df.loc[len(path_df.index)] = t

    if metadata_column_subclass:
        t = [metadata_column_subclass]
        for i, cell in enumerate(path_df.loc[0]):
            if i == 0:
                continue
            t.append(categories[cell][metadata_column_subclass])
        path_df.loc[len(path_df.index)] = t

    if metadata_column_subjects:
        t = [metadata_column_subjects]
        for i, cell in enumerate(path_df.loc[0]):
            if i == 0:
                continue
            t.append(categories[cell][metadata_column_subjects])
        path_df.loc[len(path_df.index)] = t

    path_df.to_csv(o_table, sep='\t', index=False, na_rep='nan')


if __name__ == '__main__':
    format_table()