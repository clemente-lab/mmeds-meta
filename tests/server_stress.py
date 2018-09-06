from locust import TaskSet, task, HttpLocust
from mmeds.mmeds import insert_html, insert_error
from mmeds.database import Database
from time import sleep
import mmeds.config as fig
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MyTasks(TaskSet):

    def on_start(self):
        self.client.verify = False
        self.login()
        with open(fig.HTML_DIR / 'select_download.html') as f:
            page = f.read().format(fig.TEST_USER)

        # Get page for succesful download
        for i, f in enumerate(fig.TEST_FILES):
            page = insert_html(page, 10 + i, '<option value="{}">{}</option>'.format(f, f))
        self.download_success = page

        # Get page for busy download
        with open(fig.HTML_DIR / 'welcome.html') as f:
            page = f.read().format(user=fig.TEST_USER)
        page = insert_error(page, 31, 'Requested study is currently unavailable')

        self.download_failure = page
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE)

        address = '/download_page?access_code={}'.format(fig.TEST_CODE)
        with self.client.get(address, catch_response=True) as result:
            print(result.text)

    def on_stop(self):
        self.logout()

    def login(self):
        self.client.post('/login',
                         {
                             'username': fig.TEST_USER,
                             'password': fig.TEST_PASS
                         })

    def logout(self):
        self.client.post('/logout')

    #@task
    def read_root(self):
        self.client.get('/')

    #@task
    def access_download(self):
        address = '/run_analysis?access_code={}&tool={}'.format(fig.TEST_CODE, fig.TEST_TOOL)
        self.client.get(address)
        address = '/download_page?access_code={}'.format(fig.TEST_CODE)
        with self.client.get(address, catch_response=True) as result:
            assert str(result.text) == self.download_failure
        # The duration of the sleep is set by the end of the
        # fig.TEST_TOOL string in mmeds/config
        # Makes sure the wait is the same duration as the spawned process
        sleep(int(fig.TEST_TOOL.split('-')[-1]))

        address = '/download_page?access_code={}'.format(fig.TEST_CODE)
        with self.client.get(address, catch_response=True) as result:
            assert str(result.text) == self.download_success

    @task
    def select_download(self):
        """ Test download selection. """
        downloads = [
            'barcodes',
            'reads',
            'metadata'
        ]
        for download in downloads:
            address = '/select_download'
            with self.client.post(address, {'download': download}) as result:
                print(str(type(result)))
                print(str(result))


class MyUser(HttpLocust):
    host = 'https://localhost:{}'.format(fig.PORT)
    task_set = MyTasks
