from locust import HttpLocust, TaskSet, between, task
from requests.exceptions import ConnectionError
from locust.contrib.fasthttp import FastHttpLocust

USERS = list(range(1,5000))[::-1]

class UserBehavior(TaskSet):
    def __init__(self, *args, **kwargs):
        self.id = USERS.pop()
        self.logged_in = False
        super().__init__(*args, **kwargs)

    @task()
    def login(self):
        if self.logged_in:
            return
        name = f"user{self.id}"
        print(f"login {name}")
        data = {"username": name, "password": name}
        with self.client.post("/apps/users/login/", data, catch_response=True) as res:
            try:
                if res.ok:
                    whoami = res.json()
                    if whoami["user"] is None:
                        res.failure("Was not logged in")
                    else:
                        res.success()
                        self.logged_in = True
                else:
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")

    def on_stop(self):
        USERS.append(self.id)

class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    wait_time = between(1, 5)
