import os
import re
import sys
import shutil
import requests
import platform
import webbrowser
import random
import time
from bs4 import BeautifulSoup
import mutagen
from mutagen.easyid3 import EasyID3
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout,
                           QWidget, QPushButton, QProgressBar, QTextEdit, QListWidget,
                           QListWidgetItem, QCheckBox, QFileDialog, QGroupBox, QSplitter,
                           QLineEdit, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont


class FetchWorker(QThread):
    """Worker thread for fetching metadata"""
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished_with_songs = pyqtSignal(list)

    def __init__(self, song_files, parent=None):
        super().__init__(parent)
        self.song_files = song_files
        # List of user agents to rotate
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
        ]

    def run(self):
        songs = []
        total = len(self.song_files)

        for i, (song_id, filename) in enumerate(self.song_files):
            metadata = self.fetch_song_metadata(song_id, filename)
            if metadata:
                 songs.append(metadata)

            # Update progress
            progress = int((i + 1) / total * 100)
            self.progress_updated.emit(progress)

            # Variable delay to avoid rate limiting and detection
            time.sleep(random.uniform(1.0, 2.5))

        self.finished_with_songs.emit(songs)

    def fetch_song_metadata(self, song_id, filename):
        """Fetch song metadata from Newgrounds"""
        url = f"https://www.newgrounds.com/audio/listen/{song_id}"

        try:
            self.log_updated.emit(f"Fetching metadata for song ID {song_id}...")

            # Use a rotating user agent
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'TE': 'Trailers'
            }

            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                self.log_updated.emit(f"Failed to fetch metadata for song ID {song_id} (Status code: {response.status_code})")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check if we're being redirected to login
            if "Log in / Sign Up" in soup.text or soup.select_one(".login-header"):
                # Try a different approach - parse from the page title which often has "Title by Artist"
                page_title = soup.title.string if soup.title else ""
                artist = "Unknown Artist"
                title = f"Unknown Song {song_id}"

                # Title format is usually: "Song Title by Artist - Audio"
                title_match = re.search(r'(.+) by (.+) - Audio', page_title)
                if title_match:
                    title = title_match.group(1).strip()
                    artist = title_match.group(2).strip()
                    self.log_updated.emit(f"Using title extraction: {artist} - {title}")
                else:
                    # Try with the URL directly - if the song exists, we should at least get the ID
                    # Improved fallback extraction using the song ID in the filename
                    self.log_updated.emit(f"Using fallback extraction for song {song_id}")
                    title = f"Song {song_id}"

                    # Try extracting from filename if it contains artist info
                    filename_without_ext = os.path.splitext(filename)[0]
                    if '-' in filename_without_ext:
                        parts = filename_without_ext.split('-', 1)
                        if len(parts) == 2:
                             artist = parts[0].strip()
                             title = parts[1].strip()
            else:
                # Extract title using multiple approaches
                title = None

                # Try different selectors for title
                title_selectors = [
                    'h2.pod-header',
                    'h2.detail-title',
                    'h2.item-name',
                    '.pod-head h2',
                    '.audio-info h2',
                    'div.column-wide h2'
                ]

                for selector in title_selectors:
                    title_element = soup.select_one(selector)
                    if title_element and title_element.text.strip():
                        title = title_element.text.strip()
                        break

                # If still no title, try page title approach
                if not title:
                    page_title = soup.title.string if soup.title else ""
                    title_match = re.search(r'(.+) by .+ - Audio', page_title)
                    if title_match:
                        title = title_match.group(1).strip()

                # Fallback
                if not title:
                    title = f"Song {song_id}"

                # Extract artist using a more targeted approach
                artist = None

                # Look for artist in author sections
                artist_selectors = [
                    '.item-details a.item-author',
                    '.byline a',
                    'a.item-author',
                    '.pod-body .user-link',
                    'span.author a'
                ]

                for selector in artist_selectors:
                    artist_elements = soup.select(selector)
                    for element in artist_elements:
                        text = element.text.strip()
                        # Skip if it's "Log in" or empty
                        if text and "Log in" not in text and len(text) > 1:
                            artist = text
                            break
                    if artist:
                        break

                # Fallback for artist - try from page title
                if not artist or "Log in" in artist:
                    page_title = soup.title.string if soup.title else ""
                    artist_match = re.search(r'.+ by (.+) - Audio', page_title)
                    if artist_match:
                         artist = artist_match.group(1).strip()
                    else:
                        artist = "Unknown Artist"

            # Extract genre
            genre_element = soup.select_one('dd.detail-genre')
            genre = genre_element.text.strip() if genre_element and genre_element.text.strip() else "Electronic"

            # Post-processing: Clean up artist name to ensure it's not "Log in"
            if not artist or "Log in" in artist or len(artist) < 2:
                artist = "Unknown Artist"

            self.log_updated.emit(f"Found: {artist} - {title}")

            return {
                'id': song_id,
                'title': title,
                'artist': artist,
                'genre': genre,
                'filename': filename,
                'url': url
            }

        except Exception as e:
            self.log_updated.emit(f"Error fetching metadata for song ID {song_id}: {e}")
            return None


