from time import sleep
from multiprocessing import Process

from mmeds.util import send_email, create_local_copy, log, load_config, load_metadata
from mmeds.database import MetaDataUploader, Database
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.config import DATABASE_DIR


def test(time):
    """ Simple function for analysis called during testing """
    log('test tool sleep for {}'.format(time))
    sleep(time)
    log('test tool wake up')


def spawn_analysis(atype, user, access_code, config_file, testing):
    """ Start running the analysis in a new process """
    log('In spawn_analysis')

    # Load the config for this analysis
    with Database('.', owner=user, testing=testing) as db:
        files, path = db.get_mongo_files(access_code)
    if isinstance(config_file, str):
        log('load path config {}'.format(config_file))
        config = load_config(config_file, files['metadata'])
    elif config_file is None or config_file.file is None:
        log('load default config')
        config = load_config(None, files['metadata'])
    else:
        log('load passed config')
        config = load_config(config_file.file.read().decode('utf-8'), files['metadata'])

    log('After load config')
    log(config)

    if 'qiime1' in atype:
        tool = Qiime1(user, access_code, atype, config, testing)
    elif 'qiime2' in atype:
        tool = Qiime2(user, access_code, atype, config, testing)
    elif 'test' in atype:
        log('test analysis')
        time = float(atype.split('-')[-1])
        tool = Process(target=test, args=(time,))
    else:
        log('atype didnt match any')
    tool.start()
    return tool


def handle_modify_data(access_code, myData, user, data_type, testing):
    with Database(owner=user, testing=testing) as db:
        # Create a copy of the Data file
        files, path = db.get_mongo_files(access_code=access_code)
        data_copy = create_local_copy(myData[1], myData[0], path=path)
        db.modify_data(data_copy, access_code, data_type)


def handle_data_upload(metadata, username, reads_type, testing, *datafiles):
    """
    Thread that handles the upload of large data files.
    ===================================================
    :metadata_copy: A string. Location of the metadata.
    :reads: A tuple. First element is the name of the reads/data file,
                     the second is a file type io object
    :barcodes: A tuple. First element is the name of the barcodes file,
                        the second is a file type io object
    :username: @Todo
    :testing: True if the server is running locally.
    """
    log('In handle_data_upload')
    mdf = load_metadata(metadata)
    study_name = mdf.Study.StudyName.iloc[0]
    count = 0
    new_dir = DATABASE_DIR / ('{}_{}_{}'.format(username, study_name, count))
    while new_dir.is_dir():
        new_dir = DATABASE_DIR / ('{}_{}_{}'.format(username, study_name, count))
        count += 1
    new_dir.mkdir()

    # Create a copy of the MetaData
    with open(metadata, 'rb') as f:
        metadata_copy = create_local_copy(f, metadata.name, new_dir)

    # Create a copy of the Data file
    datafile_copies = {datafile[0]: create_local_copy(datafile[2], datafile[1], new_dir) for datafile in datafiles}
    for (key, value) in datafile_copies.items():
        log('{}: {}'.format(key, value))

    with MetaDataUploader(metadata=metadata_copy,
                          path=new_dir,
                          study_type='qiime',
                          reads_type=reads_type,
                          owner=username,
                          testing=testing) as up:
        access_code, study_name, email = up.import_metadata(**datafile_copies)
    log('Added to database')

    # Send the confirmation email
    send_email(email, username, code=access_code, testing=testing)
    log('Email sent')

    return access_code
