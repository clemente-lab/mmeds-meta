from locust import TaskSet, task, HttpLocust
from mmeds.mmeds import insert_html, insert_error
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

    def login(self):
        self.client.post('/login',
                         {
                             'username': fig.TEST_USER,
                             'password': fig.TEST_PASS
                         })

    @task
    def read_root(self):
        self.client.get('/')

    @task
    def get_download(self):
        self.client.get("/download_page?access_code={}".format(fig.TEST_CODE))
        self.client.get('/run_analysis?access_code={}&tool={}'.format(fig.TEST_CODE, fig.TEST_TOOL))
        result = self.client.get('/download_page?access_code={}'.format(fig.TEST_CODE))
        assert str(result.text) == self.download_failure
        sleep(int(fig.TEST_TOOL.split('-')[-1]))

        result = self.client.get('/download_page?access_code={}'.format(fig.TEST_CODE))
        assert str(result.text) == self.download_success


class MyUser(HttpLocust):
    host = 'https://localhost:8080'
    task_set = MyTasks
