from collections import defaultdict, OrderedDict
from mmeds.error import InvalidConfigError, InvalidSQLError, InvalidModuleError, EmailError
from operator import itemgetter
from subprocess import run
from pathlib import Path
from os import environ
import os
from numpy import nan, int64, float64, datetime64
from tempfile import gettempdir
from re import sub
from time import sleep

import yaml
import gzip
import re
import pandas as pd
import numpy as np
import Levenshtein as lev
import mmeds.config as fig
from mmeds.logging import Logger
from subprocess import CalledProcessError


###########
# Classes #
###########
class SafeDict(dict):
    """ Used with str.format_map() to allow inserting formatting arguments in multiple stages """
    def __init__(self, dictionary):
        """ Initialize Safe Dict with a previously created dictionary """
        super().__init__(dictionary)
        self.missed = set()  # A set of parsing arguments

    def __getitem__(self, key):
        """ Update missed if an item is successfully formatted from the SafeDict """
        if key in self.missed:
            self.missed.remove(key)
        return super().__getitem__(key)

    def __missing__(self, key):
        """ Missing formating options are returned as is and the option is added to the missed set """
        self.missed.add(key)
        return '{' + key + '}'


#############
# Functions #
#############
def format_alerts(args):
    """ Takes a dictionary and performs formatting on any entries with the keys: 'error', 'warning', or 'success' """
    template = '''
    <div class="w3-card-4 w3-padding w3-panel w3-pale-{color} w3-border" >
    <h3> {alert}! </h3>
    <p> {message} </p>
    </div>
    '''
    for alert, color in [('error', 'red'), ('warning', 'yellow'), ('success', 'green')]:
        try:
            message = args[alert]
            # Ignore empty strings. They are sometimes passed to simplify logic in the webpages.
            if message:
                if isinstance(message, list):
                    outline = '<ul class="w3-ul w3-border">{}</ul>'
                    formatted = outline.format('\n'.join(['<li>{}</li>'.format(x) for x in message]))
                    args[alert] = template.format(alert=alert.capitalize(), message=formatted, color=color)
                else:
                    args[alert] = template.format(alert=alert.capitalize(), message=message, color=color)
        except KeyError:
            pass
    return args


def simplified_to_full(file_fp, output_fp, metadata_type, subject_type='human'):
    """
    Takes in a simplified MMEDs metadata file and expands it to the full format.
    ============================================================================
    :file_fp: The location of the simplified metadata on disk
    :output_fp: The location to write the full version of the metadata to
    :metadata_type: The type of metadata
    :subject_type: The type of subject
    """
    # Load the relvant template
    if metadata_type == 'subject':
        template = load_subject_template(subject_type)
        swapped = {}
    elif metadata_type == 'specimen':
        template = load_specimen_template()
        swapped = {
            'Specimen': 'RawData',
            'SpecimenProtocol': 'RawDataProtocol',
            'SpecimenProtocols': 'RawDataProtocols',
            'SpecimenID': 'RawDataID',
            'SpecimenNotes': 'RawDataNotes',
            'BarcodeSequence': 'BarcodeSequence',
            'LinkerPrimerSequence': 'LinkerPrimerSequence',
            'SpecimenDatePerformed':  'RawDataDatePerformed',
            'SpecimenProcessor':  'RawDataProcessor',
            'Primer':  'Primer',
            'SequencingTechnology': 'SequencingTechnology',
            'TargetGene': 'TargetGene'
        }

    # Get the required columns
    required_cols = [col for col in template.columns if template[col][0] == 'Required']

    simplified_df = pd.read_csv(file_fp, header=[0, 1], sep='\t')
    renamed_df = simplified_df.rename(columns=swapped)

    # Get the missing columns
    add_cols = set(template.columns.tolist()).difference(renamed_df.columns)

    # Add the missing columns
    for col in add_cols:
        # If the column is required fill it in based on existing data
        if col in required_cols:
            if 'ProtocolID' in col[1]:
                renamed_df[col] = (template[col].tolist() + list(range(0, len(renamed_df) - 3)))
            elif 'SpecimenID' == col[1]:
                renamed_df[col] = (template[col].tolist() +
                                   ['Specimen_' + x for x in renamed_df[('RawData', 'RawDataID')][3:].tolist()])
        # If it's optional just fill it with NAs
        else:
            renamed_df[col] = (template[col].tolist() + ([None] * (len(renamed_df) - 3)))

    # Write the dataframe to the file specified
    renamed_df.to_csv(output_fp, sep='\t', index=False, na_rep='NA')
    return renamed_df


def load_mmeds_stats():
    """ Load the values from the mmeds stats file. Used to give the stats on the homepage. """
    if Path(fig.STAT_FILE).exists():
        stats = yaml.safe_load(fig.STAT_FILE.read_text())
    else:
        stats = {}
    return stats


def load_subject_template(subject_type):
    """ Loads the base template for the subject metadata """
    if subject_type == 'human':
        df = pd.read_csv(fig.TEST_SUBJECT, header=[0, 1], nrows=3, sep='\t')
    elif subject_type == 'animal':
        df = pd.read_csv(fig.TEST_ANIMAL_SUBJECT, header=[0, 1], nrows=3, sep='\t')
    return df


def load_specimen_template():
    """ Loads the base template for the specimen metadata """
    return pd.read_csv(fig.TEST_SPECIMEN, header=[0, 1], nrows=3, sep='\t')


def load_metadata_template(subject_type):
    if subject_type == 'human':
        df = pd.read_csv(fig.TEST_METADATA, header=[0, 1], nrows=3, sep='\t')
    elif subject_type == 'animal':
        df = pd.read_csv(fig.TEST_ANIMAL_METADATA, header=[0, 1], nrows=3, sep='\t')
    return df


def join_metadata(subject, specimen, subject_type):
    """ Joins the subject and specimen metadata into a single data frame """
    if subject_type == 'human':
        subject[('Subjects', 'SubjectIdCol')] = subject[('Subjects', 'HostSubjectId')]
    elif subject_type == 'animal':
        subject[('Subjects', 'SubjectIdCol')] = subject[('AnimalSubjects', 'AnimalSubjectID')]
    subject.set_index(('Subjects', 'SubjectIdCol'), inplace=True)
    specimen.set_index(('AdditionalMetaData', 'SubjectIdCol'), inplace=True)
    df = subject.join(specimen, how='outer')
    return df


