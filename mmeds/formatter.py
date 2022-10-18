from mmeds.logging import Logger
import mmeds.config as fig


SELECT_SPECIMEN_QUERY = """\
    SELECT\
    `SpecimenID`,\
    `SpecimenCollectionDate`,\
    `SpecimenNotes`,\
    `SpecimenCollectionTime`,\
    `SpecimenWeight`,\
    `SpecimenWeightUnit`,\
    `StudyName`\
    FROM `SpecimenView` WHERE `StudyName` = "{StudyName}"\
"""

SELECT_COLUMN_SPECIMEN_QUERY = """\
    SELECT {column} FROM\
 `SpecimenView` WHERE\
 `StudyName` = "{StudyName}" AND\
 `SpecimenID` = "{SpecimenID}"\
"""

INSERT_ALIQUOT_QUERY = """\
INSERT INTO `Aliquot` (`idAliquot`, `Specimen_idSpecimen`, `Aliquot`.`user_id`, `AliquotID`, `AliquotWeight`) VALUES {}\
"""

SELECT_ALIQUOT_QUERY = """\
SELECT `AliquotID`, `AliquotWeight` FROM `Aliquot` WHERE `Specimen_idSpecimen` = "{idSpecimen}"\
"""

GET_ALIQUOT_QUERY = """\
SELECT {column} FROM `Aliquot` WHERE AliquotID = "{AliquotID}"\
"""

SELECT_SAMPLE_QUERY = """\
SELECT\
`SampleID`,\
`SampleDatePerformed`,\
`SampleProcessor`,\
`SampleProtocolInformation`,\
`SampleProtocolID`,\
`SampleConditions`,\
`SampleTool`,\
`SampleToolVersion`\
FROM `SampleView` WHERE `Aliquot_idAliquot` = "{idAliquot}"
"""

GET_SAMPLE_QUERY = """\
SELECT * FROM SampleView WHERE\
 `Aliquot_idAliquot` = {idAliquot}
"""

INSERT_QUERY = """INSERT INTO {table} ({columns}) VALUES ({values})"""

SELECT_COLUMN_SUBJECT_QUERY = """\
    SELECT {column} FROM\
    `SubjectView` WHERE\
    `StudyName` = "{StudyName}" AND\
    `HostSubjectId` = "{HostSubjectId}"\
"""

SELECT_META_ANALYSIS_QUERY = """\
    SELECT DISTINCT `RawDataID`, `StudyName`{columns}\
    FROM `MetaAnalysisView`\
    WHERE {where};
"""


def build_html_table(header, data):
    """
    Return an HTML formatted table containing the results of the provided query
    :header: List, The column names
    :data: List of Tuples, The rows of the columns
    """

    # Add the table column labels
    html = '<table class="w3-table-all w3-hoverable">\n<thead>\n <tr class="w3-light-grey">\n'
    for column in header:
        html += '<th><b>{}</b></th>\n'.format(column)
    html += '</tr></thead>'

    Logger.error("Table contents")
    Logger.error(data)

    # Add each row
    for row in data:
        html += '<tr class="w3-hover-blue">\n'
        for i, value in enumerate(row):
            html += '<th> <a href="#{' + str(i) + '}' + '"> {} </a></th>'.format(value)
        html += '</tr>'

    html += '</table>'
    return html


def build_clickable_table(header, data, page, common_args={}, row_args={}):
    """
    Return a table formatted from SQL results. Each row is a clickable link
    :header: List, The column names
    :data: List of Tuples, The rows of the columns
    :page: A string, Key to the webpage the rows will link to
    :common_args: A dict, Arguments that are the same for every row in the table
    :row_args: A dict, Argument That are specific to each row in the table. They're pulled from table.
    ==========================================================================================
    E.G.
    Building the specimen table for server.query.select_specimen

    Call looks like:

    build_clickable_table(header, data, 'query_generate_aliquot_id_page',
                          {'AccessCode': access_code},
                          {'SpecimenID': 0})

    header = [
    'SpecimenID',
    'SpecimenCollectionDate',
    'SpecimenNotes',
    'SpecimenCollectionTime',
    'SpecimenWeight',
    'StudyName'
    ]
    data = [
    ('L6S93',
     datetime.date(2018, 1, 2),
     'Alot',
     datetime.timedelta(seconds=45180),
     Decimal('0.000100000'),
     'Short_Study'),
    ('L6S93',
     datetime.date(2018, 1, 2),
     ...)
    ...
    ]
    """

    # Add the table column labels
    html = '<table class="w3-table-all w3-hoverable">\n<thead>\n <tr class="w3-light-grey">\n'
    for column in header:
        html += '<th><b>{}</b></th>\n'.format(column)
    html += '</tr></thead>'

    Logger.error("Table contents")
    Logger.error(data)

    # Add each row
    for row in data:
        html += '<tr class="w3-hover-blue">\n'
        for i, value in enumerate(row):
            row_html = '<td><a style="display:block" href="{page}?{args}"'
            # For the first row set the class
            if i == 0:
                row_html += ' class="row-link"'
            # for following rows set the indent
            else:
                row_html += ' tabindex="-1"'
            row_html += '>{value}</a></td>\n'

            html += row_html.format(
                value=value,
                page=fig.HTML_ARGS[page],
                args='&'.join(['{}={}'.format(key, item) for key, item in common_args.items()] +
                              ['{}={}'.format(key, row[item]) for key, item in row_args.items()]))
        html += '</tr>\n'
    html += '</table>'
    return html


def build_study_code_dropdown(studies):
    """
    Creates a drop down of study names with values of the access codes from the provided mongo Documents
    ===================================================================================================
    :studies: A list of MMEDSdocs Corresponding to a user's studies
    """
    study_code_html = '<option value="{access_code}">{study_name}</option>'
    study_code_list = []
    for study in studies:
        study_code_list.append(study_code_html.format(study_name=study.study_name,
                                                      access_code=study.access_code))
    return '\n'.join(study_code_list)
