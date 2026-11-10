#!/usr/bin/env python3
"""MEDSYS hospital queue and patient-record system."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date

DATA_FILE = "medsys.txt"
USER_FILE = "users.txt"


@dataclass
class Prescription:
    id: int
    med: str
    dose: str
    instr: str
    date: str
    doctor: str


@dataclass
class History:
    id: int
    act: str
    res: str
    doc: str
    date: str


@dataclass
class Patient:
    id: int
    f: str
    m: str
    l: str
    age: int
    gender: str
    history: list[History] = field(default_factory=list)
    prescriptions: list[Prescription] = field(default_factory=list)


@dataclass
class User:
    name: str = ""
    password: str = ""
    role: str = ""


patients: list[Patient] = []
active_queue: list[tuple[int, str]] = []
current_user = User()
next_history_id = 1
next_prescription_id = 1


def clear() -> None:
    if not sys.stdout.isatty():
        return
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="", flush=True)


def press() -> None:
    input("\nPress Enter...")


def read_key() -> str:
    """Read one key without waiting for Enter when attached to a terminal."""
    if os.name == "nt":
        import msvcrt

        return msvcrt.getwch()
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        return line[0]

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if not char:
            raise EOFError
        return char
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_password(prompt: str) -> str:
    print(prompt, end="", flush=True)
    if not sys.stdin.isatty():
        return input()

    password = ""
    while True:
        char = read_key()
        if char in ("\r", "\n"):
            break
        if char in ("\b", "\x7f"):
            if password:
                password = password[:-1]
                print("\b \b", end="", flush=True)
        elif len(char) == 1 and 32 <= ord(char) <= 126:
            password += char
            print("*", end="", flush=True)
    print()
    return password


def trim(value: str) -> str:
    return value.strip(" \t\n\r")


def to_lower(value: str) -> str:
    return value.lower()


def now_date() -> str:
    return date.today().isoformat()


def get_str(prompt: str) -> str:
    while True:
        value = trim(input(prompt))
        if value:
            return value
        print("Cannot be empty.")


def get_name(prompt: str) -> str:
    while True:
        value = get_str(prompt)
        if all(char.isalpha() or char in " -" for char in value):
            return value
        print("Use letters, spaces or hyphens.")


def get_gender() -> str:
    while True:
        print("Gender (M/F): ", end="", flush=True)
        gender = read_key().upper()
        print(gender)
        if gender in ("M", "F"):
            return gender
        print("Invalid.")


def _read_integer(prompt: str, min_value: int, max_value: int) -> int:
    while True:
        raw = input(prompt)
        match = re.match(r"\s*([+-]?\d+)", raw)
        if match:
            value = int(match.group(1))
            if min_value <= value <= max_value:
                return value
        print("Invalid.")


def get_age() -> int:
    return _read_integer("Age (0-150): ", 0, 150)


def get_int(prompt: str, min_value: int = 1, max_value: int = 1_000_000) -> int:
    return _read_integer(prompt, min_value, max_value)


def yes_no(prompt: str) -> bool:
    while True:
        answer = trim(input(f"{prompt} (y/n): "))
        if answer in ("y", "Y"):
            return True
        if answer in ("n", "N"):
            return False
        print("Please enter y or n.")


def _take_line(lines: Iterator[str]) -> str:
    try:
        return next(lines)
    except StopIteration as exc:
        raise ValueError("Unexpected end of medsys.txt") from exc


def _read_count(lines: Iterator[str]) -> int:
    try:
        count = int(_take_line(lines).strip())
    except ValueError as exc:
        raise ValueError("Invalid count in medsys.txt") from exc
    if count < 0:
        raise ValueError("Negative count in medsys.txt")
    return count


def save() -> None:
    output: list[str] = [f"{len(patients)}\n"]
    for patient in patients:
        output.append(
            f"{patient.id}|{patient.f}|{patient.m}|{patient.l}|{patient.age}|{patient.gender}\n"
        )
        output.append(f"{len(patient.history)}\n")
        for item in patient.history:
            output.append(
                f"{item.id}|{item.act}|{item.res}|{item.doc}|{item.date}\n"
            )
        output.append(f"{len(patient.prescriptions)}\n")
        for item in patient.prescriptions:
            output.append(
                f"{item.id}|{item.med}|{item.dose}|{item.instr}|{item.doctor}|{item.date}\n"
            )
    output.append(f"{len(active_queue)}\n")
    for patient_id, priority in active_queue:
        output.append(f"{patient_id}|{priority}\n")
    with open(DATA_FILE, "w", encoding="utf-8", newline="") as data_file:
        data_file.writelines(output)


def load() -> None:
    global next_history_id, next_prescription_id
    try:
        with open(DATA_FILE, encoding="utf-8") as data_file:
            lines = iter(data_file.read().splitlines())
    except FileNotFoundError:
        patients.clear()
        active_queue.clear()
        next_history_id = 1
        next_prescription_id = 1
        return

    loaded_patients: list[Patient] = []
    for _ in range(_read_count(lines)):
        fields = _take_line(lines).split("|")
        if len(fields) < 6:
            raise ValueError("Invalid patient record in medsys.txt")
        patient = Patient(
            id=int(fields[0]),
            f=fields[1],
            m=fields[2],
            l=fields[3],
            age=int(fields[4]),
            gender=fields[5][-1],
        )
        for _ in range(_read_count(lines)):
            record = _take_line(lines).split("|")
            if len(record) < 5:
                raise ValueError("Invalid history record in medsys.txt")
            patient.history.append(
                History(
                    id=int(record[0]),
                    act=record[1],
                    res=record[2],
                    doc=record[3],
                    date="|".join(record[4:]),
                )
            )
        for _ in range(_read_count(lines)):
            record = _take_line(lines).split("|")
            if len(record) < 6:
                raise ValueError("Invalid prescription record in medsys.txt")
            patient.prescriptions.append(
                Prescription(
                    id=int(record[0]),
                    med=record[1],
                    dose=record[2],
                    instr=record[3],
                    doctor=record[4],
                    date="|".join(record[5:]),
                )
            )
        loaded_patients.append(patient)

    loaded_queue: list[tuple[int, str]] = []
    for _ in range(_read_count(lines)):
        record = _take_line(lines).split("|", 1)
        if len(record) != 2:
            raise ValueError("Invalid queue record in medsys.txt")
        loaded_queue.append((int(record[0]), record[1]))

    patients.clear()
    patients.extend(loaded_patients)
    active_queue.clear()
    active_queue.extend(loaded_queue)
    next_history_id = max(
        (record.id for patient in patients for record in patient.history), default=0
    ) + 1
    next_prescription_id = max(
        (record.id for patient in patients for record in patient.prescriptions), default=0
    ) + 1


def in_active(patient_id: int) -> bool:
    return any(queued_id == patient_id for queued_id, _ in active_queue)


def add_to_queue(patient_id: int, emergency: bool) -> None:
    if in_active(patient_id):
        print("Already in queue.")
        return
    if emergency:
        active_queue.insert(0, (patient_id, "emergency"))
    else:
        active_queue.append((patient_id, "Regular"))
    print(f"Added to {'EMERGENCY' if emergency else 'REGULAR'} queue.")
    save()


def remove_from_queue(patient_id: int, silent: bool = False) -> None:
    for index, (queued_id, _) in enumerate(active_queue):
        if queued_id == patient_id:
            del active_queue[index]
            if not silent:
                print("Removed from queue.")
            save()
            return
    if not silent:
        print("Not in queue.")


def find_patient(patient_id: int) -> Patient | None:
    return next((patient for patient in patients if patient.id == patient_id), None)


def is_duplicate(new_patient: Patient, exclude_id: int = -1) -> bool:
    return any(
        patient.id != exclude_id
        and patient.f == new_patient.f
        and patient.m == new_patient.m
        and patient.l == new_patient.l
        and patient.gender == new_patient.gender
        and patient.age == new_patient.age
        for patient in patients
    )


def new_history(action: str, result: str, doctor: str) -> History:
    global next_history_id
    record = History(next_history_id, action, result, doctor, now_date())
    next_history_id += 1
    return record


def new_prescription(medicine: str, dosage: str, instructions: str, doctor: str) -> Prescription:
    global next_prescription_id
    record = Prescription(
        next_prescription_id, medicine, dosage, instructions, now_date(), doctor
    )
    next_prescription_id += 1
    return record


def show_patient(
    patient: Patient, show_history: bool = False, show_prescriptions: bool = False
) -> None:
    print(
        f"\nID: {patient.id}\nName: {patient.f} {patient.m} {patient.l}"
        f"\nAge: {patient.age}\nGender: {patient.gender}"
    )
    if show_history:
        print("--- History ---")
        for item in patient.history:
            print(f"{item.id} | {item.act} | {item.res} | {item.date} | {item.doc}")
    if show_prescriptions:
        print("--- Prescriptions ---")
        for item in patient.prescriptions:
            print(
                f"{item.id} | {item.med} | {item.dose} | {item.instr} | "
                f"{item.date} | Dr.{item.doctor}"
            )


def menu(title: str, options: list[str], zero: str = "Back") -> int:
    while True:
        print(f"\n========= {title} =========")
        for index, option in enumerate(options, start=1):
            print(f" [{index}] {option}")
        print(f" [0] {zero}")
        choice_text = trim(input("Choice: "))
        if not choice_text:
            continue
        if not choice_text[0].isdigit():
            print("Number.")
            continue
        match = re.match(r"\d+", choice_text)
        choice = int(match.group()) if match else -1
        if 0 <= choice <= len(options):
            clear()
            return choice
        print("Invalid.")


def register_patient() -> None:
    first = get_name("First: ")
    middle = get_name("Middle: ")
    last = get_name("Last: ")
    age = get_age()
    gender = get_gender()
    candidate = Patient(0, first, middle, last, age, gender)
    if is_duplicate(candidate):
        print("⚠ Duplicate patient (same name, gender, age).")
        if yes_no("Add existing patient to queue instead?"):
            for patient in patients:
                if (
                    patient.f == first
                    and patient.m == middle
                    and patient.l == last
                    and patient.gender == gender
                    and patient.age == age
                ):
                    choice = menu("Add to queue?", ["Emergency", "Regular"], "Skip")
                    if choice:
                        add_to_queue(patient.id, choice == 1)
                    else:
                        print("Not added.")
                    break
        else:
            print("Registration cancelled.")
        press()
        return

    new_id = max((patient.id for patient in patients), default=0) + 1
    patients.append(Patient(new_id, first, middle, last, age, gender))
    print("Registered.")
    save()
    choice = menu("Add to queue?", ["Emergency", "Regular"], "Skip")
    if choice:
        add_to_queue(new_id, choice == 1)
    press()


def serve() -> None:
    if not active_queue:
        print("No active patients.")
        press()
        return

    choice = menu("Serve", ["Emergency first", "Regular first", "By ID"])
    patient: Patient | None = None
    if choice == 1:
        index = next(
            (i for i, (_, priority) in enumerate(active_queue) if priority == "emergency"),
            None,
        )
        if index is None:
            print("No emergency.")
            press()
            return
        patient = find_patient(active_queue[index][0])
        if patient is not None:
            del active_queue[index]
    elif choice == 2:
        index = next(
            (i for i, (_, priority) in enumerate(active_queue) if priority == "Regular"),
            None,
        )
        if index is None:
            print("No regular.")
            press()
            return
        patient = find_patient(active_queue[index][0])
        if patient is not None:
            del active_queue[index]
    elif choice == 3:
        patient_id = get_int("ID: ")
        patient = find_patient(patient_id)
        if patient is None:
            return
        if not in_active(patient_id):
            print("Not in queue.")
            press()
            return
        remove_from_queue(patient_id, True)

    if patient is not None:
        action = get_str("Action: ")
        result = get_str("Result: ")
        doctor = get_str("Doctor: ")
        patient.history.append(new_history(action, result, doctor))
        if yes_no("Add prescription?"):
            medicine = get_str("Medicine: ")
            dosage = get_str("Dosage: ")
            instructions = get_str("Instructions: ")
            patient.prescriptions.append(
                new_prescription(medicine, dosage, instructions, doctor)
            )
            print("Prescription added.")
        print("Service recorded.")
        save()
    press()


def show_all(prescriptions_only: bool = False) -> None:
    for patient in patients:
        show_patient(patient, not prescriptions_only, prescriptions_only)
    press()


def search_by_id() -> None:
    patient = find_patient(get_int("ID: "))
    if patient is not None:
        show_patient(patient)
    else:
        print("Not found.")
    press()


def show_with_history() -> None:
    patient = find_patient(get_int("ID: "))
    if patient is not None:
        show_patient(patient, True)
    press()


def show_with_prescriptions() -> None:
    patient = find_patient(get_int("ID: "))
    if patient is not None:
        show_patient(patient, False, True)
    press()


def full_details() -> None:
    patient = find_patient(get_int("ID: "))
    if patient is not None:
        show_patient(patient, True, True)
    press()


def sort_patients() -> None:
    if not patients:
        print("No patients.")
        press()
        return
    while True:
        choice = menu("SORT PATIENTS", ["By ID (asc)", "By Name (A-Z)"])
        if choice == 0:
            break
        if choice == 1:
            patients.sort(key=lambda patient: patient.id)
        elif choice == 2:
            patients.sort(
                key=lambda patient: to_lower(
                    f"{patient.f} {patient.m} {patient.l}"
                )
            )
        clear()
        for patient in patients:
            show_patient(patient)
        press()
        clear()


def search_by_name() -> None:
    query = to_lower(get_str("Name part: "))
    for patient in patients:
        if query in to_lower(f"{patient.f} {patient.m} {patient.l}"):
            show_patient(patient)
    press()


def edit_patient(patient: Patient) -> None:
    while True:
        clear()
        show_patient(patient)
        choice = menu("EDIT", ["First", "Middle", "Last", "Age", "Gender"])
        if choice == 0:
            break
        old_value = ""
        duplicate = False
        if choice == 1:
            old_value = patient.f
            patient.f = get_name("New first: ")
        elif choice == 2:
            old_value = patient.m
            patient.m = get_name("New middle: ")
        elif choice == 3:
            old_value = patient.l
            patient.l = get_name("New last: ")
        elif choice == 4:
            old_age = patient.age
            patient.age = get_age()
            if is_duplicate(patient, patient.id):
                print("Duplicate! Revert.")
                patient.age = old_age
                duplicate = True
        elif choice == 5:
            old_value = patient.gender
            patient.gender = get_gender()
            if is_duplicate(patient, patient.id):
                print("Duplicate! Revert.")
                patient.gender = old_value
                duplicate = True

        if choice <= 3 and is_duplicate(patient, patient.id):
            print("Duplicate! Revert.")
            if choice == 1:
                patient.f = old_value
            elif choice == 2:
                patient.m = old_value
            else:
                patient.l = old_value
            duplicate = True
        if not duplicate:
            print("Changed.")
        save()
        press()
        clear()


def delete_patient() -> None:
    patient_id = get_int("ID: ")
    patient = find_patient(patient_id)
    if patient is None:
        print("Not found.")
        press()
        return
    if not yes_no("Really delete?"):
        return
    remove_from_queue(patient_id, True)
    patients.remove(patient)
    print("Deleted.")
    save()
    press()


def manage_history(patient: Patient) -> None:
    if not patient.history:
        print("No history.")
        press()
        return
    for item in patient.history:
        print(f"[{item.id}] {item.act} | {item.res} | {item.date} | {item.doc}")
    history_id = get_int("ID to edit/delete (0 cancel): ", 0)
    if history_id == 0:
        return
    history = next((item for item in patient.history if item.id == history_id), None)
    if history is None:
        print("Invalid.")
        press()
        return
    action = menu("Action", ["Edit", "Delete"])
    if action == 0:
        return
    if action == 2:
        patient.history.remove(history)
    else:
        history.act = get_str("New action: ")
        history.res = get_str("New result: ")
        history.doc = get_str("New doctor: ")
        print("Updated.")
    save()
    press()


def show_stats() -> None:
    total = len(patients)
    active_count = len(active_queue)
    with_history = sum(bool(patient.history) for patient in patients)
    total_history = sum(len(patient.history) for patient in patients)
    with_prescriptions = sum(bool(patient.prescriptions) for patient in patients)
    total_prescriptions = sum(len(patient.prescriptions) for patient in patients)
    actions: dict[str, int] = {}
    results: dict[str, int] = {}
    medicines: dict[str, int] = {}
    for patient in patients:
        for item in patient.history:
            actions[item.act] = actions.get(item.act, 0) + 1
            results[item.res] = results.get(item.res, 0) + 1
        for item in patient.prescriptions:
            medicines[item.med] = medicines.get(item.med, 0) + 1

    print(
        f"\nStatistics:\nTotal patients: {total}\nActive in queue: {active_count}"
        f"\nWith history: {with_history}\nTotal records: {total_history}"
        f"\nWith prescriptions: {with_prescriptions}"
        f"\nTotal prescriptions: {total_prescriptions}"
    )

    def print_top_three(values: dict[str, int]) -> None:
        for name, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:3]:
            print(f"  {name}: {count}")

    print("Top actions:")
    print_top_three(actions)
    print("Top results:")
    print_top_three(results)
    print("Top medicines:")
    print_top_three(medicines)
    press()


def show_active() -> None:
    if not active_queue:
        print("No active patients.")
    else:
        for patient_id, priority in active_queue:
            patient = find_patient(patient_id)
            if patient is not None:
                print(
                    f"ID: {patient.id} | {patient.f} {patient.m} {patient.l} | {priority}"
                )
    press()


def init_users() -> None:
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, "w", encoding="utf-8", newline="") as user_file:
            user_file.write(
                "reception|rec123|receptionist\n"
                "doctor|doc123|doctor\n"
                "pharmacist|phar123|pharmacist\n"
            )


def login() -> bool:
    global current_user
    role_names = ["receptionist", "doctor", "pharmacist"]
    while True:
        clear()
        role_choice = menu("Login", ["Receptionist", "Doctor", "Pharmacist"], "Exit")
        if role_choice == 0:
            return False
        role = role_names[role_choice - 1]
        username = get_str("Username: ")
        password = read_password("Password: ")
        valid = False
        try:
            with open(USER_FILE, encoding="utf-8") as user_file:
                for line in user_file:
                    fields = trim(line).split("|", 2)
                    if (
                        len(fields) == 3
                        and fields[0] == username
                        and fields[1] == password
                        and fields[2] == role
                    ):
                        valid = True
                        break
        except FileNotFoundError:
            pass
        if valid:
            current_user = User(username, password, role)
            print(f"Welcome, {username} ({role})!")
            press()
            clear()
            return True
        print("Invalid.")
        press()


def patient_records() -> None:
    options = ["Show All", "Search by ID"]
    if current_user.role == "pharmacist":
        options.extend(
            ["Show Prescriptions", "Full Details", "Sort Patients", "Search by Name"]
        )
    else:
        options.extend(["Show with History", "Sort Patients", "Search by Name"])

    while True:
        choice = menu("Patient Records", options)
        if choice == 0:
            break
        if choice == 1:
            show_all(current_user.role == "pharmacist")
        elif choice == 2:
            search_by_id()
        elif choice == 3:
            if current_user.role == "pharmacist":
                show_with_prescriptions()
            else:
                show_with_history()
        elif choice == 4:
            if current_user.role == "pharmacist":
                full_details()
            else:
                sort_patients()
        elif choice == 5:
            if current_user.role == "pharmacist":
                sort_patients()
            else:
                search_by_name()
        elif choice == 6 and current_user.role == "pharmacist":
            search_by_name()


def manage_patient() -> None:
    if current_user.role == "pharmacist":
        print("Access denied.")
        press()
        return
    patient = find_patient(get_int("Patient ID: "))
    if patient is None:
        return
    clear()
    show_patient(patient)
    options = ["Edit Info", "Delete Patient", "Remove from Queue"]
    if current_user.role == "doctor":
        options.append("Edit History")
    while True:
        choice = menu("MANAGE PATIENT", options)
        if choice == 0:
            break
        if choice == 1:
            edit_patient(patient)
        elif choice == 2:
            delete_patient()
        elif choice == 3:
            remove_from_queue(patient.id)
        elif choice == 4:
            manage_history(patient)
        if choice != 2:
            clear()
            show_patient(patient)
        else:
            break


def dashboard() -> None:
    if current_user.role == "receptionist":
        options = ["New Patient", "Active Queue", "Patient Records", "Manage Patient", "Statistics"]
    elif current_user.role == "doctor":
        options = ["Active Queue", "Serve Next", "Patient Records", "Manage Patient", "Statistics"]
    else:
        options = ["Patient Records", "Statistics"]

    while True:
        choice = menu(f"MEDSYS // {current_user.role}", options, "Logout")
        if choice == 0:
            break
        if current_user.role == "receptionist":
            if choice == 1:
                register_patient()
            elif choice == 2:
                show_active()
            elif choice == 3:
                patient_records()
            elif choice == 4:
                manage_patient()
            elif choice == 5:
                show_stats()
        elif current_user.role == "doctor":
            if choice == 1:
                show_active()
            elif choice == 2:
                serve()
            elif choice == 3:
                patient_records()
            elif choice == 4:
                manage_patient()
            elif choice == 5:
                show_stats()
        else:
            if choice == 1:
                patient_records()
            elif choice == 2:
                show_stats()


def main() -> int:
    load()
    init_users()
    try:
        while login():
            dashboard()
    except EOFError:
        print("\nInput ended.")
    finally:
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