def camel_case(value):
    """ Converts VALUE to camel case, replacing '_', '-', '.', ' ', with the capitalization. """
    return ''.join([x.capitalize() for x in
                    str(value).replace('.', ' ').replace('_', ' ').replace('-', ' ').split(' ')])


def write_metadata(df, output_path):
    """
    Write a dataframe or dictionary to a mmeds format metadata file.
    ================================================================
    :df: A pandas dataframe or python dictionary formatted like mmeds metadata
    :output_path: The path to write the metadata to
    """
    if isinstance(df, pd.DataFrame):
        unsorted = df.to_dict('list')
    else:
        unsorted = df

    if ('Subjects', 'HostSubjectId') in unsorted.keys():
        subject_type = 'human'
    elif ('AnimalSubjects', 'AnimalSubjectID') in unsorted.keys():
        subject_type = 'animal'

    template = load_metadata_template(subject_type)

    metadata_length = len(unsorted[('RawData', 'RawDataID')])

    # Add NAs for columns not included in the dict/DF
    for col in template.columns:
        if unsorted.get(col) is None:
            unsorted[col] = ['NA'] * metadata_length

    # Create a sorted dictionary
    mmeds_meta = OrderedDict.fromkeys(sorted(unsorted.keys(),
                                             key=itemgetter(0, 1)))
    for key in mmeds_meta.keys():
        mmeds_meta[key] = unsorted[key]

    # Create the header lines
    lines = ['\t'.join([key[0] for key in mmeds_meta.keys()]),
             '\t'.join([key[1] for key in mmeds_meta.keys()])]

    # Add the additional column info
    additional_headers = ['Optional', 'Text', 'No Limit']
    for i in range(3):
        header_line = []
        # Build the header info
        for table, column in mmeds_meta.keys():
            if table == 'AdditionalMetaData':
                header_line.append(additional_headers[i])
            else:
                header_line.append(template[(table, column)].iloc[i])

        lines.append('\t'.join(header_line))

    for row in range(metadata_length):
        new_line = []
        for key, item in mmeds_meta.items():
            new_line.append(str(item[row]).replace('\t', '').strip())
        # Remove all non-ASCII characters using regular expressions
        cleaned_line = sub(r'[^\x00-\x7f]', r'', '\t'.join(new_line))
        lines.append(cleaned_line)

    output = Path(output_path)
    if not output.exists():
        output.touch()
    output.write_text('\n'.join(lines) + '\n')


def load_metadata(file_name, header=[0, 1], skiprows=[2, 3, 4], na_values='NA', keep_default_na=False):
    """ Load a combined mmeds metadata file """
    return pd.read_csv(file_name,
                       sep='\t',
                       header=header,
                       parse_dates=True,
                       skiprows=skiprows,
                       na_values=na_values,
                       keep_default_na=keep_default_na)


def load_config(config_file, metadata, ignore_bad_cols=False):
    """
    Read the provided config file to determine settings for the analysis.
    ====================================================================
    Note: This function tries to support the various formats a config file
        might be presented to it in. When uploading a config file to the server
        it is loaded as a particular type of FileStream object that I haven't
        been able to replicate outside of the server. So when testing or loading
        the default config from disk I have had to pass it in as a file path.
    """
    try:
        config = {}
        # Replace with a switch statement or unify config_file type
        # If a Path was passed (as is the case during testing)
        if isinstance(config_file, Path):
            page = config_file.read_text()
        # If no config was provided load the default
        elif config_file is None or config_file == '':
            Logger.debug('Using default config')
            page = fig.DEFAULT_CONFIG.read_text()
        elif isinstance(config_file, str):
            page = Path(config_file).read_text()
        else:
            # Load the file contents
            page = config_file

        config = yaml.safe_load(page)
    except (yaml.YAMLError, yaml.scanner.ScannerError):
        raise InvalidConfigError('There was an error loading your config. Config files must be in YAML format.')

    # Check if columns == 'all'
    for param in ['metadata', 'taxa_levels', 'sub_analysis']:
        config['{}_all'.format(param)] = (config[param] == 'all')
    return parse_parameters(config, metadata, ignore_bad_cols=ignore_bad_cols)


def parse_parameters(config, metadata, ignore_bad_cols=False):
    """
    Helper function for load_config. This parses the individual options provided in
    the config file. For example, the user can put 'all' as the taxa column option
    which this will then replace with a list of 1 -> 7. Similar for metadata columns
    used in analysis, if the user put all, this will select all the valid columns from
    the metadata. This functionality has been causing some problems recently however.
    """
    # Ignore the 'all' keys
    diff = {x for x in set(config.keys()).difference(fig.CONFIG_PARAMETERS)
            if '_all' not in x}
    if diff:
        raise InvalidConfigError('Invalid parameter(s) {} in config file'.format(diff))
    try:
        # Parse the values/levels to be included in the analysis
        for option in fig.CONFIG_PARAMETERS:
            Logger.debug('checking {}'.format(option))
            # Get approriate metadata columns based on the metadata file
            if option == 'metadata' or option == 'sub_analysis':
                config[option], config['{}_continuous'.format(option)] = get_valid_columns(metadata,
                                                                                           config[option],
                                                                                           ignore_bad_cols)
            # Split taxa_levels into a list or create the list if 'all'
            elif option == 'taxa_levels':
                if config[option] == 'all':
                    config[option] = [i + 1 for i in range(7)]
                    config['taxa_levels_all'] = True
                else:
                    # Otherwise split the values into a list
                    config['taxa_levels_all'] = False
            elif config[option] == 'False':
                config[option] = False
            elif config[option] == 'True':
                config[option] = True
            # Otherwise just ensure the parameter exists.
            else:
                assert config[option]
        if config['sub_analysis'] and len(config['metadata']) == 1:
            raise InvalidConfigError('More than one column must be select as metadata to run sub_analysis')
    except (KeyError, AssertionError):
        raise InvalidConfigError('Missing parameter {} in config file'.format(option))
    return config


