from locust import TaskSet, task, HttpLocust
from mmeds.mmeds import insert_html, insert_error
from mmeds.database import Database
from mmeds.authentication import add_user, remove_user
from pathlib import Path
from time import sleep
import mmeds.config as fig
import urllib3
import hashlib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MyTasks(TaskSet):

    def on_start(self):
        self.client.verify = False

        self.ID = self.locust.IDs.pop()
        self.user = fig.TEST_USER + self.ID
        self.dir = Path(str(fig.TEST_DIR) + self.ID)
        self.code = fig.TEST_CODE + self.ID

        add_user(self.user, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        self.login()

        with open(fig.HTML_DIR / 'select_download.html') as f:
            page = f.read().format(self.user)

        # Get page for succesful download
        for i, f in enumerate(fig.TEST_FILES.keys()):
            page = insert_html(page, 22 + i, '<option value="{}">{}</option>'.format(f, f))
        self.download_success = page

        # Get page for busy download
        with open(fig.HTML_DIR / 'welcome.html') as f:
            page = f.read().format(user=self.user)
        page = insert_error(page, 22, 'Requested study is currently unavailable')

        self.download_failure = page
        with Database(self.dir, user='root', owner=self.user, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=self.code)
        self.upload_files()

    def on_stop(self):
        self.logout()

    def login(self):
        self.client.post('/login',
                         {
                             'username': self.user,
                             'password': fig.TEST_PASS
                         })

    def logout(self):
        self.client.post('/logout')
        remove_user(self.user, True)

    @task
    def read_root(self):
        with self.client.get('/', catch_response=True) as response:
            sess = response.headers['Set-Cookie']
            split = sess.split(';')
            session_id = split[0].split('=')[1]

    @task
    def access_download(self):
        address = '/run_analysis?access_code={}&tool={}'.format(self.code, fig.TEST_TOOL)
        self.client.get(address)
        address = '/download_page?access_code={}'.format(self.code)
        with self.client.get(address, catch_response=True) as result:
            assert str(result.text) == self.download_failure
        # The duration of the sleep is set by the end of the
        # fig.TEST_TOOL string in mmeds/config
        # Makes sure the wait is the same duration as the spawned process
        sleep(float(fig.TEST_TOOL.split('-')[-1]))

        address = '/download_page?access_code={}'.format(self.code)
        with self.client.get(address, catch_response=True) as result:
            assert str(result.text) == self.download_success

    @task
    def select_download(self):
        """ Test download selection. """
        address = '/download_page?access_code={}'.format(self.code)
        with self.client.get(address) as result:
            assert str(result.text) == self.download_success
            for download in fig.TEST_FILES.keys():
                address = '/select_download'
                with self.client.post(address, {'download': download}) as dresult:

                    h1 = hashlib.md5()
                    h1.update(dresult.content)

                    hash1 = h1.digest()
                    hash2 = fig.TEST_CHECKS[download]

                    # Assert that the hashes match
                    assert hash1 == hash2

    @task
    def upload_files(self):
        address = '/upload?study_type={}'.format('qiime')
        with self.client.get(address):
            address = '/validate_qiime'
            with open(fig.TEST_METADATA, 'rb') as f:
                metadata = f.read()
            with open(fig.TEST_READS, 'rb') as f:
                reads = f.read()
            with open(fig.TEST_BARCODES, 'rb') as f:
                barcodes = f.read()
            files = {
                'myMetaData': metadata,
                'reads': reads,
                'barcodes': barcodes
            }
            # Test the upload
            with self.client.post(address, files=files) as result:
                print(result)


class MyUser(HttpLocust):
    host = 'https://localhost:{}'.format(fig.PORT)
    IDs = [str(i) for i in range(500)]
    task_set = MyTasks

    def teardown(self):
        with Database(self.dir, user='root', owner=self.user, testing=True) as db:
            db.mongo_clean(self.code)