class CopyWorker(QThread):
    """Worker thread for copying songs"""
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, songs_to_copy, gd_path, music_path, parent=None):
        super().__init__(parent)
        self.songs_to_copy = songs_to_copy
        self.gd_path = gd_path
        self.music_path = music_path

    def run(self):
        total = len(self.songs_to_copy)
        if total == 0:
            self.log_updated.emit("No songs selected for copying.")
            self.finished.emit()
            return

        self.log_updated.emit(f"Copying {total} songs to {self.music_path}...")

        for i, song in enumerate(self.songs_to_copy):
            source_path = self.gd_path / song['filename']

            # Create safe filename
            safe_filename = f"{song['artist']} - {song['title']}.mp3"
            safe_filename = re.sub(r'[\\/*?:"<>|]', '_', safe_filename)  # Remove illegal characters

            destination_path = self.music_path / safe_filename

            # Copy the file
            try:
                shutil.copy2(source_path, destination_path)

                # Add metadata
                try:
                    audio = EasyID3(destination_path)
                except mutagen.id3.ID3NoHeaderError:
                    # If there's no ID3 tag, add one
                    audio = mutagen.File(destination_path, easy=True)
                    audio.add_tags()

                audio['title'] = song['title']
                audio['artist'] = song['artist']
                audio['genre'] = song['genre']
                audio.save()

                self.log_updated.emit(f"Copied: {song['artist']} - {song['title']}")
            except Exception as e:
                self.log_updated.emit(f"Error copying {song['filename']}: {e}")

            # Update progress
            progress = int((i + 1) / total * 100)
            self.progress_updated.emit(progress)

            # Small delay
            time.sleep(0.1)

        self.log_updated.emit(f"Successfully copied {total} songs to {self.music_path}")
        self.finished.emit()


