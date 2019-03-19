from collections import defaultdict
from mmeds.error import InvalidConfigError, InvalidSQLError, InvalidModuleError, LoggedOutError
from subprocess import run
from datetime import datetime
from pathlib import Path
from os import environ
from numpy import nan, issubdtype, int64, float64, datetime64, number
from functools import wraps
from inspect import isfunction
from smtplib import SMTP
from imaplib import IMAP4_SSL
from email.message import EmailMessage

import mmeds.config as fig
import pandas as pd


def catch_server_errors(page_method):
    """ Handles LoggedOutError, and HTTPErrors for all mmeds pages. """
    @wraps(page_method)
    def wrapper(*a, **kwargs):
        try:
            return page_method(*a, **kwargs)
        except LoggedOutError:
            with open(fig.HTML_DIR / 'index.html') as f:
                page = f.read()
            return page
    return wrapper


def decorate_all_methods(decorator):
    def apply_decorator(cls):
        for k, m in cls.__dict__.items():
            if isfunction(m):
                setattr(cls, k, decorator(m))
        return cls
    return apply_decorator


def load_config(config_file, metadata):
    """ Read the provided config file to determine settings for the analysis. """
    config = {}
    # If no config was provided load the default
    if config_file is None or config_file == '':
        log('Using default config')
        with open(fig.STORAGE_DIR / 'config_file.txt', 'r') as f:
            page = f.read()
    else:
        # Load the file contents
        page = config_file

    # Parse the config
    lines = page.split('\n')
    for line in lines:
        if line.startswith('#') or line == '':
            continue
        else:
            parts = line.split('\t')
            if parts[0] not in fig.CONFIG_PARAMETERS:
                raise InvalidConfigError('Invalid parameter {} in config file'.format(parts[0]))
            config[parts[0]] = parts[1]
    try:
        # Parse the values/levels to be included in the analysis
        for option in fig.CONFIG_PARAMETERS:
            # Get approriate metadata columns based on the metadata file
            if option == 'metadata':
                config[option], config['metadata_continuous'] = get_valid_columns(metadata, config[option])
            # Split taxa_levels into a list or create the list if 'all'
            elif option == 'taxa_levels':
                if config[option] == 'all':
                    config[option] = [i + 1 for i in range(7)]
                else:
                    # Otherwise split the values into a list
                    config[option] = config[option].split(',')
            # Otherwise just ensure the parameter exists.
            else:
                assert config[option]
    except (KeyError, AssertionError):
        raise InvalidConfigError('Missing parameter {} in config file'.format(option))

    return config


def copy_metadata(metadata_file, metadata_copy):
    """
    Copy the provided metadata file with a few additional columns to be used for analysis
    =====================================================================================
    :metadata_file: Path to the metadata file.
    :metadata_copy: Path to save the new metadata file.
    """
    mdf = pd.read_csv(metadata_file, sep='\t', header=[0, 1], na_filter=False).T
    mdf.loc[('AdditionalMetaData', 'Separate'), :] = ['Required', 'Text', 'Limit 45 Characters'] +\
        ['All' for x in range(mdf.shape[1] - 3)]
    mdf.loc[('AdditionalMetaData', 'Together'), :] = mdf.loc['RawData', 'RawDataID']
    mdf.T.to_csv(metadata_copy, sep='\t')


def get_valid_columns(metadata_file, option):
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
    summary_cols = []
    col_types = {}
    # Filter out any categories containing only NaN
    # Or containing only a single metadata value
    # Or where every sample contains a different value
    df = pd.read_csv(metadata_file, header=0, skiprows=[0, 2, 3, 4], sep='\t')
    if option == 'all':
        cols = df.columns
    else:
        cols = option.split(',')
    # Ensure there aren't any invalid columns specified to be included in the analysis
    try:
        for col in cols:
            # If 'all' only select columns that don't have all the same or all unique values
            if (df[col].isnull().all() or df[col].nunique() == 1 or df[col].nunique() == len(df[col])):
                if col in ['Together', 'Separate']:
                    summary_cols.append(col)
                    col_types[col] = False
                elif option == 'all':
                    continue
                else:
                    raise InvalidConfigError('Invalid metadata column {} selected for analysis'.format(col))
            # If the columns is explicitly specified only check that it exists in the metadata
            else:
                assert df[col].any()
                summary_cols.append(col)
                col_types[col] = pd.api.types.is_numeric_dtype(df[col])
    except KeyError:
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
    ICD_codes = {
        'XXX.XXXX': 'Subject is healthy to the best of our knowledge',
        'NA': 'No Value',
        nan: 'No Value'
    }
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
            code = code[:3] + '.' + code[3:]
            ICD_codes[code] = description
    return ICD_codes


