import json
import string
import random
from locust import HttpUser, TaskSet, between, task, constant
from requests.exceptions import ConnectionError
from locust.contrib.fasthttp import FastHttpLocust

USERS = list(range(1,5000))[::-1]

class UserBehavior(TaskSet):
    def __init__(self, *args, **kwargs):
        self.id = USERS.pop()
        self.logged_in = False
        self.cookies = None
        super().__init__(*args, **kwargs)

    def login(self):
        if self.logged_in:
            return True
        name = f"user{self.id}"
        #print(f"login {name}")
        data = {"username": name, "password": name}
        with self.client.post("/apps/users/login/", data, catch_response=True) as res:
            try:
                if res.ok:
                    whoami = res.json()
                    if whoami["user"] is None:
                        res.failure("Was not logged in")
                    else:
                        self.present = whoami["user"]["is_present"]
                        self.cookies = res.cookies
                        self.logged_in = True
                        res.success()
                else:
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")

        return self.logged_in

    def on_stop(self):
        USERS.append(self.id)

    @task()
    def toggle_present(self):
        self._toggle_present("/apps/users/setpresence/")

    #@task()
    def toggle_present_no_autoupdate(self):
        self._toggle_present("/apps/users/setpresence-no-autoupdate/")

    #@task()
    def toggle_present_only_autoupdate(self):
        self._toggle_present("/apps/users/setpresence-only-autoupdate/")

    def _toggle_present(self, url):
        if not self.login():
            return
        with self.json_post(url, not self.present) as res:
            try:
                if res.ok:
                    self.present = not self.present
                    res.success()
                else:
                    print(res.content)
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")

    #@task()
    def simple_autoupdate(self):
        self.request("/apps/users/simple-autoupdate/")

    #@task()
    def simple_autoupdate_no_history(self):
        self.request("/apps/users/simple-autoupdate-no-history/")

    #@task()
    def echo(self):
        data = {"data": ''.join(random.choice(string.ascii_lowercase) for i in range(16))}
        self.request("/apps/users/echo/", data)

    #@task()
    def echo_login(self):
        if not self.login():
            return
        data = {"data": ''.join(random.choice(string.ascii_lowercase) for i in range(16))}
        self.request("/apps/users/echo-login/", data)

    #@task()
    def get_config(self):
        self.request("/apps/users/get-config/")

    #@task()
    def get_config_login(self):
        if not self.login():
            return
        self.request("/apps/users/get-config-login/")

    #@task()
    def current_autoupdate(self):
        self.request("/apps/users/current-autoupdate/")

    #@task()
    def current_autoupdate_login(self):
        if not self.login():
            return
        self.request("/apps/users/current-autoupdate-login/")

    def request(self, url, data=None):
        with self.json_post(url, data) as res:
            try:
                if res.ok:
                    res.success()
                else:
                    print(res.content)
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")

    def json_post(self, url, data):
        headers = {
            'Content-Type': 'application/json',
        }
        if self.cookies is not None:
            headers['X-CSRFToken'] = self.cookies.get('OpenSlidesCsrfToken')

        return self.client.post(
            url,
            data=json.dumps(data),
            headers=headers,
            catch_response=True,
            cookies=self.cookies)

class UserClass(HttpUser):
    tasks = [UserBehavior]
    #wait_time = between(1, 5)
    wait_time = constant(2)