def get_valid_columns(metadata_file, option, ignore_bad_cols=False):
    """
    Helper for parse_parameters.

    Get the column headers for metadata columns meeting the
    criteria to be used in analysis.
    =======================================================
    :metadata_file: Path to the metadata file for this analysis.
    :option: A string. Either a comma separated list of columns or 'all' for all columns
    Returns:
        :summary_cols: A list of columns that are valid for summary analysis
        :col_types: A dictionary with the values of summary_cols as keys.
            True indicates that the column contains continuous values.
            False indicates that it contains discrete value.
    """
    Logger.debug('get valid columns with ignore = {}'.format(ignore_bad_cols))
    summary_cols = []
    col_types = {}
    if not option == 'none':
        # Filter out any categories containing only NaN
        # Or containing only a single metadata value
        # Or where every sample contains a different value
        df = load_metadata(metadata_file, header=0, na_values='nan', skiprows=[0, 2, 3, 4])
        if option == 'all':
            cols = df.columns
        else:
            cols = option

        for col in cols:
            # Ensure there aren't any invalid columns specified to be included in the analysis
            try:
                # If 'all' only select columns that don't have all the same or all unique values
                if df[col].isnull().all() or df[col].nunique() == 1 or df[col].nunique() == len(df[col]):
                    if col in ['Together', 'Separate']:
                        summary_cols.append(col)
                        col_types[col] = False
                    elif option == 'all':
                        continue
                    elif not ignore_bad_cols:
                        raise InvalidConfigError('Invalid metadata column {} selected for analysis'.format(col))
                # If the columns is explicitly specified only check that it exists in the metadata
                else:
                    assert df[col].any()
                    summary_cols.append(col)
                    col_types[col] = pd.api.types.is_numeric_dtype(df[col])
            except KeyError:
                if not ignore_bad_cols:
                    raise InvalidConfigError('Invalid metadata column {} in config file'.format(col))
    return summary_cols, col_types


def write_config(config, path):
    """ Write out the config file being used to the working directory. """
    config_text = {}
    for (key, value) in config.items():
        # Don't write values that are generated on loading
        if key in ['Together', 'Separate', 'metadata_continuous', 'taxa_levels_all', 'metadata_all',
                   'sub_analysis_continuous', 'sub_analysis_all']:
            continue
        # If the value was initially 'all', write that
        elif key in ['taxa_levels', 'metadata', 'sub_analysis']:
            if config['{}_all'.format(key)]:
                config_text[key] = 'all'
            # Write lists as comma seperated strings
            elif value:
                config_text[key] = list(value)
            else:
                config_text[key] = 'none'
        else:
            config_text[key] = value
    with open(path / 'config_file.yaml', 'w') as f:
        yaml.dump(config_text, f)


def copy_metadata(metadata_file, metadata_copy):
    """
    Copy the provided metadata file with a few additional columns to be used for analysis
    =====================================================================================
    :metadata_file: Path to the metadata file.
    :metadata_copy: Path to save the new metadata file.
    """
    mdf = load_metadata(metadata_file).T
    mdf.loc[('AdditionalMetaData', 'Separate'), :] = ['Required', 'Text', 'Limit 45 Characters'] +\
        ['All' for x in range(mdf.shape[1] - 3)]
    mdf.loc[('AdditionalMetaData', 'Together'), :] = mdf.loc['RawData', 'RawDataID']
    write_metadata(mdf.T, metadata_copy)


def get_col_type(raw_column):
    """
    Return the type of data the column should be checked for.
    =========================================================
    :raw_column: The column to check for type
    """
    check_date = False
    col_type = None
    if 'Date' in raw_column.name:
        col_type = datetime64
        try:
            column = pd.to_datetime(raw_column)
        # If there is an error converting to datetime
        # check the individual cells
        except ValueError:
            column = raw_column
            check_date = True
    # Try to set the type based on the most common type
    else:
        column = raw_column
        types = {
            int: 0,
            float: 0,
            str: 0
        }

        for cell in raw_column:
            # Don't count NA
            if cell == 'NA':
                continue
            # Check if value is numeric
            elif is_numeric(cell):
                try:
                    int(cell)
                    types[int] += 1
                except ValueError:
                    types[float] += 1
            # Check if it's a string
            else:
                try:
                    str(cell)
                    types[str] += 1
                except TypeError:
                    continue
        col_type = max(types, key=types.get)
    return column, col_type, check_date


def load_ICD_codes():
    """ Load all known ICD codes and return them as a dictionary """
    # The dictionary is defined this way so every new entry gets 'XXXX' added automatically
    ICD_codes = defaultdict(lambda: {'XXXX': 'Unknown details'})
    ICD_codes['XXX'] = {'XXXX': 'Subject is healthy to the best of our knowledge'}
    ICD_codes['NA'] = {'NA': 'No Value'}
    ICD_codes[nan] = {nan: 'No Value'}
    with open(fig.STORAGE_DIR / 'icd10cm_codes_2018.txt') as f:
        # Parse each line
        for line in f:
            parts = line.split(' ')
            # Code is first part
            code = parts[0]
            # Description is second
            description = ' '.join(parts[1:]).strip()
            # Fill in codes with 'X'
            while len(code) < 7:
                code += 'X'
            ICD_codes[code[:3]][code[3:]] = description
    return ICD_codes


def parse_ICD_codes(df):
    """ Parse the ICD codes into seperate columns """
    df.fillna('XXX.XXXX', inplace=True)
    codes = df['ICDCode']['ICDCode'].tolist()
    IBC, IC, ID, IDe = [], [], [], []
    null = nan
    for code in codes:
        try:
            parts = code.split('.')
            # Gets the first character
            IBC.append(parts[0][0])
            # Gets the next 4th, 5th, and 6th characters
            ID.append(parts[1][:-1])
            # Gets the final character
            IDe.append(parts[1][-1])
            # Tries to add the 2nd and 3rd numbers
            # adds NA if 'XX'
            IC.append(int(parts[0][1:]))
        except ValueError as e:
            if 'invalid literal' in e.args[0] and ": 'XX'" in e.args[0]:
                IC.append(null)
            else:
                raise e
        # If the value is null it will error
        except (AttributeError, IndexError):
            IBC.append(null)
            IC.append(null)
            ID.append(null)
            IDe.append(null)

    # Add the parsed values to the dataframe
    df['IllnessBroadCategory', 'ICDFirstCharacter'] = IBC
    df['IllnessCategory', 'ICDCategory'] = IC
    df['IllnessDetails', 'ICDDetails'] = ID
    df['IllnessDetails', 'ICDExtension'] = IDe
    return df


