from time import sleep
from multiprocessing import Process

from mmeds.mmeds import send_email, create_local_copy, log, load_config
from mmeds.database import Database
from mmeds.authentication import get_email
from mmeds.error import AnalysisError, InvalidConfigError
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.config import DATABASE_DIR


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


def spawn_analysis(atype, user, access_code, config_file, testing):
    """ Start running the analysis in a new process """

    # Load the config for this analysis
    with Database('.', owner=user, testing=testing) as db:
        files, path = db.get_mongo_files(access_code)

    config = load_config(config_file, files['metadata'])

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


def handle_data_upload(metadata, for_reads, rev_reads, barcodes, username, testing):
    """
    Thread that handles the upload of large data files.
    ===================================================
    :metadata_copy: A string. Location of the metadata.
    :reads: A file
    :barcodes: @Todo
    :username: @Todo
    :testing: True if the server is running locally.
    """
    log('In handle_data_upload')
    count = 0
    new_dir = DATABASE_DIR / ('{}_{}'.format(username, count))
    while new_dir.is_dir():
        new_dir = DATABASE_DIR / ('{}_{}'.format(username, count))
        count += 1
    new_dir.mkdir()

    # Create a copy of the MetaData
    with open(metadata, 'rb') as f:
        metadata_copy = create_local_copy(f, metadata.name, new_dir)

    # Create a copy of the Data files
    if for_reads.file is not None:
        for_reads_copy = create_local_copy(for_reads.file, for_reads.filename, new_dir)
    else:
        for_reads_copy = None
    if rev_reads.file is not None:
        rev_reads_copy = create_local_copy(rev_reads.file, rev_reads.filename, new_dir)
    else:
        rev_reads_copy = None

    # Create a copy of the Data file
    if barcodes.file is not None:
        barcodes_copy = create_local_copy(barcodes.file, barcodes.filename, new_dir)
    else:
        barcodes_copy = None

    log('Copies created')
    # Otherwise upload the metadata to the database
    with Database(new_dir, owner=username, testing=testing) as db:
        access_code, study_name, email = db.read_in_sheet(metadata_copy,
                                                          'qiime',
                                                          for_reads=for_reads_copy,
                                                          rev_reads=rev_reads_copy,
                                                          barcodes=barcodes_copy)
    log('Added to database')

    # Send the confirmation email
    send_email(email, username, code=access_code, testing=testing)
    log('Email sent')
