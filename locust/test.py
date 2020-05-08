import json
from locust import HttpLocust, TaskSet, between, task
from requests.exceptions import ConnectionError

USERS = list(range(1,5000))[::-1]

class UserBehavior(TaskSet):
    def __init__(self, *args, **kwargs):
        self.id = USERS.pop()
        self.logged_in = False
        super().__init__(*args, **kwargs)

    def login(self):
        if self.logged_in:
            return True
        name = f"user{self.id}"
        print(f"login {name}")
        data = {"username": name, "password": name}
        with self.client.post("/apps/users/login/", data, catch_response=True) as res:
            try:
                if res.ok:
                    whoami = res.json()
                    self.present = whoami["user"]["is_present"]
                    self.cookies = res.cookies
                    self.logged_in = True
                    res.success()
                else:
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")

        return self.logged_in

    def on_start(self):
        pass

    def on_stop(self):
        USERS.append(self.id)

    @task()
    def toggle_present(self):
        if not self.login():
            return
        print(f"User: {self.id}")
        with self.json_post("/apps/users/setpresence/", not self.present) as res:
            try:
                if res.ok:
                    self.present = not self.present
                    res.success()
                else:
                    print(res.content)
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")

    def json_post(self, url, data):
        headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': self.cookies.get('OpenSlidesCsrfToken')
        }
        return self.client.post(
            url,
            data=json.dumps(data),
            headers=headers,
            catch_response=True,
            cookies=self.cookies)

class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    wait_time = between(1, 5)
