import json
from flask import Flask, jsonify, request
from playhouse.shortcuts import model_to_dict
from passlib.hash import pbkdf2_sha256 as pbkdf2

from agent.job import JobModel
from agent.server import Server
from agent.proxy import Proxy

application = Flask(__name__)


@application.before_request
def validate_access_token():
    try:
        if application.debug:
            return
        method, access_token = request.headers["Authorization"].split(" ")
        stored_hash = Server().config["access_token"]
        if method.lower() == "bearer" and pbkdf2.verify(
            access_token, stored_hash
        ):
            return
        return jsonify({"message": "Unauthenticated"}), 401
    except Exception:
        return jsonify({"message": "Bad Request"}), 400


@application.route("/authentication", methods=["POST"])
def reset_authentication_token():
    data = request.json
    Server().setup_authentication(data["token"])
    return jsonify({"message": "Success"})


"""
POST /benches
{
    "name": "bench-1",
    "python": "/usr/bin/python3.6",
    "apps": [
        {
            "name": "frappe",
            "repo": "https://github.com/frappe/frappe",
            "branch": "version-12",
            "hash": "ada803c5b57e489bfbc2dee6292a4bcb3ff69aa0"
        },
        {
            "name": "erpnext",
            "repo": "https://github.com/frappe/erpnext",
            "branch": "version-12",
            "hash": "782f45ae5f272173b5daadb493d40cf7ccf131b4"
        }
    ],
    "config": {
        "background_workers": 8,
        "error_report_email": "test@example.com",
        "frappe_user": "frappe",
        "gunicorn_workers": 16,
        "mail_login": "test@example.com",
        "mail_password": "test",
        "mail_server": "smtp.example.com",
        "monitor": 1,
        "redis_cache": "redis://localhost:13000",
        "redis_queue": "redis://localhost:11000",
        "redis_socketio": "redis://localhost:12000",
        "server_script_enabled": true,
        "socketio_port": 9000,
        "webserver_port": 8000
    }
}

"""


@application.route("/ping")
def ping():
    return {"message": "pong"}


@application.route("/server")
def get_server():
    return Server().dump()


@application.route("/benches")
def get_benches():
    return {name: bench.dump() for name, bench in Server().benches.items()}


@application.route("/benches/<string:bench>")
def get_bench(bench):
    return Server().benches[bench].dump()


@application.route("/benches/<string:bench>/sites")
def get_sites(bench):
    sites = Server().benches[bench].sites
    return {name: site.dump() for name, site in sites.items()}


@application.route("/benches/<string:bench>/apps")
def get_apps(bench):
    apps = Server().benches[bench].apps
    return {name: site.dump() for name, site in apps.items()}


@application.route("/benches/<string:bench>/config")
def get_config(bench):
    return Server().benches[bench].config


@application.route("/benches/<string:bench>/sites/<string:site>")
def get_site(bench, site):
    return Server().benches[bench].sites[site].dump()


@application.route("/benches", methods=["POST"])
def new_bench():
    data = request.json
    job = Server().new_bench(
        data["name"], data["python"], data["config"], data["apps"]
    )
    return {"job": job}


"""
POST /benches/bench-1/sites
{
    "name": "test.frappe.cloud",
    "mariadb_root_password": "root",
    "admin_password": "admin",
    "apps": ["frappe", "press"],
    "config": {
        "monitor": 1,
    }
}

"""


@application.route("/benches/<string:bench>/sites", methods=["POST"])
def new_site(bench):
    data = request.json
    job = (
        Server()
        .benches[bench]
        .new_site(
            data["name"],
            data["config"],
            data["apps"],
            data["mariadb_root_password"],
            data["admin_password"],
        )
    )
    return {"job": job}


@application.route("/benches/<string:bench>/config", methods=["POST"])
def bench_set_config(bench):
    data = request.json
    job = Server().benches[bench].setconfig_job(data)
    return {"job": job}


@application.route("/proxy/hosts", methods=["POST"])
def proxy_add_host():
    data = request.json
    job = Proxy().add_host_job(data["name"])
    return {"job": job}


@application.route("/proxy/upstreams", methods=["POST"])
def proxy_add_upstream():
    data = request.json
    job = Proxy().add_upstream_job(data["name"])
    return {"job": job}


@application.route(
    "/proxy/upstreams/<string:upstream>/sites", methods=["POST"]
)
def proxy_add_upstream_site(upstream):
    data = request.json
    job = Proxy().add_site_to_upstream_job(upstream, data["name"])
    return {"job": job}


@application.route(
    "/proxy/upstreams/<string:upstream>/sites/<string:site>",
    methods=["DELETE"],
)
def proxy_remove_upstream_site(upstream, site):
    job = Proxy().remove_site_from_upstream_job(upstream, site)
    return {"job": job}


def to_dict(model):
    if isinstance(model, JobModel):
        job = model_to_dict(model, backrefs=True)
        job["data"] = json.loads(job["data"]) or {}
        for step in job["steps"]:
            step["data"] = json.loads(step["data"]) or {}
    else:
        job = list(map(model_to_dict, model))
    return job


@application.route("/jobs")
@application.route("/jobs/<int:id>")
@application.route("/jobs/status/<string:status>")
def jobs(id=None, status=None):
    choices = [x[1] for x in JobModel._meta.fields["status"].choices]
    if id:
        job = to_dict(JobModel.get(JobModel.id == id))
    elif status in choices:
        job = to_dict(
            JobModel.select(JobModel.id, JobModel.name).where(
                JobModel.status == status
            )
        )
    return jsonify(json.loads(json.dumps(job, default=str)))