def load_mapping_file(file_fp, delimiter):
    """
    Load the metadata file and assign datatypes to the columns
    ==========================================================
    :file_fp: The path to the mapping file
    :delimiter: The delimiter used in the mapping file
    """
    df = pd.read_csv(file_fp,
                     sep=delimiter,
                     header=[0, 1],
                     skiprows=[2, 3, 4],
                     na_filter=False)
    df.replace('NA', nan, inplace=True)
    # Get the tables in the dataframe while maintaining order
    tables = []
    errors = []
    warnings = []
    for (table, header) in df.axes[1]:
        tables.append(table)
        for column in df[table]:
            if '' in df[table][column]:
                errors.append('-1\t-1\tColumn Value Error: Column {} is missing entries'.format(column))
            try:
                df[table].assign(column=df[table][column].astype(fig.COLUMN_TYPES[table][column]))
            # Additional metadata won't have an entry so will automatically be treated as a string
            except KeyError:
                df[table].assign(column=df[table][column].astype('object'))
            # Error handling for column values that don't match the column type
            except ValueError:
                errors.append('-1\t-1\tColumn Value Error: Column {} contains the wrong type of values'.format(column))
    tables = list(dict.fromkeys(tables))
    return tables, df, errors, warnings


def load_html(file_path, **kwargs):
    """
    Load the specified html file. Inserting the head and topbar
    """
    # Load the html page
    with open(file_path) as f:
        page = f.read().split('\n')

    # Load the head information
    with open(fig.HTML_DIR / 'header.html') as f:
        header = f.read().split('\n')

    # Load the topbar information
    with open(fig.HTML_DIR / 'topbar.html') as f:
        topbar = f.read().split('\n')

    new_page = page[:3] + header + topbar + page[3:]
    return '\n'.join(new_page).format(**kwargs)


def load_MIxS_metadata(file_fp, skip_rows, unit_column):
    """
    A function for load and transforming the MIxS data in a pandas dataframe.
    ========================================================================
    :file_fp: The path to the file to convert
    :skip_rows: The number of rows to skip after the header
    :unit_column: A string. If None then the function checks each cell for units.
    """
    units = {}
    # Read in the data file
    df = pd.read_csv(file_fp, header=0, sep='\t')
    # Set the index to be the 'column_header' column
    df.set_index('column_header', inplace=True)
    # Remove rows with null indexes
    df = df.loc[df.index.notnull()]
    # Transpose the dataframe across the diagonal
    df = df.T
    # Drop unnamed columns
    df.drop([x for x in df.axes[0] if 'Unnamed' in x], inplace=True)
    # Drop any columns with only np.nan values
    df.dropna(how='all', axis='columns', inplace=True)
    # Replace np.nans with "NA"s
    df.fillna('"NA"', inplace=True)
    return df, units


