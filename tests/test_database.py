from mmeds.database import Database
from mmeds.authentication import add_user
import mmeds.config as fig

# Checking whether or NOT a blank value or default value can be retrieved from the database.
# Validating each value if it is successfully saved to the database.
# Ensuring the data compatibility against old hardware or old versions of operating systems.
# Verifying the data in data tables can be modified and deleted
# Running data tests for all data files, including clip art, tutorials, templates, etc.


def test_users():
    add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL)
    with Database(fig.TEST_DIR, user='root', owner='testuser') as db:
        access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_FAIL,
                                                          'qiime',
                                                          reads=fig.TEST_READS,
                                                          barcodes=fig.TEST_BARCODES,
                                                          access_code=fig.TEST_CODE)


test_users()
