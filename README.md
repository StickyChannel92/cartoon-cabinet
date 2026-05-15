# cartoon-cabinet
a locally-hosted website to organize cartoons

# to use
1. unzip the client to wherever you want
2. edit cartoon-server.py and change the directories to your liking
3. install ffmpeg via `sudo apt install ffmpeg`
4. cd to the directory
5. run the following commands
```
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements
python3 cartoon-server.py
```
6. open http://localhost:7777 in your browser

# to make a desktop shortcut:
1. Create `Cartoon Cabinet.desktop` with the following text (change the bash commands according to your client directory)
```
#!/usr/bin/env xdg-open
[Desktop Entry]
Version=1.0
Type=Application
Name=Cartoon Server
Comment=Run cartoon_server.py and open localhost
Terminal=true
Exec=bash -c 'source /home/username/Documents/cartoons/venv/bin/activate && python /home/username/Documents/cartoons/cartoon_server.py & sleep 2 && xdg-open http://localhost:7777/ && wait'
Icon=utilities-terminal
Categories=Entertainment;Cartoons;Movies and TV;
```
2. double click on it and mark as Trusted
3. simply access your client by opening this desktop entry

# documentation
* TV shows use the txt method of displaying metadata, via `metadata.txt` in the TV show's directory
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
* disclaimers are in `disclaimer.txt` with a one-line warning. Can add more via `disclaimer2.txt` and `disclaimern.txt` etc
* seasons are divided into folders named `Season 1`, `Season 2` and `Season n` etc
* tv shows that have a `Specials` folder will have their contents detected accordingly
* similar to `Specials`, `English Screening Demo` folders will be scanned if applicable
* "multishows" are a cartoon with mini-series included (e.g. True and the Rainbow Kingdom has a main series with its own specials, and 5 other mini-series.
* podcasts are the only cartoons to have an audio format detection (unless they are videos and you put them in a Specials folder)
* `fanart.png`, and `thumb.png` will be used for the cartoon's header and poster
* for movies, the video immediately opens up. if an image exists with the same name as the video file, the client will use that on the movie menu (e.g. `Kung Fu Panda.mkv` will use `Kung Fu Panda.png` as the cover art)
* subtitles are automatically detected either by the media container, or an SRT file
* the misc directories (MISC_DIRS) will list all of their contents at once, useful for a theatrical shorts or indie animation folder
* you can specify which directories will be excluded from being scanned, in SKIP_DIRS
* the host can be changed on the last line of the python script.
```
app.run(host='0.0.0.0', port=7777, debug=False, threaded=True)
```
