from time import sleep
from multiprocessing import Process

from mmeds.mmeds import send_email, create_local_copy, log
from mmeds.database import Database
from mmeds.authentication import get_email
from mmeds.error import AnalysisError
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2


def run_analysis(qiime):
    """ Run qiime analysis. """
    try:
        qiime.run()
    except AnalysisError as e:
        email = get_email(qiime.owner, testing=qiime.testing)
        send_email(email,
                   qiime.owner,
                   'error',
                   analysis_type=qiime.atype,
                   error=e.message,
                   testing=qiime.testing)


def test(time, atype):
    """ Simple function for analysis called during testing """
    sleep(time)


def spawn_analysis(atype, user, access_code, config, testing):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        qiime = Qiime1(user, access_code, atype, config, testing)
        p = Process(target=run_analysis, args=(qiime,))
    elif 'qiime2' in atype:
        qiime = Qiime2(user, access_code, atype, config, testing)
        p = Process(target=run_analysis, args=(qiime,))
    elif 'test' in atype:
        time = float(atype.split('-')[-1])
        p = Process(target=test, args=(time, atype))
    p.start()
    return p


def handle_modify_data(access_code, myData, data_type, testing):
    with Database('.', testing=testing) as db:
        # Create a copy of the Data file
        files, path = db.get_mongo_files(access_code=access_code)
        data_copy = create_local_copy(myData.file, myData.filename, path=path)
        db.modify_data(data_copy, access_code, data_type)


def handle_data_upload(metadata_copy, reads, barcodes, username, path, testing):
    """
    Thread that handles the upload of large data files.
    ===================================================
    :metadata_copy: A string. Location of the metadata.
    :reads: A file
    :barcodes: @Todo
    :username: @Todo
    :path: @Todo
    :testing: True if the server is running locally.
    """
    log('In handle_data_upload')

    # Create a copy of the Data file
    if reads.file is not None:
        reads_copy = create_local_copy(reads.file, reads.filename, path)
    else:
        reads_copy = None

    # Create a copy of the Data file
    if barcodes.file is not None:
        barcodes_copy = create_local_copy(barcodes.file, barcodes.filename, path)
    else:
        barcodes_copy = None

    log('Copies created')
    # Otherwise upload the metadata to the database
    with Database(path, owner=username, testing=testing) as db:
        access_code, study_name, email = db.read_in_sheet(metadata_copy,
                                                          'qiime',
                                                          reads=reads_copy,
                                                          barcodes=barcodes_copy)
    log('Added to database')

    # Send the confirmation email
    send_email(email, username, code=access_code, testing=testing)
    log('Email sent')
