"""Local web interface for the MEDSYS hospital queue and patient records."""

from __future__ import annotations

import hmac
import json
import mimetypes
import re
import secrets
import threading
from datetime import date
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import medsys

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8000
MAX_BODY = 1_000_000
SESSION_COOKIE = "medsys_session"
SESSION_MAX_AGE = 8 * 60 * 60
sessions: dict[str, dict[str, str]] = {}
state_lock = threading.RLock()

# Keep the web and command-line interfaces on the same data files, regardless
# of the directory from which this script is started.
medsys.DATA_FILE = str(ROOT / "medsys.txt")
medsys.USER_FILE = str(ROOT / "users.txt")
medsys.load()
medsys.init_users()


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _read_users() -> list[tuple[str, str, str]]:
    users: list[tuple[str, str, str]] = []
    try:
        with open(medsys.USER_FILE, encoding="utf-8") as user_file:
            for line in user_file:
                fields = line.strip().split("|", 2)
                if len(fields) == 3:
                    users.append((fields[0], fields[1], fields[2]))
    except FileNotFoundError:
        pass
    return users


def _safe_field(value: object, label: str, maximum: int = 200) -> str:
    if not isinstance(value, str):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{label} is required.")
    cleaned = value.strip()
    if not cleaned:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{label} is required.")
    if len(cleaned) > maximum or any(char in cleaned for char in "|\r\n"):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{label} is invalid.")
    return cleaned


def _valid_name(value: object, label: str) -> str:
    name = _safe_field(value, label, 60)
    if not all(char.isalpha() or char in " -'" for char in name):
        raise ApiError(
            HTTPStatus.BAD_REQUEST,
            f"{label} can only contain letters, spaces, apostrophes, or hyphens.",
        )
    return name


def _optional_name(body: dict[str, object], field: str, label: str) -> str:
    value = body.get(field, "")
    return "" if value is None or value == "" else _valid_name(value, label)


def _patient_dict(patient: medsys.Patient, role: str) -> dict[str, object]:
    result: dict[str, object] = {
        "id": patient.id,
        "first": patient.f,
        "middle": patient.m,
        "last": patient.l,
        "name": " ".join(part for part in (patient.f, patient.m, patient.l) if part),
        "age": patient.age,
        "gender": patient.gender,
        "history": [],
        "prescriptions": [],
    }
    if role != "pharmacist":
        result["history"] = [
            {
                "id": item.id,
                "action": item.act,
                "result": item.res,
                "doctor": item.doc,
                "date": item.date,
            }
            for item in reversed(patient.history)
        ]
    if role == "pharmacist":
        result["prescriptions"] = [
            {
                "id": item.id,
                "medicine": item.med,
                "dosage": item.dose,
                "instructions": item.instr,
                "doctor": item.doctor,
                "date": item.date,
            }
            for item in reversed(patient.prescriptions)
        ]
    return result


def _bootstrap(role: str) -> dict[str, object]:
    patients = medsys.patients
    queue = []
    for position, (patient_id, priority) in enumerate(medsys.active_queue, start=1):
        patient = medsys.find_patient(patient_id)
        if patient is not None:
            queue.append(
                {
                    "position": position,
                    "priority": priority,
                    "patient": _patient_dict(patient, role),
                }
            )
    all_history = [record for patient in patients for record in patient.history]
    all_prescriptions = [
        record for patient in patients for record in patient.prescriptions
    ]
    today = date.today().isoformat()
    return {
        "patients": [_patient_dict(patient, role) for patient in patients],
        "queue": queue if role != "pharmacist" else [],
        "stats": {
            "patients": len(patients),
            "in_queue": len(queue) if role != "pharmacist" else 0,
            "emergency": sum(item["priority"] == "emergency" for item in queue)
            if role != "pharmacist"
            else 0,
            "encounters": len(all_history),
            "prescriptions": len(all_prescriptions),
            "today": sum(record.date == today for record in all_history),
        },
    }


def _patient_or_404(patient_id: int) -> medsys.Patient:
    patient = medsys.find_patient(patient_id)
    if patient is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "Patient not found.")
    return patient