def is_numeric(s):
    """
    Check if the provided string is a number.
    =========================================
    :s: The string to check
    """
    try:
        float(s)
        result = True
    except ValueError:
        result = False
    return result


def create_local_copy(fp, filename, path=fig.STORAGE_DIR):
    """ Create a local copy of the file provided. """
    # If the fp is None return None
    if fp is None or fp == '':
        return None

    # Create the filename
    file_copy = Path(path) / Path(filename).name

    # Ensure there is not already a file with the same name
    while file_copy.is_file():
        file_copy = Path(path) / '_'.join([fig.get_salt(5), Path(filename).name])

    # Write the data to a new file stored on the server
    with open(file_copy, 'wb') as nf:
        if isinstance(fp, bytes):
            nf.write(fp)
        else:
            while True:
                data = fp.read(8192)
                nf.write(data)
                if not data:
                    break
    return str(file_copy)


def build_error_rows(df, tables, headers, markup):
    """
    Helper function for generate_error_html. Builds out the rows of a metadata error table.
    This highlights for the user where the problems are and notes how they need to be fixed.
    """
    html = ''
    # Build each row of the table
    for row in range(len(df[tables[0]][headers[0]])):
        html += '<tr>'
        # Build each column in the row
        for col, (table, header) in enumerate(zip(tables, headers)):
            item = df[table][header][row]
            if table == 'Subjects':
                try_col = -2
            else:
                try_col = col
            # Add the error/warning if there is one
            try:
                color, issue = markup[row + 4][try_col]
                html += '<td style="color:black" bgcolor="{}">\
                    {}<div style="font-weight:bold">\
                    <br>-----------<br>{}</div></td>\n'.format(color, item, issue)
            # Otherwise add the table item
            except KeyError:
                html += '<td style="color:black">{}</td>\n'.format(item)
        html += '</tr>\n'
    return html


def generate_error_html(file_fp, errors, warnings):
    """
    Generates an html page marking the errors and warnings found in
    the given metadata file.
    ===============================================================
    :file_fp: The original metadata file
    :errors: A list of the errors the metadata file produced
    :warnings: A list of the warnings the metadata file produced
    """
    df = pd.read_csv(file_fp, sep='\t', header=[0, 1], skiprows=[2, 3, 4], na_filter=False)
    df.replace('NA', nan, inplace=True)

    html = '<!DOCTYPE html>\n<html>\n'
    html += '<link type="text/javascript" rel="stylesheet" href="/CSS/stylesheet.css">\n'
    html += '<title> MMEDS Metadata Errors </title>\n'
    html += '<body>'
    markup = defaultdict(dict)
    top = []

    Logger.debug('generate errors')
    Logger.debug(errors)
    # Add Errors to markup table
    for error in errors:
        row, col, item = error.split('\t')
        top.append(('red', item))
        if row == '0':
            markup[int(row) + 3][int(col)] = ['red', item]
        else:
            markup[int(row) + 4][int(col)] = ['red', item]

    # Add warnings to markup table
    for warning in warnings:
        row, col, item = warning.split('\t')
        if row == '-1' and col == '-1':
            top.append(('orange', item))
        elif row == '0':
            markup[int(row) + 3][int(col)] = ['orange', item]
        else:
            markup[int(row) + 4][int(col)] = ['orange', item]

    # Add general warnings and errors
    for color, er in set(top):
        html += '<h3 style="color:{}">'.format(color) + '\n' + er + '</h3>\n'

    # Get all the table and header names
    tables = []
    columns = []
    count = 0
    table_html = ''
    column_html = ''
    for (table, header) in df.axes[1]:
        for column in df[table]:
            try:
                color, er = markup[-1][count]
                table_html += '<th style="color:{}">'.format(color) + table + '\n' + er + '</th>\n'
                column_html += '<th style="color:{}">'.format(color) + column + '\n' + er + '</th>\n'
            except KeyError:
                table_html += '<th>' + table + '</th>\n'
                column_html += '<th>' + column + '</th>\n'

            tables.append(table)
            columns.append(column)
            count += 1

    # Create the table and column rows of the table
    html += '<table>'
    html += '<tr>' + table_html + '\n</tr>'
    html += '<tr>' + column_html + '\n</tr>'
    # Fill out the table
    html += build_error_rows(df, tables, columns, markup)
    html += '</table>\n</body>\n</html>'
    return html


def parse_code_blocks(path):
    """
    Parses the code blocks found in mmeds/resources/summary_code.txt into a dict
    """
    # Load the code templates
    data = Path(path).read_text().split('\n=====\n')

    # Dict for storing all the different code templates
    code_blocks = {}
    for code in data:
        parts = code.split('<source>\n')
        code_blocks[parts[0]] = parts[1]
    return code_blocks


def send_email(toaddr, user, message='upload', testing=False, **kwargs):
    """
    Sends a confirmation email to addess containing user and code.
    ==============================================================
    :toaddr: The address to send the email to
    :user: The user account that toaddr belongs to
    :message: The type of message to send
    :kwargs: Any information that is specific to a paricular message type
    """
    Logger.debug('Send email of type: {} to: {} on behalf of {}'.format(message, toaddr, user))

    # Templates for the different emails mmeds sends
    if message == 'upload':
        body = 'Hello {email},\nthe user {user} uploaded data for the {study} study to the mmeds database server.\n' +\
               'In order to gain access to this data without the password to\n{user} you must provide ' +\
               'the following access code:\n{code}\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'New Data Uploaded'
    elif message == 'ids_generated':
        body = 'Hello {email},\nthe user {user} uploaded {id_type}s for the study {study}. \n' +\
               'The aliquots are added and the IDs have been generated.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = f'{kwargs["id_type"].capitalize()} IDs Generated'
    elif message == 'reset':
        body = 'Hello {user},\nYour password has been reset.\n' +\
               'The new password is:\n{password}\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Password Reset'
    elif message == 'change':
        body = 'Hello {user},\nYour password has been changed.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Password Change'
    elif message == 'analysis_start':
        body = 'Hello {user},\nYour requested {analysis} analysis on study {study} has started.\n' +\
               'You will recieve another email when this analysis completes.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Analysis Started'
    elif message == 'analysis_done':
        body = 'Hello {user},\nYour requested {analysis} analysis on study {study} is complete.\n' +\
               'You can retrieve the results using the access code {code}.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Analysis Complete'
    elif message == 'error':
        body = 'Hello {user},\nThere was an error during requested {analysis} analysis.\n' +\
               'Please check the error file associated with this study.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Error During Analysis'
    elif message == 'too_many_on_node':
        body = 'Hello {user},\nThere was an issue starting requested {analysis} analysis.\n' +\
               'There are too many analyses already running on the main node.\n' +\
               'Either submit a new analysis to the queue or wait until others finish.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Analysis Not Started'

    email_body = body.format(
        user=user,
        cemail=fig.CONTACT_EMAIL,
        email=toaddr,
        id_type=kwargs.get('id_type'),
        study=kwargs.get('study'),
        code=kwargs.get('code'),
        analysis=kwargs.get('analysis'),
        password=kwargs.get('password'),
    )
    if testing:
        path = Path(gettempdir()) / '{user}_{message}.mail'.format(user=user, message=message)
        path.write_text(email_body)
        Logger.error(str(path) + ":\n" + path.read_text())
    else:
        script = 'echo "{body}" | mail -s "{subject}" "{toaddr}"'
        if 'summary' in kwargs.keys():
            script += ' -A {summary}'.format(summary=kwargs['summary'])
        cmd = script.format(body=email_body, subject=subject, toaddr=toaddr)
        run(['/bin/bash', '-c', cmd], check=True)


