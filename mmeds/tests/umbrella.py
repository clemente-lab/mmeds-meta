from subprocess import run
import time

from mmeds.authentication import add_user, remove_user
from mmeds.database import upload_metadata

import mmeds.config as fig
import mmeds.secrets as sec

add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing = True)
add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing = True)

test_setup = [(fig.TEST_SUBJECT, 
               fig.TEST_SPECIMEN, 
               fig.TEST_DIR, 
               fig.TEST_USER, 
               'Test_Single', 
               'single_end', 
               'single_barcodes', 
               fig.TEST_READS, 
               None, 
               fig.TEST_BARCODES, 
               fig.TEST_CODE)] ''',
              (fig.TEST_SUBJECT_ALT,
               fig.TEST_SPECIMEN_ALT,
               fig.TEST_DIR_0,
               fig.TEST_USER_0,
               'Test_Single_0',
               'single_end',
               'single-barcodes',
               fig.TEST_READS,
               None,
               fig.TEST_BARCODES,
               fig.TEST_CODE + '0'),
              (fig.TEST_SUBJECT,
               fig.TEST_SPECIMEN,
               fig.TEST_DIR,
               fig.TEST_USER,
               'Test_Paired',
               'paired_end',
               'single_barcodess',
               fig.TEST_READS,
               fig.TEST_REV_READS,
               fig.TEST_BARCODES,
               fig.TEST_CODE_PAIRED),
              (fig.TEST_SUBJECT,
               fig.TEST_SPECIMEN,
               fig.TEST_DIR,
               fig.TEST_USER,
               'Test_Demuxed',
               'single_end',
               'single_barcodes',
               fig.TEST_DEMUXED,
               None,
               fig.TEST_BARCODES,
               fig.TEST_CODE_DEMUX)]
'''
for setup in test_setup:
    start = time.time()
    upload_metadata(setup)
    print(time.time() - start)

#run(['pytest', 'mmeds/tests/unit/test_database.py'])
run(['pytest', 'mmeds/tests/unit/test_documents.py'])

remove_user(fig.TEST_USER, testing = True)
#remove_user(fig.TEST_USER_0, testing = True)
