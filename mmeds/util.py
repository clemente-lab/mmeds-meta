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
import pandas as pd
import mmeds.config as fig
from mmeds.logging import Logger


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
    if Path(fig.STAT_FILE).exists():
        stats = yaml.safe_load(fig.STAT_FILE.read_text())
    else:
        stats = {}
    return stats


def load_subject_template(subject_type):
    if subject_type == 'human':
        df = pd.read_csv(fig.TEST_SUBJECT, header=[0, 1], nrows=3, sep='\t')
    elif subject_type == 'animal':
        df = pd.read_csv(fig.TEST_ANIMAL_SUBJECT, header=[0, 1], nrows=3, sep='\t')
    return df


def load_specimen_template():
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
    return pd.read_csv(file_name,
                       sep='\t',
                       header=header,
                       parse_dates=True,
                       skiprows=skiprows,
                       na_values=na_values,
                       keep_default_na=keep_default_na)


def load_config(config_file, metadata, ignore_bad_cols=False):
    """ Read the provided config file to determine settings for the analysis. """
    try:
        config = {}
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


def get_valid_columns(metadata_file, option, ignore_bad_cols=False):
    """
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


def make_pheniqs_config(reads_forward, reads_reverse, barcodes_forward, barcodes_reverse, mapping_file, o_directory):
    """
    Method for taking in fastq.gz files and tsv mapping files and creating an
    output.json file that can be read by the 'pheniqs' module for demultiplexing
    """
    # The top of the output.json file, including R1, I1, I2, and R2
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
    """ Generate tsv file that corresponds to the groups in a metadata category """
    df = pd.read_csv(Path(mapping_file), header=[0, 1], na_filter=False, sep='\t')
    categories = ['#q2:types']
    for cell in df[col]['categorical']:
        if cell not in categories:
            categories.append(cell)
    out_data = {'#SampleID': categories}
    out_df = pd.DataFrame(data=categories)
    out_tsv = out_df.to_csv(sep='\t')
    return out_tsv


def strip_error_barcodes(num_allowed_errors, map_hash, input_dir, output_dir):
    # Strip errors for each fastq.gz file in input_dir
    count = 1
    for filename in os.listdir(input_dir):
        sample = ''
        # Match sample file to sample in hash
        for key in map_hash:
            if filename.startswith(key):
                sample = key
                break
        if not sample == '':
            # Open sample file for reading
            f = gzip.open(Path(input_dir) / filename, mode='rt')
            out = ''

            line = f.readline()
            # Compare each line's barcodes with the expected barcodes and count diff
            while line is not None and not line == '':
                code = line[len(line)-18:len(line)-1].split('-')
                diff = 0
                # Compare forward barcodes and count diff
                for i in range(len(code[0])):
                    if not code[0][i] == map_hash[sample][0][i]:
                        diff += 1
                # Compare reverse barcodes and count diff
                for i in range(len(code[1])):
                    if not code[1][i] == map_hash[sample][1][i]:
                        diff += 1

                # If diff does not exceed N, write read to output
                if diff <= num_allowed_errors:
                    out += line
                    out += f.readline()
                    out += f.readline()
                    out += f.readline()
                # Else skip read
                else:
                    f.readline()
                    f.readline()
                    f.readline()

                line = f.readline()

            # Write output file to output_dir
            p_out = Path(output_dir) / filename
            p_out.touch()
            p_out.write_bytes(gzip.compress(out.encode('utf-8')))
            print(count, 'written', filename)
            count += 1


def parse_barcodes(forward_barcodes, reverse_barcodes, forward_mapcodes, reverse_mapcodes):
    """
    forward_barcodes, reverse_barcodes are the paths to those barcode files.
    forward_mapcodes, reverse_mapcodes are lists of barcodes taken from the mapping file.
    reverse_complement: reverse complement the barcodes in the mapping file.
    """
    results_dict = dict.fromkeys(reverse_mapcodes)
    full_results = {}
    with open(forward_barcodes, 'r') as forward, open(reverse_barcodes, 'r') as reverse:
        forward_barcodes = forward.readlines()
        for i, line in enumerate(reverse):
            line = line.strip('\n')
            if not i % 4 == 1:
                continue
            else:
                # If the forward, reverse barcodes are in the mapping file.
                if line in reverse_mapcodes and forward_barcodes[i].strip('\n') in forward_mapcodes:
                    # count barcodes
                    if not results_dict[line]:
                        results_dict[line] = 1
                    else:
                        results_dict[line] += 1

                if line in full_results.keys():
                    full_results[line] += 1
                else:
                    full_results[line] = 1
        return results_dict, full_results