def recieve_email(user, message, text, max_count=120):
    """
    Checks for a email for USER of type MESSAGE containing TEXT
    COUNT: How many seconds to wait
    """
    result = False
    mail = Path(gettempdir()) / '{user}_{message}.mail'.format(user=user, message=message)

    count = 0
    while count < max_count and not mail.exists():
        count += 1
        sleep(1)

    if mail.exists():
        body = mail.read_text()
        if text in body:
            result = body
            mail.unlink()  # Delete the email so it doesn't affect future tests
        else:
            raise EmailError('Email for {} about {} does not contain correct contents'.format(user, message))
    else:
        raise EmailError('Email for {} about {} was not sent'.format(user, message))
    return result


def pyformat_translate(value):
    """ Convert from numpy to standard python datatypes. """
    if isinstance(value, int64):
        result = int(value)
    elif isinstance(value, float64):
        result = float(value)
    else:
        result = value
    return result


def parse_locals(line, variables, new_env):
    """
    Replace variables used in the environment setup with their definitions.
    """
    # Update any values with local variables
    if '$' in line:
        for variable, path in variables.items():
            line = line.replace('${}'.format(variable), path)
    if '~' in line:
        for variable, path in variables.items():
            home = new_env.get('MMEDS')
            if home is None:
                home = new_env.get('HOME')
            line = line.replace('~', home)
    return line, variables


def setup_environment(module):
    """
    Returns a dictionary with the environment variables loaded for a particular module.
    ===================================================================================
    :module: A string. The name of the module to load.
    """
    # Check there is nothing in module that could cause problems
    if not module.replace('/', '').replace('_', '').replace('-', '').replace('.', '').isalnum():
        raise InvalidModuleError('{} is not a valid module name. '.format(module) +
                                 'Modules may only contain letters, numbers, "/", "_", "-", and "."')

    module_file = (fig.MODULE_ROOT / module).read_text()

    new_env = environ.copy()
    variables = {}

    for line in module_file.splitlines():
        if line.startswith('#'):
            continue
        line, variables = parse_locals(line, variables, new_env)
        parts = line.strip().split(' ')
        # Set locally used variables
        if parts[0] == 'set':
            variables[parts[1]] = parts[2]
        # Add to PATH
        elif parts[0] == 'prepend-path':
            new_env[parts[1]] = '{}:{}'.format(parts[2], new_env[parts[1]])
        # Remove from PATH
        elif parts[0] == 'remove-path':
            path_parts = new_env[parts[1]].split(':')
            new_env[parts[1]] = ':'.join([part for part in path_parts if not part == parts[1]])
        # Set environment variables
        elif parts[0] == 'setenv':
            new_env[parts[1]] = parts[2]
    Logger.debug("Created environment for module {}".format(module))
    Logger.debug(new_env)
    return new_env


def create_qiime_from_mmeds(mmeds_file, qiime_file, tool_type):
    """
    Create a qiime mapping file from the mmeds metadata
    ===================================================
    :mmeds_file: The path to the mmeds metadata.
    :qiime_file: The path where the qiime mapping file should be written.
    """
    mdata = pd.read_csv(mmeds_file, header=1, skiprows=[2, 3, 4], sep='\t')

    headers = list(mdata.columns)

    hold = headers[0]
    di = headers.index('RawDataID')
    headers[0] = '#SampleID'
    headers[di] = hold

    hold = headers[1]
    di = headers.index('BarcodeSequence')
    headers[1] = 'BarcodeSequence'
    headers[di] = hold

    hold = headers[2]
    di = headers.index('LinkerPrimerSequence')
    headers[2] = 'LinkerPrimerSequence'
    headers[di] = hold

    di = headers.index('SampleID')
    headers[di] = 'MmedsSampleID'

    with open(qiime_file, 'w') as f:
        f.write('\t'.join(headers) + '\n')
        if 'qiime2' == tool_type:
            f.write('\t'.join(['#q2:types'] + ['categorical' for x in range(len(headers) - 1)]) + '\n')
        seen_ids = set()
        seen_bars = set()
        for row_index in range(len(mdata)):
            if str(mdata['RawDataID'][row_index]) in seen_ids:
                continue
            row = []
            for header in headers:
                if header == '#SampleID':
                    row.append(str(mdata['RawDataID'][row_index]))
                    seen_ids.add(str(mdata['RawDataID'][row_index]))
                elif header == 'BarcodeSequence':
                    row.append(str(mdata['BarcodeSequence'][row_index]))
                    seen_bars.add(str(mdata['BarcodeSequence'][row_index]))
                elif header == 'MmedsSampleID':
                    row.append(str(mdata['SampleID'][row_index]))
                else:
                    row.append(str(mdata[header][row_index]))
            f.write('\t'.join(row) + '\n')
    return list(mdata.columns)


