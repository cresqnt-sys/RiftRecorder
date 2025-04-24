# RiftRecorder

RiftRecorder is an application made for recording paths for the macro RiftScope.

## Features

*   **Record:** Capture keyboard presses/releases and mouse movements/clicks/scrolls.
*   **Playback:** Replay recorded actions at adjustable speeds.
*   **Save/Load:** Store recordings to JSON files and load them back later.
*   **Countdown:** Add a delay before recording or playback starts.
*   **Speed Control:** Play back recordings faster or slower than the original speed.
*   **Essential Moves Filter:** Optionally simplify mouse playback by removing intermediate move events, keeping only those just before clicks/scrolls.
*   **Stop Key:** Use the `Esc` key as a global hotkey to stop recording or playback.

## Installation

1.  **Clone the repository (or download the files):**
    ```bash
    git clone https://github.com/cresqnt-sys/RiftScope # Or download ZIP
    cd RiftRecorder
    ```
2.  **Install dependencies:**
    RiftRecorder requires Python 3 and the following libraries:
    *   `PyQt6`: For the graphical user interface.
    *   `keyboard`: For capturing and replaying keyboard events.
    *   `mouse`: For capturing and replaying mouse events.

    You can install them using pip:
    ```bash
    pip install PyQt6 keyboard mouse
    ```
    *Note:* The `keyboard` and `mouse` libraries often require administrator privileges to hook into system-wide input events, especially on Windows and macOS.

## Usage

1.  **Run the application:**
    ```bash
    python main.py
    ```
    *You might need to run this command with administrator privileges (e.g., using `sudo python main.py` on Linux/macOS or "Run as administrator" on Windows) for the recording/playback to work correctly.* 

2.  **Using the UI:**
    *   Adjust **Countdown** and **Playback Speed** settings as needed.
    *   Check **Only Essential Moves** if you want simplified mouse playback.
    *   Click **Record** to start capturing actions (after the countdown).
    *   Perform the desired keyboard/mouse actions.
    *   Press **Stop** or the `Esc` key to finish recording.
    *   Click **Play** to replay the last recording or a loaded one.
    *   Press **Stop** or the `Esc` key to interrupt playback.
    *   Click **Save** to save the current recording to a `.json` file.
    *   Click **Load** to load a recording from a `.json` file.

## License

This project is licensed under the [GNU Affero General Public License v3.0] - see the LICENSE file for details.

## Credits

*   **Creator:** noteab
*   **Contributor:** cresqnt_
