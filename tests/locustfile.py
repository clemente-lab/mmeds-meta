from locust import TaskSet, task, HttpLocust
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MyTasks(TaskSet):

    def on_start(self):
        self.client.verify = False

    @task
    def read_root(self):
        self.client.get('/')


class MyUser(HttpLocust):
    host = 'https://localhost:8080'
    task_set = MyTasks