def quote_sql(sql, quote='`', **kwargs):
    """
        Returns the sql query with the identifiers properly qouted using QUOTE
        '`' AKA backtick is generally accepted as the quote character to use
        for table and column names. Any other characters within it will be treated
        as part of the variable name.
        https://dev.mysql.com/doc/refman/8.0/en/identifiers.html
    """
    # There are only two quote characters allowed
    assert (quote == '`' or quote == "'")

    if not isinstance(sql, str):
        raise InvalidSQLError('Provided SQL {} is not a string'.format(sql))

    # Clear any  existing quotes before adding the new ones
    cleaned_sql = sql.replace(quote, '')
    quoted_args = {}
    for key, item in kwargs.items():
        # Check the entry is a string
        if not isinstance(item, str):
            raise InvalidSQLError('SQL Identifier {} is not a string'.format(item))
        # Check the entry isn't too long
        if len(item) > 66 and 'JOIN' not in item:
            raise InvalidSQLError('SQL Identifier {} is too long ( > 66 characters)'.format(item))
        # Check that there are only allowed characters: Letters, Numbers, '_', and '*'
        good_set = {'_', '`', '*', '.', '(', ')', '=', ' '}
        result = ''.join(set(item).difference(good_set))
        if not result.isalnum():
            raise InvalidSQLError('Illegal characters in identifier {}.'.format(item) +
                                  ' Only letters, numbers, and {good_set} are permitted')

        quoted_args[key] = '{quote}{item}{quote}'.format(quote=quote, item=item)
    formatted = cleaned_sql.format(**quoted_args)
    return formatted


def make_pheniqs_config(reads_forward, reads_reverse, barcodes_forward, barcodes_reverse, mapping_file, o_directory,
                        testing=False):
    """
    Method for taking in fastq.gz files and tsv mapping files and creating an
    output.json file that can be read by the 'pheniqs' module for demultiplexing
    """
    # The top of the output.json file, including R1, I1, I2, and R2
    if testing:
        out_s = f'{{\n\t"input": [\n\t\t"%s",\n\t\t"%s",\n\t\t"%s",\n\t\t"%s"\n\t],\n\t"output": [ "{o_directory}/output_all.fastq" ],'
    else:
        out_s = '{\n\t"input": [\n\t\t"%s",\n\t\t"%s",\n\t\t"%s",\n\t\t"%s"\n\t],\n\t"output": [ "output_all.fastq" ],'
    out_s += '\n\t"template": {\n\t\t"transform": {\n\t\t\t"comment": "This global transform directive specifies the \
    segments that will be written to output as the biological sequences of interest, this represents all of R1 and R2."'
    out_s += ',\n\t\t\t"token": [ "0::", "3::" ]\n\t\t}\n\t},\n\t"sample": {\n\t\t"transform": {\n\t\t\t"token": '
    out_s += '[ "1::8", "2::8" ]\n\t\t},\n\t\t"algorithm": "pamld",\n\t\t"confidence threshold": 0.95,\n\t\t'
    out_s += '"noise": 0.05,\n\t\t"codec": {\n'

    out_s = out_s % (reads_forward, barcodes_forward, barcodes_reverse, reads_reverse)

    # Template for each sample and their barcodes
    sample_template = '\t\t\t"@%s": {\n\t\t\t\t"LB": "%s",\n\t\t\t\t"barcode": [ "%s", "%s" ],\n\t\t\t\t"output": [\
        \n\t\t\t\t\t"%s/%s_S1_L001_R1_001.fastq.gz",\n\t\t\t\t\t"%s/%s_S1_L001_R2_001.fastq.gz"\n\t\t\t\t]\n\t\t\t}'

    # Getting mapping file as DataFrame
    headers = True
    map_df = pd.read_csv(Path(mapping_file), sep='\t', header=[0, 1], na_filter=False)

    try:
        length = len(map_df['#SampleID']['#q2:types'])
    except KeyError:
        map_df = pd.read_csv(Path(mapping_file), sep='\t', header=[0], na_filter=False)
        length = len(map_df['#SampleID'])
        headers = False

    if headers:
        ids = map_df['#SampleID']['#q2:types']
        b1s = map_df['BarcodeSequence']['categorical']
        b2s = map_df['BarcodeSequenceR']['categorical']
    else:
        ids = map_df['#SampleID']
        b1s = map_df['BarcodeSequence']
        b2s = map_df['BarcodeSequenceR']

    # Adding each sample and barcodes to output.json
    for i in range(length):
        name = ids[i]
        b1 = b1s[i]
        b2 = b2s[i]
        out_s += sample_template % (name, name, b1, b2, o_directory, name, o_directory, name)
        if i == length-1:
            out_s += '\n'
        else:
            out_s += ',\n'

    # Bottom of output.json file
    out_s += '\t\t},\n\t\t"undetermined": {\n\t\t\t"output": [\n\t\t\t\t\
        "%s/undetermined_S1_L001_R1_001.fastq.gz",\n\t\t\t\t\
        "%s/undetermined_S1_L001_R2_001.fastq.gz"\n\t\t\t]\n\t\t}\n\t}\n}' % (o_directory, o_directory)

    return out_s


def make_grouped_mapping_file(mapping_file, col):
    """ Generate DataFrame that corresponds to the groups in a metadata category """
    df = pd.read_csv(Path(mapping_file), header=[0, 1], na_filter=False, sep='\t')
    categories = ['#q2:types']
    for cell in df[col]['categorical']:
        if cell not in categories:
            categories.append(cell)
    out_data = {'#SampleID': categories}
    out_df = pd.DataFrame(data=out_data)
    return out_df


