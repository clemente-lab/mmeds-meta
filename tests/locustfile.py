from locust import TaskSet, task, HttpLocust
import mmeds.config as fig
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MyTasks(TaskSet):

    def on_start(self):
        self.client.verify = False
        self.login()

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
        self.client.get('/download_page?access_code={}'.format(fig.TEST_CODE))


class MyUser(HttpLocust):
    host = 'https://localhost:8080'
    task_set = MyTasks
