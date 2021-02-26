from mmeds.logging import Logger


SELECT_SPECIMEN_QUERY = """\
SELECT\
 `SpecimenID`,\
 `SpecimenCollectionDate`,\
 `SpecimenInformation`,\
 `SpecimenCollectionTime`,\
 `SpecimenWeight`,\
 `StudyName`\
 FROM `SpecimenView` WHERE `StudyName` = "{StudyName}"\
"""

SELECT_ID_SPECIMEN_QUERY = """\
    SELECT `idSpecimen` FROM\
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
SELECT {column} FROM `Aliquot` WHERE AliquotID = "{aliquot_id}"\
"""

SELECT_SAMPLE_QUERY = """\
SELECT\
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
        html += '<tr class="w3-hover-blue">'
        for i, value in enumerate(row):
            html += '<th> <a href="#{' + str(i) + '}' + '"> {} </a></th>'.format(value)
        html += '</tr>'

    html += '</table>'
    return html


def build_specimen_table(access_code, header, data):
    """
    Return a table formatted for the specimen select page
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
    row_html = '<th><a href="../query/generate_aliquot_id?AccessCode={}&SpecimenID={}">{}</a></th>'

    # Add each row
    for row in data:
        html += '<tr class="w3-hover-blue">'
        # TODO fix hardcoded web path here
        for i, value in enumerate(row):
            html += row_html.format(access_code, row[0], value)
        html += '</tr>\n'
    html += '</table>'
    return html


def build_aliquot_table(access_code, header, data):
    """
    Return a table formatted for Samples
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

    row_html = '<th><a href="../query/generate_sample_id?AccessCode={}&AliquotID={}">{}</a></th>'
    # Add each row
    for row in data:
        html += '<tr class="w3-hover-blue">'
        # TODO fix hardcoded web path here
        for i, value in enumerate(row):
            html += row_html.format(access_code, row[0], value)
        html += '</tr>\n'
    html += '</table>'
    return html