def strip_error_barcodes(num_allowed_errors,
                         mapping_file,
                         input_dir,
                         output_dir,
                         verbose,
                         filename_template=fig.FASTQ_FILENAME_TEMPLATE,
                         sample_id_cats=fig.QIIME_SAMPLE_ID_CATS,
                         forward_barcode_cats=fig.QIIME_FORWARD_BARCODE_CATS,
                         reverse_barcode_cats=fig.QIIME_REVERSE_BARCODE_CATS):
    """
    Strip reads with errors from demultiplexed fastq files and write new file content
    This has only been tested using input that has been demultiplexed using 'pheniqs'
    =================================================================================
    :num_allowed_errors: Maximum number of errors in barcode pairs to not be stripped
    :mapping_file: File containing sample IDs and barcode pairs
    :input_dir: Directory containing demultiplexed fastq files
    :output_dir: Directory in which to store stripped fastq files
    :verbose: Print information to stdout
    :filename_template: String with formatting for sample id and (1 or 2) for forward/reverse
    :sample_id_cats: tuple with sample id header text
    :forward_barcode_cats: tuple with forward barcode header text
    :reverse_barcode_cats: tuple with reverse barcode header text
    """
    # Read in mapping file
    output_content = {}
    map_df = pd.read_csv(Path(mapping_file), sep='\t', header=[0, 1], na_filter=False)

    # Only three columns are needed
    sample_ids = map_df[sample_id_cats[0]][sample_id_cats[1]]
    forward_barcodes = map_df[forward_barcode_cats[0]][forward_barcode_cats[1]]
    reverse_barcodes = map_df[reverse_barcode_cats[0]][reverse_barcode_cats[1]]

    # Hash data for easy access
    map_hash = {key: (value1, value2) for (key, value1, value2) in zip(sample_ids, forward_barcodes, reverse_barcodes)}
    verbose_template = '{} Writing {}'
    count = 0

    # Generate output for each sample's forward and reverse input files
    for key in map_hash:
        forward_filename = filename_template.format(key, 1)
        reverse_filename = filename_template.format(key, 2)

        # Create output files
        forward_output = Path(output_dir) / forward_filename
        reverse_output = Path(output_dir) / reverse_filename
        forward_output.touch()
        reverse_output.touch()

        # Forward Reads
        count += 1
        Logger.debug(verbose_template.format(count, forward_filename))
        if verbose:
            print(verbose_template.format(count, forward_filename))
        # Generate error-stripped content and write gzipped output
        with gzip.open(forward_output, 'wt') as f:
            f.write(
                get_stripped_file_content(
                    num_allowed_errors,
                    map_hash[key][0],
                    map_hash[key][1],
                    Path(input_dir) / forward_filename
                )
            )

        # Reverse Reads
        count += 1
        Logger.debug(verbose_template.format(count, reverse_filename))
        if verbose:
            print(verbose_template.format(count, reverse_filename))
        # Generate error-stripped content and write gzipped output
        with gzip.open(reverse_output, 'wt') as f:
            f.write(
                get_stripped_file_content(
                    num_allowed_errors,
                    map_hash[key][0],
                    map_hash[key][1],
                    Path(input_dir) / reverse_filename
                )
            )


def get_stripped_file_content(num_allowed_errors, forward_barcode, reverse_barcode, filename):
    """
    Get the error-stripped content of one demultiplexed fastq file
    ==============================================================
    :num_allowed_errors: Maximum number of errors in barcode pairs to not be stripped
    :forward_barcode: First of two barcodes associated with the sample
    :reverse_barcode: Second of two barcodes associated with the sample
    :filename: Absolute Path object to demultiplexed fastq file
    """
    content = ''
    f = gzip.open(filename, mode='rt')

    # This raw string pattern matches one entire read in the format used by the pheniqs library demultiplexer
    # The two sections in parentheses match to the forward and reverse barcodes that were used to assign the read
    # Example of this pattern: '@M00914:50:00000-JN85L:1:1101:18345:1663 2:N:0:CTCGACTT-ATCGTACG
    #                           TACCGTACCCGTTACGTTTACGTGACCGTAGGGCAGAAATGAACCAGTAGACCGATTACGATT
    #                           +
    #                           ABBBBBBBBBBBBBBBCC///>----A---09'
    pattern = r'@.+:0:([ACTGN]+)-([ACTGN]+)\n.+\n.+\n.+\n'

    # Create an iterator for which the .group method contains (whole_read, forward_barcode, reverse_barcode)
    reads = re.finditer(pattern, f.read())
    read = next(reads, None)
    while read:

        # Use Levenshtein distance on each barcode to determine error count
        diff = lev.distance(read.group(1), forward_barcode)
        diff += lev.distance(read.group(2), reverse_barcode)

        # Add read to the output if there are few enough errors
        if diff <= num_allowed_errors:
            content += read.group(0)

        read = next(reads, None)

    return content


def parse_barcodes(forward_barcodes, reverse_barcodes, forward_mapcodes, reverse_mapcodes):
    """
    forward_barcodes, reverse_barcodes are the paths to those barcode files.
    forward_mapcodes, reverse_mapcodes are lists of barcodes taken from the mapping file.
    """
    results_dict = dict.fromkeys(reverse_mapcodes)
    full_results = {}
    barcode_ids = []

    # open the barcode files
    with open(forward_barcodes, 'r') as forward, open(reverse_barcodes, 'r') as reverse:
        forward_barcodes = forward.readlines()
        for i, line in enumerate(reverse):
            line = line.strip('\n')

            # save barcode id, in case the barcode is found in the mapping file
            if i % 4 == 0:
                barcode_id = line

            elif i % 4 == 1:
                # If the forward, reverse barcodes are in the mapping file.
                if line in reverse_mapcodes and forward_barcodes[i].strip('\n') in forward_mapcodes:

                    # add entry for new barcode or increment an existing count
                    if not results_dict[line]:
                        results_dict[line] = 1
                    else:
                        results_dict[line] += 1

                    # save barcode id, since it's in the mapping file
                    barcode_ids.append(barcode_id)

                # increment counts for all barcodes, not just those in the mapping file.
                if line in full_results.keys():
                    full_results[line] += 1
                else:
                    full_results[line] = 1
        return results_dict, full_results, barcode_ids