def insert_error(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<h4><font color="red">' + error_message + '</font></h4>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_warning(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] +\
        ['<h4><font color="orange">' + error_message + '</font></h4>'] +\
        lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_html(page, line_number, html):
    """
    Inserts additional HTML into the provided HTML page at the specified line number.
    =================================================================================
    :page: The page (a string) to insert the new HTML into
    :line_number: The line to insert the HTML
    :html: The HTML to insert
    """
    lines = page.split('\n')
    new_lines = lines[:line_number] + [html] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def is_numeric(s):
    """
    Check if the provided string is a number.
    =========================================
    :s: The string to check
    """
    if issubdtype(type(s), str):
        if ('.e' in s or '.E' in s):
            return False
        try:
            float(s)
            return True
        except (TypeError, ValueError):
            pass
        try:
            import unicodedata
            unicodedata.numeric(s)
            return True
        except (TypeError, ValueError):
            pass
    elif issubdtype(type(s), number):
        return True
    return False


def create_local_copy(fp, filename, path=fig.STORAGE_DIR):
    """ Create a local copy of the file provided. """
    log("In create_local_copy.")
    # If the fp is None return None
    if fp is None:
        return None

    # Create the filename
    file_copy = Path(path) / Path(filename).name

    # Ensure there is not already a file with the same name
    while file_copy.is_file():
        file_copy = Path(path) / '_'.join([fig.get_salt(5), filename])
    log('Created filepath {}'.format(file_copy))

    # Write the data to a new file stored on the server
    with open(file_copy, 'wb') as nf:
        while True:
            data = fp.read(8192)
            nf.write(data)
            if not data:
                break
    log('Copy finished')
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

    log('generate errors')
    log(errors)
    # Add Errors to markup table
    for error in errors:
        row, col, item = error.split('\t')
        if row == '-1' and col == '-1':
            top.append(['red', item])
        markup[int(row)][int(col)] = ['red', item]

    # Add warnings to markup table
    for warning in warnings:
        row, col, item = warning.split('\t')
        if row == '-1' and col == '-1':
            top.append(['orange', item])
        markup[int(row)][int(col)] = ['orange', item]

    # Add general warnings and errors
    for color, er in top:
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


def split_data(column):
    """
    Split the data into multiple columns
    ------------------------------------
    :column: A pandas Series object
    """
    result = defaultdict(list)
    if column.name == 'lat_lon':
        log("name: {}, vals: {}".format(column.name, column))
        # Skip the header
        for value in column[1:]:
            parsed = value.strip('+').split('-')
            log('Parsed: {}'.format(parsed))
            result['Latitude'].append(parsed[0])
            result['Longitude'].append(parsed[1])
    elif column.name == 'assembly_name':
        for value in column:
            parsed = value.strip(' ')
            result['Tool'].append(parsed[0])
            result['Version'].append(parsed[1])
    else:
        raise ValueError
    return result


def MIxS_to_mmeds(file_fp, out_file, skip_rows=0, unit_column=None):
    """
    A function for converting a MIxS formatted datafile to a MMEDS formatted file.
    ------------------------------------------------------------------------------
    :file_fp: The path to the file to convert
    :out_file: The path to write the new metadata file to
    :skip_rows: The number of rows to skip after the header
    :unit_column: A string. If None then the function checks each cell for units.
    """

    df, units = load_MIxS_metadata(file_fp, skip_rows, unit_column)

    # Create a new dictionary for accessing the columns belonging to each table
    all_cols = defaultdict(list)
    all_cols.update(fig.METADATA_COLS)

    # Find all columns that don't have a mapping and add them to AdditionalMetaData
    unmapped_items = [x for x in df.columns if fig.MMEDS_MAP.get(x) is None]
    for item in unmapped_items:
        # If there is no units entry for the item
        if pd.isnull(units.get(item)):
            first = df[item][0].split(' ')
            # If the value is numeric grab the units in the data cell
            if is_numeric(first[0]):
                unit_col = item
                df[item] = df[item].map(lambda x: x.split(' ')[0])
            else:
                unit_col = item
        # Add the units to the header if available
        else:
            unit_col = item
        fig.MIXS_MAP[('AdditionalMetaData', str(unit_col))] = str(unit_col)
        fig.MMEDS_MAP[item] = ('AdditionalMetaData', str(unit_col))
        all_cols['AdditionalMetaData'].append(str(unit_col))

    # Build the data for the new format
    meta = {}
    for col in df.columns:
        (table, column) = fig.MMEDS_MAP[col]
        if ':' in column:
            log('Table: {}, Column: {}'.format(table, column))
            cols = column.split(':')
            data = split_data(df[col])
            for new_col in cols:
                meta[(table, new_col)] = data[new_col]
        else:
            meta[(table, column)] = df[col].astype(str)

    # Write the file
    write_mmeds_metadata(out_file, meta, all_cols, len(df))


def write_mmeds_metadata(out_file, meta, all_cols, num_rows):
    """
    Write out a mmeds metadate file based on the data provided
    ----------------------------------------------------------
    :out_file: The path to write the metadata to
    :meta: A dictionary containing all the information to write
    :all_cols: A dictionary specifying all the tables and columns
        for this metadata file
    :num_rows: An int. The number of rows in the original metadata
    """

    # Build the first two rows of the mmeds metadata file
    table_row, column_row = [], []
    for table in sorted(all_cols.keys()):
        for column in sorted(all_cols[table]):
            table_row.append(table)
            column_row.append(column.strip(' ()'))

    # Get the additional header rows from one of the example metadata files
    md_template = pd.read_csv(fig.TEST_METADATA, sep='\t', header=[0, 1], nrows=5, na_filter=False)
    column_type = []
    column_unit = []
    column_required = []
    for (table, column) in zip(table_row, column_row):
        try:
            column_type.append(str(md_template[table][column].iloc[0]))
            column_unit.append(str(md_template[table][column].iloc[1]))
            column_required.append(str(md_template[table][column].iloc[2]))
        except (KeyError, IndexError):
            column_type.append('')
            column_unit.append('')
            column_required.append('')

    # Write out each line of the file
    with open(out_file, 'w') as f:
        f.write('\t'.join(table_row) + '\n')
        f.write('\t'.join(column_row) + '\n')
        f.write('\t'.join(column_type) + '\n')
        f.write('\t'.join(column_unit) + '\n')
        f.write('\t'.join(column_required) + '\n')
        for i in range(num_rows):
            row = []
            for table, column in zip(table_row, column_row):
                # Add the value to the row
                try:
                    row.append(meta[(table, column)][i].strip('"'))
                # If a value doesn't exist for this table, column insert NA
                except (KeyError, IndexError):
                    log('Key error for {}, {}, {}'.format(table, column, i))
                    row.append('NA')
            f.write('\t'.join(row) + '\n')


def mmeds_to_MIxS(file_fp, out_file, skip_rows=0, unit_column=None):
    """
    A function to convert a mmeds formatted metadata file to a MIxS one.
    """
    # Read in the data file
    df = pd.read_csv(file_fp, header=[0, 1], skiprows=[2, 3, 4], sep='\t')
    with open(out_file, 'w') as f:
        f.write('\t'.join(['column_header'] + list(map(str, df['RawData']['RawDataID'].tolist()))) + '\n')
        for (col1, col2) in df.columns:
            if df[col1][col2].notnull().any():
                try:
                    header = fig.MIXS_MAP[(col1, col2)]
                except KeyError:
                    header = col2
                f.write('\t'.join([header] + list(map(str, df[col1][col2].tolist()))) + '\n')


def log(text):
    """ Write provided text to the log file. """
    if isinstance(text, dict):
        log_text = '\n'.join(["{}: {}".format(key, value) for (key, value) in text.items()])
    elif isinstance(text, list):
        log_text = '\n'.join(list(map(str, text)))
    else:
        log_text = str(text)
    with open(fig.MMEDS_LOG, 'a+') as f:
        f.write('{}: {}\n'.format(datetime.now(), log_text))


def send_email(toaddr, user, message='upload', testing=False, **kwargs):
    """
    Sends a confirmation email to addess containing user and code.
    ==============================================================
    :toaddr: The address to send the email to
    :user: The user account that toaddr belongs to
    :message: The type of message to send
    :kwargs: Any information that is specific to a paricular message type
    """
    log('Send email to: {} on behalf of {}'.format(toaddr, user))

    # Templates for the different emails mmeds sends
    if message == 'upload':
        body = 'Hello {email},\nthe user {user} uploaded data to the mmeds database server.\n' +\
               'In order to gain access to this data without the password to\n{user} you must provide ' +\
               'the following access code:\n{code}\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'New Data Uploaded'
    elif message == 'reset':
        body = 'Hello {user},\nYour password has been reset.\n' +\
               'The new password is:\n{password}\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {contact} with a description of your problem.\n'
        subject = 'Password Reset'
    elif message == 'change':
        body = 'Hello {user},\nYour password has been changed.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Password Change'
    elif message == 'analysis':
        body = 'Hello {user},\nYour requested {analysis} analysis on study {study} is complete.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Analysis Complete'
    elif message == 'error':
        body = 'Hello {user},\nThere was an error during requested {analysis} analysis.\n' +\
               'Please check the error file associated with this study.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Error During Analysis'

    email_body = body.format(
        user=user,
        cemail=fig.CONTACT_EMAIL,
        email=toaddr,
        analysis=kwargs.get('analysis_type'),
        study=kwargs.get('study_name'),
        code=kwargs.get('code'),
        password=kwargs.get('password')
    )
    if testing:
        # Setup the email to be sent
        msg = EmailMessage()
        msg['From'] = fig.MMEDS_EMAIL
        msg['To'] = toaddr
        # Add in any necessary text fields
        msg.set_content(email_body)

        # Connect to the server and send the mail
        server = SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(fig.MMEDS_EMAIL, 'mmeds_server')
        server.send_message(msg)
        server.quit()
    else:
        script = 'echo "{body}" | mail -s "{subject}" "{toaddr}"'
        if 'summary' in kwargs.keys():
            script += ' -A {summary}'.format(kwargs['summary'])
        cmd = script.format(body=email_body, subject=subject, toaddr=toaddr)
        run(['/bin/bash', '-c', cmd], check=True)
    return cmd


def recieve_email(num_messages=1, search='FROM "{}"'.format(fig.MMEDS_EMAIL)):
    """
    Fetch email from the test account
    :num_messages: An int. How many emails to return, starting with the most recent
    :search: A string. Any specific search criteria, default is emails from mmeds
    """
    mail = IMAP4_SSL('imap.gmail.com')
    mail.login(fig.TEST_EMAIL, fig.TEST_EMAIL_PASS)
    log(mail.list())
    mail.select('inbox')
    result, data = mail.search(None, search)
    messages = []
    all_mail = data[0].split(b' ')
    for message in all_mail[len(all_mail) - num_messages:]:
        typ, m = mail.fetch(message, 'ALL')
        messages.append((typ, m))
    mail.logout()
    return messages


def pyformat_translate(value):
    """ Convert from numpy to standard python datatypes. """
    if isinstance(value, int64):
        result = int(value)
    elif isinstance(value, float64):
        result = float(value)
    else:
        result = value
    return result


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
        # Update any values with local variables
        if '$' in line:
            for variable, path in variables.items():
                line = line.replace('${}'.format(variable), path)
        if '~' in line:
            for variable, path in variables.items():
                line = line.replace('~', new_env['HOME'])
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
    return new_env


def create_qiime_from_mmeds(mmeds_file, qiime_file, analysis_type):
    """
    Create a qiime mapping file from the mmeds metadata
    ===================================================
    :mmeds_file: The path to the mmeds metadata.
    :qiime_file: The path where the qiime mapping file should be written.
    """
    mdata = pd.read_csv(mmeds_file, header=1, skiprows=[2, 3, 4], sep='\t')

    headers = list(mdata.columns)

    di = headers.index('RawDataID')
    hold = headers[0]
    headers[0] = '#SampleID'
    headers[di] = hold

    di = headers.index('SampleID')
    hold = headers[3]
    headers[3] = 'MmedsSampleID'
    headers[di] = hold

    hold = headers[1]
    di = headers.index('BarcodeSequence')
    headers[1] = 'BarcodeSequence'
    headers[di] = hold

    hold = headers[2]
    di = headers.index('LinkerPrimerSequence')
    headers[2] = 'LinkerPrimerSequence'
    headers[di] = hold

    hold = headers[-1]
    di = headers.index('Description')
    headers[-1] = 'Description'
    headers[di] = hold

    with open(qiime_file, 'w') as f:
        f.write('\t'.join(headers) + '\n')
        if 'qiime2' in analysis_type:
            f.write('\t'.join(['#q2:types'] + ['categorical' for x in range(len(headers) - 1)]) + '\n')
        for row_index in range(len(mdata)):
            row = []
            for header in headers:
                if header == '#SampleID':
                    row.append(str(mdata['RawDataID'][row_index]))
                elif header == 'MmedsSampleID':
                    row.append(str(mdata['SampleID'][row_index]))
                else:
                    row.append(str(mdata[header][row_index]))
            f.write('\t'.join(row) + '\n')
    return list(mdata.columns)


def quote_sql(sql, quote='`', **kwargs):
    """ Returns the sql query with the identifiers properly qouted using QUOTE"""
    # There are only two quote characters allowed
    assert (quote == '`' or quote == "'")
    quoted_args = {}
    for key, item in kwargs.items():
        # Check the entry is a string
        if not isinstance(item, str):
            raise InvalidSQLError('SQL Identifier {} is not a string'.format(item))
        # Check the entry isn't too long
        elif len(item) > 66:
            raise InvalidSQLError('SQL Identifier {} is too long ( > 66 characters)'.format(item))
        # Check that there are only allowed characters: Letters, Numbers, and '_'
        elif not item.replace('_', '').isalnum():
            raise InvalidSQLError('Illegal characters in identifier {}.' +
                                  ' Only letters, numbers, and "_" are permitted'.format(item))

        quoted_args[key] = '{quote}{item}{quote}'.format(quote=quote, item=item)
    formatted = sql.format(**quoted_args)
    return formatted
