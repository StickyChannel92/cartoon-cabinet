# cartoon-cabinet
a locally-hosted website to organize cartoons.

# to use
1. unzip the client to wherever you want.
2. edit cartoon-server.py and change the directories to your liking.
3. install ffmpeg via `sudo apt install ffmpeg`
4. cd to the directory
5. run the following commands.
```
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements
python3 cartoon-server.py
```
6. open http://localhost:7777 in your browser

# documentation
TV shows use the txt method of displaying metadata, via `metadata.txt` in the TV show's directory.
```
TITLE: English Title
ENGLISH: Translated English Title
LOCATION: en
SOURCE: Service1
SOURCE2: Service2
SOURCEn: Servicen
DESCRIPTION: A brief description of the show content.
DATE: 20xx
```
disclaimers are in `disclaimer.txt` with a one-line warning. Can add more via `disclaimer2.txt` and so on.