def create_barcode_mapfile(output_dir, for_barcodes, rev_barcodes, file_name, map_file, ret_dicts=False):
    """
    Helper function for validate_demultiplex()
    Replaces the samples in a qiime1 mapping file with barcodes for a given sample in that mapping file.
    Then we can test if the those barcodes are in the demultiplexed file and the proportion they represent of all reads.

    output_dir: where the barcode mapping file will be written to.
    for_barcodes: path to gzipped, forward barcode file
    rev_barcodes: path to reverse barcode file
    map_file: path to a qiime mapping file
    ret_dicts: return results dictionaries from parsing barcode files
    """
    map_df = pd.read_csv(Path(map_file), sep='\t', header=[0, 1], na_filter=False)

    # get matching sample
    matched_sample = None
    for sample in map_df[('#SampleID', '#q2:types')]:
        if str(sample) == file_name.split('_')[0] or\
               str(sample) == f'{file_name.split("_")[0]}_{file_name.split("_")[1]}':
            matched_sample = sample
            break

    # filter mapping file down to said sample
    map_df.set_index(('#SampleID', '#q2:types'), inplace=True)
    map_df = map_df.filter(items=[matched_sample], axis='index')

    # Get barcodes for that sample
    results_dict, full_dict, barcode_ids = parse_barcodes(for_barcodes, rev_barcodes,
                                                          map_df[('BarcodeSequence', 'categorical')].tolist(),
                                                          map_df[('BarcodeSequenceR', 'categorical')].tolist())
    # map_df = map_df.append([map_df]*(len(barcode_ids)-1), ignore_index=True)
    map_df.reset_index(drop=True, inplace=True)

    # replace sampleIDs with barcodes
    map_df[('#SampleID', '#q2:types')] = pd.Series(barcode_ids, dtype=str)
    map_df[('#SampleID', '#q2:types')] = map_df[('#SampleID', '#q2:types')].str.split(' ', expand=True)[0]
    map_df[('#SampleID', '#q2:types')] = map_df[('#SampleID', '#q2:types')].str.replace('@', '')

    # make sure this column is first
    map_df.set_index(('#SampleID', '#q2:types'), inplace=True)
    map_df.reset_index(inplace=True)

    # add this column to the end of the mapping file, so it passes Qiime1 mapping file validation
    map_df[('Description', 'categorical')] = np.nan

    map_df.to_csv(f'{output_dir}/{file_name}_qiime_barcode_mapfile.tsv', index=None, header=True, sep='\t')
    if ret_dicts:
        ret_val = (map_df, results_dict, full_dict)
    else:
        ret_val = map_df

    return ret_val


def validate_demultiplex(demux_file, for_barcodes, rev_barcodes, map_file, log_dir, is_gzip, get_read_counts=False,
                         on_chimera=True):
    """
    Calls qiime1 script to validate a gzipped, demultiplex fastq file.
    source_dir: where the data is located.
    demux_file: path to gzipped, demultiplexed, fastq file.
    for_barcodes: path to gzipped, forward barcode file
    rev_barcodes: path to reverse barcode file
    map_file: path to a qiime mapping file
    log_dir: path to log dir, where the results will be saved
    """
    # TODO: generalize for single barcodes

    # Allows us to test that the correct barcodes are in the resulting demultiplexed file.
    barcode_return = create_barcode_mapfile(Path(demux_file).parent, for_barcodes, rev_barcodes,
                                            Path(demux_file).stem, map_file, get_read_counts)
    if get_read_counts:
        map_df = barcode_return[0]
        matched_barcodes = barcode_return[1]
        all_barcodes = barcode_return[2]
    else:
        map_df = barcode_return

    new_env = setup_environment('qiime/1.9.1')

    test_file = f'{Path(demux_file).parent}/{Path(demux_file).stem}_test.fastq'
    map_file = f'{Path(demux_file).parent}/{Path(demux_file).stem}_qiime_barcode_mapfile.tsv'

    gunzip_demux_file = ['gunzip', f'{demux_file}.gz']
    gzip_demux_file = ['gzip', demux_file]
    create_fastq_copy = ['cp', f'{demux_file}', f'{test_file}']

    # to create the fasta file, on every line mod4 = 1, replace @ with >
    # then on every line mod4 = 2, print the line. then skip all other lines.
    create_fasta_file = ['sed', '-n', '-i', '1~4s/^@/>/p;2~4p', f'{test_file}']


    # Call qiime1 validate demultiplex script
    if on_chimera:
        validate_demux_file = f'ml python/2.7.9-UCS4; validate_demultiplexed_fasta.py -b -a\
                            -i {test_file}\
                            -o {log_dir}\
                            -m {map_file};\
                            rm {test_file}'
    else:
        validate_demux_file = f'validate_demultiplexed_fasta.py -b -a\
                            -i test_file\
                            -o {log_dir}\
                            -m {map_file};\
                            rm {test_file}'

    try:
        if is_gzip:
            run(gunzip_demux_file, capture_output=True, check=True)

        run(create_fastq_copy, capture_output=True, check=True)
        run(create_fasta_file, capture_output=True, check=True)
        validate_output = run(validate_demux_file, capture_output=True, env=new_env, check=True, shell=True)

        if is_gzip:
            run(gzip_demux_file, capture_output=True, check=True)

    except CalledProcessError as e:
        Logger.debug(e)
        print(e.output)
        raise e

    if get_read_counts:
        ret_val = (validate_output, matched_barcodes, all_barcodes)
    else:
        ret_val = validate_output

    return ret_val

def run_analysis(path, tool_type, testing=False):
    """
    Run analysis for one of MMEDs tools
    Currently only setup for qiime2

    path: path to analysis folder i.e. Study/Qiime2_0)
    tool_type: tool to use. qiime1, qiime2, lefse, etc
    """
    if testing:
        # This module file is setup for running on github actions
        qiime_env = setup_environment('qiime2-2020.8')
    else:
        # This module file is setup for running on minerva
        qiime_env = setup_environment('qiime2/2020.8')

    print('env loaded')
    jupyter_env = setup_environment('jupyter')

    qiime_p1 = f'bash {path}/run_qiime_part1.sh'
    qiime_p2 = f'bash {path}/run_qiime_part2.sh'

    qiime = f'qiime tools import --type EMPSingleEndSequences --input-path $RUN_Qiime2/import_dir --output-path $RUN_Qiime2/qiime_artifact.qza'

    try:
        output1 = run(qiime_p1, env=qiime_env, capture_output=True, shell=True)

        if testing:
            # TODO: Need to generalize this and see how the summary jupyter files are created
            # Hard coded values are needed for current qiime2 test
            # Which just runs existing test files with default config
            s_grouped_metadata_df = make_grouped_mapping_file(f'{path}/qiime_mapping_file.tsv', 'SpecimenBodySite')

            s_grouped_metadata_df.to_csv(f'{path}/grouped_SpecimenBodySite_mapping_file.tsv', sep='\t', index=False)

        output2 = run(qiime_p2, env=qiime_env, capture_output=True, shell=True)

        Logger.debug(output1)
        Logger.debug(output2)

    except CalledProcessError as e:
        Logger.debug(e)
        print(e.output)
        raise e
