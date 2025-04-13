# GDSongExtractor

[![Donate](https://img.shields.io/badge/Donate-Ko--fi-blue.svg)](https://ko-fi.com/MalikHw47)

***NO APP ICON FOR NOW LOL***...

GDSongExtractor is a desktop application that helps you easily find, identify, and manage the custom songs downloaded by Geometry Dash. It automatically scans your Geometry Dash installation folder, fetches song metadata (like title, artist, and genre) from Newgrounds using the song ID, and allows you to copy the songs with proper ID3 tags to your music library.

![Screenshot Placeholder](/screenshots/placeholder.png)

## Features

* **Automatic GD Folder Detection:** Attempts to automatically locate your Geometry Dash songs folder on Windows, Linux (Wine/Proton), and macOS.
* **Metadata Fetching:** Scrapes Newgrounds.com to retrieve accurate Title, Artist, and Genre information for each song based on its filename (ID). Includes robust fallback mechanisms if direct scraping fails.
* **ID3 Tagging:** Automatically applies the fetched Title, Artist, and Genre metadata as ID3 tags to the copied MP3 files.
* **Graphical User Interface:** Easy-to-use interface built with PyQt6.
* **Song Listing & Filtering:** Displays found songs in a sortable list and allows filtering by artist or title.
* **Selective Copying:** Choose which songs you want to copy to your music folder.
* **Custom Music Folder:** Allows you to specify a custom destination folder for copied songs.
* **Cross-Platform:** Executables available for Windows, Linux, and macOS (check releases!).
* **Customizable Banner:** Supports a custom 16:9 banner image placed in a `resources` folder next to the executable.

## Installation (Using Pre-built Executable)

1.  **Go to the Releases Page:** Navigate to the [Releases](https://github.com/MalikHw/GDSongExtractor/releases) section
2.  **Download the Latest Version:** Find the latest release and download the appropriate executable file for your operating system (`.exe` for Windows, an installation script for Linux).
3.  **Run the setup:** Whether you're on Windows or Linux, just run the setup file (`install.sh` for linux and `gdsongextractor-*-windows.exe` for windows.

That's it! No Python installation or dependencies needed for end-users.

## Usage

1.  **Run the application:** Double-click the `GDSongExtractor.exe` file (Windows) or run the executable from your terminal (`./GDSongExtractor` on Linux/macOS).
2.  **Verify Paths:** Check the detected "Geometry Dash Folder" and "Music Folder" paths. If the Music folder is incorrect or you want a different destination, click "Change Music Folder".
3.  **Scan Songs:** Click the "Scan Songs" button. The application will scan the GD folder for MP3 files, fetch metadata from Newgrounds (this may take some time), and populate the "Available Songs" list. Progress is shown in the progress bar and log window.
4.  **Select Songs:** Select the songs you wish to copy from the list. You can use Ctrl/Cmd+Click for multiple individual selections, Shift+Click for ranges, or the "Select All" / "Select None" buttons.
5.  **Filter (Optional):** Use the search bar to filter the list by song title or artist.
6.  **Copy Songs:** Click the "Copy Selected Songs" button. The selected songs will be copied to your designated Music folder with proper filenames (`Artist - Title.mp3`) and ID3 tags.

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue on GitHub. If you'd like to contribute code, please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. *(Remember to create the LICENSE file)*

## Author

* **MalikHw47** (loner lol)

## Support

If you find this tool useful, consider supporting me:

[![Donate](https://img.shields.io/badge/Donate-Ko--fi-blue.svg)](https://ko-fi.com/MalikHw47)
