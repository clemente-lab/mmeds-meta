import mmeds.config as fig
from mmeds.logging import Logger


SELECT_SPECIMEN_QUERY = """
SELECT * FROM Specimen INNER JOIN
Experiment INNER JOIN
Study ON Study_idStudy = idStudy
ON Experiment_idExperiment = idExperiment
WHERE StudyName = "{}"
"""

GET_SPECIMEN_ID_QUERY = """
SELECT idSpecimen FROM Specimen INNER JOIN
Experiment INNER JOIN
Study ON Study_idStudy = idStudy
ON Experiment_idExperiment = idExperiment
WHERE StudyName = "{}"
AND SpecimenID = "{}"
"""

INSERT_ALIQUOT_QUERY = """
INSERT INTO `Aliquot` (`idAliquot`, `Specimen_idSpecimen`, `Aliquot`.`user_id`, `AliquotID`, `AliquotWeight`)
VALUES
{}
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

    # Add each row
    for row in data:
        html += '<tr class="w3-hover-blue">'
        for i, value in enumerate(row):
            html +=  ''.format(access_code, row[0])
            html += '<th><a href="../query/generate_id?AccessCode={}&SpecimenID={}">{}</a></th>'.format(access_code,
                                                                                                     row[0],
                                                                                                     value)
        html += '</tr>\n'
    html += '</table>'
    return html