class GeometryDashSongManager(QMainWindow):
    def __init__(self):
        super().__init__()

        # Setup window properties
        self.setWindowTitle("GDSongExtractor v1.0 by MalikHw47")
        self.setMinimumSize(900, 650)

        # Initialize variables - Set gd_path and music_path to None initially
        self.songs = []
        self.gd_path = None
        self.music_path = None

        # Create UI FIRST
        self.init_ui()

        # Now get paths AFTER UI (and log_text) exists
        self.gd_path = self.get_gd_songs_path()
        self.music_path = self.get_music_folder_path()

        # Update labels *after* paths are determined and UI exists
        self.gd_path_label.setText(f"Geometry Dash Folder: {self.gd_path if self.gd_path else 'Not Found'}")
        self.music_path_label.setText(f"Music Folder: {self.music_path if self.music_path else 'Not Found'}")

        # Log initial status *after* UI exists
        self.log("GDSongExtractor v1.0 started")
        if not self.gd_path:
            self.log("ERROR: Couldn't find Geometry Dash folder")
            self.scan_btn.setEnabled(False)
        if not self.music_path:
            self.log("ERROR: Couldn't find default Music folder (but created one if possible)")

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout()

        # Main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        main_layout.addWidget(content_widget, 1)

        # Paths info
        paths_group = QGroupBox("Folder Paths")
        paths_layout = QVBoxLayout(paths_group)

        # Initialize labels with placeholder text
        self.gd_path_label = QLabel("Geometry Dash Folder: Initializing...")
        self.music_path_label = QLabel("Music Folder: Initializing...")

        paths_layout.addWidget(self.gd_path_label)
        paths_layout.addWidget(self.music_path_label)

        # Settings button
        settings_btn = QPushButton("Change Music Folder")
        settings_btn.clicked.connect(self.change_music_folder)
        paths_layout.addWidget(settings_btn)

        content_layout.addWidget(paths_group)

        # Splitter for log and song list
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Log area
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        # Song list area with search
        song_list_group = QGroupBox("Available Songs")
        song_list_layout = QVBoxLayout(song_list_group)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter song title or artist...")
        self.search_input.textChanged.connect(self.filter_songs)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self.filter_songs)

        clear_search_button = QPushButton("Clear")
        clear_search_button.clicked.connect(self.clear_search)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(search_button)
        search_layout.addWidget(clear_search_button)

        song_list_layout.addLayout(search_layout)

        # Add a separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        song_list_layout.addWidget(line)

        # Song list
        self.song_list = QListWidget()
        self.song_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        song_list_layout.addWidget(self.song_list)

        # Selection buttons
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_songs)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_songs)

        select_buttons_layout = QHBoxLayout()
        select_buttons_layout.addWidget(select_all_btn)
        select_buttons_layout.addWidget(select_none_btn)
        song_list_layout.addLayout(select_buttons_layout)

        # Add widgets to splitter
        splitter.addWidget(log_group)
        splitter.addWidget(song_list_group)
        # Adjust initial splitter sizes dynamically or use defaults
        initial_width = self.width() if self.width() > 0 else 900
        splitter.setSizes([int(initial_width * 0.4), int(initial_width * 0.6)])

        content_layout.addWidget(splitter, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        content_layout.addWidget(self.progress_bar)

        # Action buttons
        button_layout = QHBoxLayout()

        self.scan_btn = QPushButton("Scan Songs")
        self.scan_btn.clicked.connect(self.scan_songs)

        self.copy_btn = QPushButton("Copy Selected Songs")
        self.copy_btn.clicked.connect(self.copy_songs)
        self.copy_btn.setEnabled(False)

        donate_btn = QPushButton("Donate")
        donate_btn.clicked.connect(self.open_donation)
        donate_btn.setStyleSheet("background-color: #29abe0; color: white;")

        button_layout.addWidget(self.scan_btn)
        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(donate_btn)

        content_layout.addLayout(button_layout)

        # Set main layout
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def log(self, message):
        """Add a message to the log"""
        # Check if log_text exists before trying to append
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.append(message)
            # Scroll to bottom
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
             # Fallback if log is called too early (shouldn't happen now, but safe)
             print(f"LOG (early): {message}")

    def get_gd_songs_path(self):
        """Get the path to Geometry Dash songs folder based on OS"""
        gd_path = None
        try:
            if platform.system() == "Windows":
                 username = os.environ.get('USERNAME') or os.environ.get('USER')
                 # Use LOCALAPPDATA environment variable for robustness
                 local_app_data = os.environ.get('LOCALAPPDATA')
                 if local_app_data:
                     gd_path = Path(local_app_data) / "GeometryDash"
                 elif username: # Fallback to constructed path
                     gd_path = Path(f"C:/Users/{username}/AppData/Local/GeometryDash")

            elif platform.system() == "Linux":
                username = os.environ.get('USER')
                # Common Wine path, check if ~/.wine exists first
                wine_path = Path.home() / ".wine" # Use Path.home()
                if wine_path.exists() and username:
                    # Check for potential Proton path first if Steam directory exists
                    steam_path = Path.home() / ".steam" / "steam" / "steamapps" / "compatdata" / "322170" / "pfx"
                    proton_gd_path = None
                    if steam_path.exists():
                         # Standard Proton user might be steamuser
                         steam_user_path = steam_path / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "GeometryDash"
                         if steam_user_path.exists():
                              proton_gd_path = steam_user_path
                         else:
                              # Fallback to current username within proton prefix (less common)
                              user_proton_path = steam_path / "drive_c" / "users" / username / "AppData" / "Local" / "GeometryDash"
                              if user_proton_path.exists():
                                   proton_gd_path = user_proton_path

                    if proton_gd_path:
                         gd_path = proton_gd_path
                         self.log("Detected Steam Play (Proton) Geometry Dash path.")
                    else:
                        # Fallback to standard Wine path
                        wine_gd_path = wine_path / f"drive_c/users/{username}/AppData/Local/GeometryDash"
                        if wine_gd_path.exists():
                             gd_path = wine_gd_path
                             self.log("Detected standard Wine Geometry Dash path.")

            elif platform.system() == "Darwin": # macOS
                 username = os.environ.get('USER')
                 if username:
                     # Default path for GD on macOS
                     mac_path = Path.home() / "Library" / "Application Support" / "GeometryDash"
                     if mac_path.exists():
                          gd_path = mac_path

            else:
                self.log(f"Unsupported operating system: {platform.system()}")
                return None

            if gd_path and not gd_path.exists():
                 self.log(f"Potential Geometry Dash path found but does not exist: {gd_path}")
                 return None
            elif not gd_path:
                 self.log("Could not determine Geometry Dash path.")
                 return None

        except Exception as e:
            self.log(f"Error determining Geometry Dash path: {e}")
            return None

        self.log(f"Found Geometry Dash path: {gd_path}")
        return gd_path

    def get_music_folder_path(self):
        """Get the path to the user's Music folder"""
        music_path = None
        try:
            if platform.system() == "Windows":
                # Use SHGetKnownFolderPath for robustness (requires ctypes/comtypes, fallback if unavailable)
                try:
                    import ctypes
                    from ctypes import wintypes, windll

                    FOLDERID_Music = ctypes.GUID('{4BD8D571-6D19-48D3-BE97-422220080E43}')
                    SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath
                    SHGetKnownFolderPath.argtypes = [
                        ctypes.POINTER(ctypes.GUID), wintypes.DWORD,
                        wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)
                    ]
                    SHGetKnownFolderPath.restype = ctypes.HRESULT

                    path_ptr = wintypes.LPWSTR()
                    if SHGetKnownFolderPath(ctypes.byref(FOLDERID_Music), 0, None, ctypes.byref(path_ptr)) == 0: # S_OK
                         music_path = Path(path_ptr.value)
                         ctypes.windll.ole32.CoTaskMemFree(path_ptr) # Free memory
                    else: # Fallback if API call fails
                         raise OSError("SHGetKnownFolderPath failed")

                except Exception:
                     # Fallback if ctypes fails or on minimal systems
                     username = os.environ.get('USERNAME') or os.environ.get('USER')
                     if username:
                        user_profile = os.environ.get('USERPROFILE')
                        if user_profile:
                             music_path = Path(user_profile) / "Music"
                        else: # Absolute fallback
                             music_path = Path(f"C:/Users/{username}/Music")

            elif platform.system() == "Linux":
                username = os.environ.get('USER')
                if username:
                     # Check XDG user directory config first
                     try:
                         # Use subprocess to call xdg-user-dir for reliability
                         result = subprocess.run(['xdg-user-dir', 'MUSIC'], capture_output=True, text=True, check=True)
                         xdg_music_dir = result.stdout.strip()
                         if xdg_music_dir and Path(xdg_music_dir).is_dir():
                             music_path = Path(xdg_music_dir)
                         else: # Fallback to default if xdg-user-dir gives bad path or isn't set
                             music_path = Path.home() / "Music"
                     except (FileNotFoundError, subprocess.CalledProcessError): # If xdg-user-dir command fails
                         music_path = Path.home() / "Music"

            elif platform.system() == "Darwin": # macOS
                music_path = Path.home() / "Music"

            else:
                 self.log(f"Cannot determine Music folder for OS: {platform.system()}")
                 return None

            # Create the directory if it doesn't exist and we found a path
            if music_path and not music_path.exists():
                try:
                    music_path.mkdir(parents=True, exist_ok=True)
                    self.log(f"Created Music folder: {music_path}")
                except Exception as e:
                     self.log(f"Error creating Music folder {music_path}: {e}")
                     return None # Failed to create

        except Exception as e:
             self.log(f"Error determining Music folder path: {e}")
             return None

        if music_path:
             self.log(f"Using Music folder: {music_path}")
        else:
             self.log("Could not determine Music folder path.")

        return music_path

    def change_music_folder(self):
        """Open dialog to change music folder destination"""
        # Start Browse from the current music path if it exists, otherwise home dir
        start_dir = str(self.music_path) if self.music_path and self.music_path.exists() else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder", start_dir)
        if folder:
            new_path = Path(folder)
            # Basic check if the selected folder is writable
            if os.access(str(new_path), os.W_OK):
                 self.music_path = new_path
                 self.music_path_label.setText(f"Music Folder: {self.music_path}")
                 self.log(f"Music folder changed to: {self.music_path}")
            else:
                 self.log(f"ERROR: Cannot write to selected folder: {new_path}")
                 # Optionally show a message box to the user here using QMessageBox

    def scan_songs(self):
        """Scan for song files and fetch metadata"""
        if not self.gd_path: # Add check here
            self.log("ERROR: Geometry Dash path not set or found. Cannot scan.")
            return

        self.log("Scanning for Geometry Dash songs...")
        self.progress_bar.setValue(0)
        self.song_list.clear()
        self.songs = []
        self.copy_btn.setEnabled(False)
        self.search_input.clear()

        # Get song files
        song_files = self.get_song_files()

        if not song_files:
            self.log("No suitable Geometry Dash song files found.")
            # Re-enable scan button if scan failed early
            self.scan_btn.setEnabled(True if self.gd_path else False)
            return

        self.log(f"Found {len(song_files)} song files. Fetching metadata...")

        # Disable scan button during operation
        self.scan_btn.setEnabled(False)

        # Start fetch worker
        self.fetch_worker = FetchWorker(song_files)
        self.fetch_worker.progress_updated.connect(self.progress_bar.setValue)
        self.fetch_worker.log_updated.connect(self.log)
        self.fetch_worker.finished_with_songs.connect(self.update_song_list)
        self.fetch_worker.start()

    def get_song_files(self):
        """Get all MP3 files from Geometry Dash folder, filtering out specified patterns"""
        song_files = []
        if not self.gd_path or not self.gd_path.exists():
             self.log("Geometry Dash path is invalid, cannot get song files.")
             return song_files

        try:
             for file in os.listdir(self.gd_path):
                 # Ignore .ogg files and files starting with 's'
                 if file.lower().startswith('s'):
                     continue

                 if file.lower().endswith('.mp3'):
                     try:
                         # Extract song ID from filename (like 1260.mp3)
                         song_id_str = file.split('.')[0]
                         # Ensure it's purely numeric before converting
                         if song_id_str.isdigit():
                             song_id = int(song_id_str)
                             song_files.append((song_id, file))
                         else:
                              self.log(f"Skipping {file} - filename does not start with a numeric ID")
                     except ValueError:
                         self.log(f"Skipping {file} - not a valid Newgrounds song file format (numeric ID expected)")
                     except IndexError:
                         self.log(f"Skipping {file} - unexpected filename format")

        except FileNotFoundError:
             self.log(f"ERROR: Geometry Dash directory not found at {self.gd_path}")
        except Exception as e:
             self.log(f"Error reading Geometry Dash directory {self.gd_path}: {e}")

        return song_files

    def update_song_list(self, songs):
        """Update the song list with fetched songs"""
        # Sort songs alphabetically by artist, then title
        self.songs = sorted(songs, key=lambda s: (s['artist'].lower(), s['title'].lower()))

        if not self.songs: # Check after sorting
            self.log("No songs found or all metadata fetches failed.")
            self.scan_btn.setEnabled(True if self.gd_path else False) # Re-enable scan button if GD path valid
            return

        # Populate song list
        self.populate_song_list(self.songs) # Use the sorted list

        self.log(f"Found and sorted {len(self.songs)} songs with metadata.")
        self.copy_btn.setEnabled(True)
        self.scan_btn.setEnabled(True if self.gd_path else False) # Re-enable scan button if GD path valid

    def populate_song_list(self, songs):
        """Populate the song list widget with the given songs"""
        self.song_list.clear()

        for song in songs:
            item = QListWidgetItem(f"{song['artist']} - {song['title']}")
            item.setData(Qt.ItemDataRole.UserRole, song)
            # Add tooltip with more info
            tooltip_text = f"ID: {song['id']}\nGenre: {song['genre']}\nFilename: {song['filename']}"
            item.setToolTip(tooltip_text)
            self.song_list.addItem(item)

    def filter_songs(self):
        """Filter songs based on search input"""
        search_text = self.search_input.text().lower().strip()

        if not search_text:
            # If search is empty, show all songs
            self.populate_song_list(self.songs)
            return

        # Filter songs where title or artist contains the search text
        filtered_songs = [
            song for song in self.songs
            if search_text in song['title'].lower() or search_text in song['artist'].lower()
        ]

        self.populate_song_list(filtered_songs)
        self.log(f"Found {len(filtered_songs)} songs matching '{search_text}'")

    def clear_search(self):
        """Clear search and show all songs"""
        self.search_input.clear()
        self.populate_song_list(self.songs)

    def select_all_songs(self):
        """Select all songs in the list"""
        # Check if the list actually contains items before selecting
        if self.song_list.count() > 0:
             self.song_list.selectAll()

    def select_no_songs(self):
        """Deselect all songs in the list"""
        self.song_list.clearSelection()

    def copy_songs(self):
        """Copy selected songs to Music folder"""
        if not self.music_path: # Add check here
            self.log("ERROR: Music path not set. Cannot copy songs.")
            return
        if not self.gd_path: # Add check here for safety
            self.log("ERROR: Geometry Dash path not set. Cannot copy songs.")
            return


        selected_items = self.song_list.selectedItems()

        if not selected_items:
            self.log("No songs selected. Please select songs to copy.")
            return

        songs_to_copy = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        # Disable buttons during operation
        self.scan_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        # Start copy worker
        self.copy_worker = CopyWorker(songs_to_copy, self.gd_path, self.music_path)
        self.copy_worker.progress_updated.connect(self.progress_bar.setValue)
        self.copy_worker.log_updated.connect(self.log)
        self.copy_worker.finished.connect(self.copy_finished)
        self.copy_worker.start()

    def copy_finished(self):
        """Handle copy operation finished"""
        # Re-enable buttons, checking path validity
        self.scan_btn.setEnabled(True if self.gd_path else False)
        self.copy_btn.setEnabled(True if self.songs else False) # Only enable copy if there are songs loaded

    def open_donation(self):
        """Open donation page"""
        self.log("Opening donation page...")
        webbrowser.open("https://ko-fi.com/MalikHw47")


def main():
    # Required for xdg-user-dir call on Linux
    import subprocess

    # Set High DPI scaling based on Qt version recommendations
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    # Apply a style if desired (optional)
    # app.setStyle('Fusion')
    window = GeometryDashSongManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # Add import subprocess inside main or globally if used elsewhere
    import subprocess # Added import here for get_music_folder_path
    main()
