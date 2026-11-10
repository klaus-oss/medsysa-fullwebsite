# MEDSYS Hospital Queue

Python version of the hospital queue and patient-record system.

## Run the command-line app

```bash
python3 medsys.py
```

## Run the web interface

```bash
python3 medsys_web.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The web interface uses only the Python standard library and shares patient, queue, and account data with the command-line app. Stop the server with `Ctrl+C`.

The web server binds to `127.0.0.1` so it is only available on the local machine. Account passwords are stored in plaintext in `users.txt` by the existing application; use this setup only for local development and replace the default credentials before handling real patient information.

Both interfaces read and write patient records and the active queue in `medsys.txt`, and read role credentials from `users.txt`. If `users.txt` does not exist, the application creates it with these default accounts:

| Role | Username | Password |
| --- | --- | --- |
| Receptionist | `reception` | `rec123` |
| Doctor | `doctor` | `doc123` |
| Pharmacist | `pharmacist` | `phar123` |
