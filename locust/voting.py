import json
from locust import HttpLocust, TaskSet, task, constant
from requests.exceptions import ConnectionError

USERS = list(range(1,5000))[::-1]

MOTION_POLL_ID = 1

class UserBehavior(TaskSet):
    def __init__(self, *args, **kwargs):
        self.id = USERS.pop()
        self.logged_in = False
        self.is_present = False
        self.has_voted = False
        self.cookies = None
        super().__init__(*args, **kwargs)

    def login(self):
        if self.logged_in:
            return True
        name = f"user{self.id}"
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

    @task
    def vote(self):
        if not self.login():
            return
        if not self.set_present():
            return
        if self.has_voted:
            return

        if self.request(f"/rest/motions/motion-poll/{MOTION_POLL_ID}/vote/", "Y"):
            self.has_voted = True

    def set_present(self):
        if self.is_present:
            return True

        if self.request("/apps/users/setpresence/", True):
            self.is_present = True

        return self.is_present

    def request(self, url, data=None):
        with self.json_post(url, data) as res:
            try:
                if res.ok:
                    res.success()
                    return True
                else:
                    print(res.content)
                    res.failure(f"not ok: {res.status_code}")
            except ConnectionError:
                res.failure("ConnectionError")
        return False

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

class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    wait_time = constant(1)