class MedsysHandler(BaseHTTPRequestHandler):
    server_version = "MEDSYS/1.0"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_json(self, status: int, payload: object, cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, relative_path: str) -> None:
        file_path = WEB_ROOT / relative_path
        try:
            body = file_path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in (
            "application/javascript",
            "application/json",
        ):
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid request body.") from exc
        if length <= 0 or length > MAX_BODY:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Request body is empty or too large.")
        try:
            decoded = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object.")
        return decoded

    def _session(self) -> tuple[str, dict[str, str]] | tuple[None, None]:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        if morsel is None:
            return None, None
        token = morsel.value
        user = sessions.get(token)
        if user is None:
            return None, None
        return token, user

    def _require_user(self, roles: set[str] | None = None) -> dict[str, str]:
        _, user = self._session()
        if user is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Please sign in to continue.")
        if roles is not None and user["role"] not in roles:
            raise ApiError(HTTPStatus.FORBIDDEN, "Your role cannot perform this action.")
        return user

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if not path.startswith("/api/") and path != "/api":
            if method != "GET":
                self.send_error(HTTPStatus.NOT_FOUND)
            elif path == "/":
                self._send_file("index.html")
            elif path in ("/styles.css", "/app.js"):
                self._send_file(path.lstrip("/"))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            with state_lock:
                self._api(method, path)
        except ApiError as error:
            self._send_json(error.status, {"error": error.message})
        except (OSError, ValueError) as error:
            print(f"Request failed: {error}")
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "The request could not be completed."})

    def _api(self, method: str, path: str) -> None:
        if method == "GET" and path == "/api/session":
            _, user = self._session()
            self._send_json(HTTPStatus.OK, {"user": user})
            return

        if method == "POST" and path == "/api/login":
            body = self._body()
            username = _safe_field(body.get("username"), "Username", 80)
            password = _safe_field(body.get("password"), "Password", 200)
            role = _safe_field(body.get("role"), "Role", 30).lower()
            if role not in {"receptionist", "doctor", "pharmacist"}:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid role.")
            valid = any(
                hmac.compare_digest(saved_user.encode(), username.encode())
                and hmac.compare_digest(saved_password.encode(), password.encode())
                and saved_role == role
                for saved_user, saved_password, saved_role in _read_users()
            )
            if not valid:
                raise ApiError(HTTPStatus.UNAUTHORIZED, "Those sign-in details do not match.")
            token = secrets.token_urlsafe(32)
            user = {"username": username, "role": role}
            sessions[token] = user
            cookie = (
                f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; "
                f"Max-Age={SESSION_MAX_AGE}"
            )
            self._send_json(HTTPStatus.OK, {"user": user}, cookie)
            return

        if method == "POST" and path == "/api/logout":
            token, _ = self._session()
            if token:
                sessions.pop(token, None)
            cookie = f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
            self._send_json(HTTPStatus.OK, {"ok": True}, cookie)
            return

        user = self._require_user()
        role = user["role"]
        if method == "GET" and path == "/api/bootstrap":
            self._send_json(HTTPStatus.OK, _bootstrap(role))
            return

        if method == "POST" and path == "/api/patients":
            self._require_user({"receptionist"})
            body = self._body()
            first = _valid_name(body.get("first"), "First name")
            middle = _optional_name(body, "middle", "Middle name")
            last = _valid_name(body.get("last"), "Last name")
            age = body.get("age")
            if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 150:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Age must be between 0 and 150.")
            gender = str(body.get("gender", "")).upper()
            if gender not in ("M", "F"):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose M or F for gender.")
            candidate = medsys.Patient(0, first, middle, last, age, gender)
            if medsys.is_duplicate(candidate):
                raise ApiError(HTTPStatus.CONFLICT, "A patient with those details already exists.")
            priority = body.get("priority")
            if priority not in (None, "", "Regular", "emergency"):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid queue priority.")
            patient_id = max((patient.id for patient in medsys.patients), default=0) + 1
            patient = medsys.Patient(patient_id, first, middle, last, age, gender)
            medsys.patients.append(patient)
            if priority == "emergency":
                medsys.active_queue.insert(0, (patient_id, "emergency"))
            elif priority == "Regular":
                medsys.active_queue.append((patient_id, "Regular"))
            medsys.save()
            self._send_json(HTTPStatus.CREATED, {"patient": _patient_dict(patient, role)})
            return

        match = re.fullmatch(r"/api/patients/(\d+)(?:/(queue))?", path)
        if match:
            patient_id = int(match.group(1))
            if match.group(2) == "queue":
                if method != "POST":
                    raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                self._require_user({"receptionist"})
                patient = _patient_or_404(patient_id)
                body = self._body()
                priority = body.get("priority")
                if priority not in ("Regular", "emergency"):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid queue priority.")
                if medsys.in_active(patient_id):
                    raise ApiError(HTTPStatus.CONFLICT, "This patient is already in the queue.")
                if priority == "emergency":
                    medsys.active_queue.insert(0, (patient_id, "emergency"))
                else:
                    medsys.active_queue.append((patient_id, "Regular"))
                medsys.save()
                self._send_json(HTTPStatus.OK, {"ok": True})
                return
            patient = _patient_or_404(patient_id)
            if method == "PUT":
                self._require_user({"receptionist", "doctor"})
                body = self._body()
                first = _valid_name(body.get("first"), "First name")
                middle = _optional_name(body, "middle", "Middle name")
                last = _valid_name(body.get("last"), "Last name")
                age = body.get("age")
                if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 150:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Age must be between 0 and 150.")
                gender = str(body.get("gender", "")).upper()
                if gender not in ("M", "F"):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Choose M or F for gender.")
                candidate = medsys.Patient(patient_id, first, middle, last, age, gender)
                if medsys.is_duplicate(candidate, patient_id):
                    raise ApiError(HTTPStatus.CONFLICT, "A patient with those details already exists.")
                patient.f, patient.m, patient.l = first, middle, last
                patient.age, patient.gender = age, gender
                medsys.save()
                self._send_json(HTTPStatus.OK, {"patient": _patient_dict(patient, role)})
                return
            if method == "DELETE":
                self._require_user({"receptionist", "doctor"})
                medsys.remove_from_queue(patient_id, silent=True)
                medsys.patients.remove(patient)
                medsys.save()
                self._send_json(HTTPStatus.OK, {"ok": True})
                return

        match = re.fullmatch(r"/api/queue/(\d+)", path)
        if match:
            if method != "DELETE":
                raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            self._require_user({"receptionist", "doctor"})
            patient_id = int(match.group(1))
            _patient_or_404(patient_id)
            if not medsys.in_active(patient_id):
                raise ApiError(HTTPStatus.NOT_FOUND, "This patient is not in the queue.")
            medsys.remove_from_queue(patient_id, silent=True)
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        if method == "POST" and path == "/api/serve":
            self._require_user({"doctor"})
            body = self._body()
            patient_id = body.get("patient_id")
            if isinstance(patient_id, bool) or not isinstance(patient_id, int):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a patient from the queue.")
            patient = _patient_or_404(patient_id)
            if not medsys.in_active(patient_id):
                raise ApiError(HTTPStatus.CONFLICT, "This patient is no longer in the queue.")
            action = _safe_field(body.get("action"), "Encounter", 200)
            result = _safe_field(body.get("result"), "Outcome", 500)
            medicine = body.get("medicine", "")
            dosage = body.get("dosage", "")
            instructions = body.get("instructions", "")
            prescription = None
            if medicine or dosage or instructions:
                medicine = _safe_field(medicine, "Medicine", 150)
                dosage = _safe_field(dosage, "Dosage", 150)
                instructions = _safe_field(instructions, "Instructions", 500)
                prescription = medsys.Prescription(
                    medsys.next_prescription_id,
                    medicine,
                    dosage,
                    instructions,
                    medsys.now_date(),
                    user["username"],
                )
                medsys.next_prescription_id += 1
            patient.history.append(
                medsys.new_history(action, result, user["username"])
            )
            if prescription is not None:
                patient.prescriptions.append(prescription)
            medsys.remove_from_queue(patient_id, silent=True)
            medsys.save()
            self._send_json(HTTPStatus.CREATED, {"ok": True})
            return

        raise ApiError(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MedsysHandler)
    server.daemon_threads = True
    print(f"MEDSYS web interface running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down MEDSYS web interface.")
    finally:
        server.server_close()
        with state_lock:
            medsys.save()


if __name__ == "__main__":
    main()
