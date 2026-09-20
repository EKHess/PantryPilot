# PantryPilot

A locally run Flask app to manage grocery inventory in your house. Uses SQLite3 for the database. 

## Upcoming Feature Ideas

- A "notes" field for item entries
- Filtered search by:
    - category
    - store
    - inactive or active state

## Installation
There is no real installation for this project aside from simply cloning the repo to a location on your computer using `git clone`, or downloading the source code ZIP file to a folder of your choosing.

## Run locally

Requires Python 3 and `pip` and packages detailed in `requirments.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

Alternatively, if you're a `conda` user like me, you can create a safe, separate virtual environment for this project using:

```bash
$ conda env create -f environment.yml
```

> You may need to edit the path of the `prefix` in the YAML file to the location where you'd like the Conda cirtual environment to be stored.

Then actiavte it using:

```bash
$ conda activate PantryPilot
(PantryPilot) $
```

Then you can launch the app using:

```bash
(PantryPilot) $ python app.py
```

Open <http://127.0.0.1:8888> in a browser. Application data is stored locally in `data/finance.db`.

If you have other apps running on this port already, you can change the port on start-up using:

```bash
(PantryPilot) $ python app.py --port 1234
```

where `1234` is your desired port. Generally any 4-digit port number is allowed, so long as it is not already in use.

> [!NOTE]
> The use of the `python` or `python3` command depends entirely on your installation of Anaconda, Python and your OS. Double check which to use for your specific setup before launching.

