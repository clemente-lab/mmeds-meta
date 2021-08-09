import click
from test_server_generated import TestServer
from pathlib import Path

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--path', required=True, type=click.Path(exists=True),
                help='Path to directory containing test files')

def main(path):
    server = TestServer()
    TestServer.setup_server()
    top_dir = Path(path)
    sub_directories = ['blank_column_tests', 'na_column_tests', 'other_column_tests', 'number_column_tests', 'date_column_tests']

    total_directories = []
    for directory in sub_directories:
        total_directories.append(top_dir / directory / 'specimen')
        total_directories.append(top_dir / directory / 'subject')

    for directory in total_directories:
        for test_file in directory.glob('*.tsv'):
            server.upload_otu_data(test_file)


if __name__ == '__main__':
    main()
