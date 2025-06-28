# Dashlane CLI GUI

A simple graphical user interface (GUI) for interacting with the Dashlane Command Line Interface (CLI). This tool aims to make it easier to search for and retrieve your Dashlane passwords and logins without needing to constantly use the command line.

---

## Features

* **Search and Filter:** Quickly find your Dashlane items by title or login.
* **View Details:** Access a dedicated window to view selected item details, including the password.
* **Secure Copy:** Easily copy passwords, logins, or both to your clipboard.
* **Automatic Clipboard Clearing:** Passwords copied to the clipboard are automatically cleared after a configurable delay for enhanced security.
* **Password Visibility Toggle:** Show or hide passwords within the details window.
* **Search History:** Keeps a short history of your recent searches for quick re-selection.
* **Customizable Settings:** Adjust the clipboard clear delay and clear your search history directly from the GUI.

---

## Requirements

To use this application, you **must** have:

* **Dashlane CLI (dcli)** installed and configured on your system. You can download it from the [official Dashlane CLI page](https://www.dashlane.com/features/command-line-interface).
* **An active Dashlane session** with `dcli` logged in. The GUI relies on `dcli` to fetch your vault data.

---

## Installation & Usage

There are two main ways to use this application:

### 1. Using the Executable (Recommended for most users)

The easiest way to use the Dashlane CLI GUI is by downloading the pre-built executable.

1.  Go to the [**Releases** page](https://github.com/Sanaker/dashlane-gui/releases) of this GitHub repository.
2.  Download the `Dashlane CLI GUI.exe` file from the `v0.1.0-alpha` release (or the latest release available).
3.  Extract the contents of the downloaded `.zip` file (if applicable).
4.  **Ensure `bilde.png` and `config.ini` are located in the same directory as the `Dashlane CLI GUI.exe` executable.** If you downloaded a `.zip` from the release, these files should already be packaged together correctly.
5.  Double-click `Dashlane CLI GUI.exe` to run the application.

### 2. Running from Source

If you prefer to run the application directly from the Python source code:

1.  **Clone this repository:**
    ```bash
    git clone [https://github.com/Sanaker/dashlane-gui.git]
    cd dashlane-gui
    ```
2.  **Install Python (if you don't have it):** This application requires Python 3.x.
3.  **Install dependencies:
4.  `PyInstaller` (For building the application)
5.  **Run the application:**
    ```bash
    python main.py
    ```

---

## Development & Building the Executable (for Contributors)

If you're a developer and want to build the executable yourself or contribute to the project:

### Dependencies

* Python 3.x
* `tkinter` (usually comes with Python)
* `PyInstaller` (for building executables: `pip install pyinstaller`)

### Building with PyInstaller

To create a standalone executable (e.g., `.exe` for Windows), use PyInstaller:

1.  Ensure PyInstaller is installed:
    ```bash
    pip install pyinstaller
    ```
2.  Navigate to the project root directory in your terminal.
3.  Run the PyInstaller command. Use the appropriate line continuation character for your shell (`^` for Windows CMD, `` ` `` for PowerShell, or `\` for Linux/macOS shells):

    **For Windows PowerShell:**
    ```powershell
    pyinstaller --noconsole --onefile `
    --name "Dashlane CLI GUI" `
    --icon "bilde.png" `
    --add-data "bilde.png;." `
    --add-data "config.ini;." `
    main.py
    ```
    **For Windows Command Prompt (CMD), Linux, or macOS (all on one line):**
    ```bash
    pyinstaller --noconsole --onefile --name "Dashlane CLI GUI" --icon "bilde.png" --add-data "bilde.png;." --add-data "config.ini;." main.py
    ```

    The executable will be generated in the `dist/` directory.

---

## Security Notes

* This application relies directly on the `dcli` for all interactions with your Dashlane vault. Your passwords and sensitive data are never stored permanently by this GUI.
* We've implemented logging that *does not* capture your passwords or logins in cleartext.
* Copied passwords automatically clear from your clipboard after a configurable delay.
* **Always ensure your `dcli` is properly secured and authenticated.** If you encounter authentication issues, try running `dcli accounts whoami` in your terminal.

---

## Contributing

Feel free to open issues for bug reports or feature requests. Pull requests are also welcome!

---

## License

*(Please add your chosen license here, e.g., MIT, Apache 2.0, GPL. If you haven't decided, the MIT License is a popular and permissive choice.)*

---
