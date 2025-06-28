import tkinter as tk
from tkinter import messagebox, Toplevel, Listbox, Scrollbar
from tkinter import ttk
import subprocess
import threading
import sys
import json
import logging
import configparser
import os
import platform
import time
import string
import webbrowser
from subprocess import TimeoutExpired # Import TimeoutExpired specifically

# --- Configuration and Logging Setup ---
_CONFIG_FILE = 'config.ini'
_LOG_FILE = 'dashlane_gui.log'
_MAX_SEARCH_HISTORY = 10

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
                    filename=_LOG_FILE,
                    filemode='a')
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

# --- Dashlane Color Palette ---
DL_COLORS = {
    "dark_accent": "#02333D",
    "main_bg_light": "#F8F8F8",
    "input_bg": "#FFFFFF",
    "button_light_hover": "#F0F0F0",
    "highlight_blue": "#00A5FF",
    "text_dark": "#333333",
    "text_light": "#FFFFFF",
    "error_red": "#E74C3C",
    "warning_orange": "#F39C12",
    "scrollbar_thumb_light": "#E0E0E0"
}


# --- App Class Definition ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dashlane CLI GUI")

        self.CONFIG_FILE = _CONFIG_FILE
        self.LOG_FILE = _LOG_FILE
        self.MAX_SEARCH_HISTORY = _MAX_SEARCH_HISTORY

        # Use self.app_config for the ConfigParser instance to avoid name conflict with tk.Tk.config()
        self.app_config = configparser.ConfigParser()
        self.app_config['SETTINGS'] = {
            'clipboard_clear_delay_seconds': '30',
            'search_history': '[]',
            'window_x': '0',
            'window_y': '0',
            'window_width': '600',
            'window_height': '500'
        }

        try:
            if os.path.exists(self.CONFIG_FILE):
                self.app_config.read(self.CONFIG_FILE)
                logging.info(f"Configuration loaded from {self.CONFIG_FILE}")
            else:
                with open(self.CONFIG_FILE, 'w') as f:
                    self.app_config.write(f)
                logging.info(f"Created default configuration file: {self.CONFIG_FILE}")
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")

        self.CLIPBOARD_CLEAR_DELAY_SECONDS = int(self.app_config['SETTINGS']['clipboard_clear_delay_seconds'])
        self.SEARCH_HISTORY = json.loads(self.app_config['SETTINGS']['search_history'])

        # Global variables for application state
        self.CURRENTLY_DISPLAYED_ITEMS = []
        self._treeview_sort_orders = {}
        self._countdown_id = None
        self._countdown_seconds_remaining = 0

        # Set the window icon
        try:
            icon_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'bilde.png')
            if os.path.exists(icon_path):
                self.iconphoto(False, tk.PhotoImage(file=icon_path))
                logging.info(f"Application icon set from {icon_path}")
            else:
                logging.warning(f"Application icon file not found at {icon_path}. Skipping icon setting.")
        except Exception as e:
            logging.error(f"Error setting application icon: {e}")

        # Set initial window geometry
        try:
            initial_x = int(self.app_config['SETTINGS']['window_x'])
            initial_y = int(self.app_config['SETTINGS']['window_y'])
            initial_width = int(self.app_config['SETTINGS']['window_width'])
            initial_height = int(self.app_config['SETTINGS']['window_height'])
            self.geometry(f"{initial_width}x{initial_height}+{initial_x}+{initial_y}")
            logging.info(f"Restored window geometry: {initial_width}x{initial_height}+{initial_x}+{initial_y}")
        except Exception as e:
            logging.warning(f"Could not restore window geometry, using defaults. Error: {e}")
            self.geometry("600x500")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize styles
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self._setup_styles()

        # Create main frames (login and main GUI)
        self.login_frame = ttk.Frame(self, style='DarkAccent.TFrame')
        self.main_gui_frame = ttk.Frame(self, style='MainContent.TFrame')

        # Create and pack the status label early so it's always visible
        self.status_label = ttk.Label(self, text="Initializing...", relief=tk.FLAT, anchor=tk.W, style='Status.TLabel')
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, ipady=2)
        self.update_status("Initializing...", 'info') # Now this updates a visible label

        # Immediately pack the login frame as the initial view
        self.login_frame.pack(expand=True, fill="both")
        # Create the login_status_label and buttons, set initial state
        self.login_status_label = ttk.Label(self.login_frame, text="Checking Dashlane CLI login status...", style='DarkAccent.TLabel', wraplength=400)
        self.login_status_label.pack(pady=10)
        self.sync_button = ttk.Button(self.login_frame, text="Sync & Login", command=self.start_sync_thread, state=tk.DISABLED)
        self.sync_button.pack(pady=20)
        self.dcli_install_button = ttk.Button(self.login_frame, text="Open DCLI Install Page", command=self.open_dcli_install_page, state=tk.DISABLED)
        self.dcli_install_button.pack(pady=10)

        # Initial check for dcli status (this will update login_status_label or switch frame)
        self.check_dcli_status()

    def _setup_styles(self):
        # Use self.configure() to set the background of the main Tkinter window
        self.configure(bg=DL_COLORS["dark_accent"])
        self.style.configure('TFrame', background=DL_COLORS["dark_accent"], borderwidth=0, relief='flat')
        self.style.configure('DarkAccent.TFrame', background=DL_COLORS["dark_accent"], borderwidth=0, relief='flat')
        self.style.configure('TLabel', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"])
        self.style.configure('DarkAccent.TLabel', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"])
        self.style.configure('MainContent.TFrame', background=DL_COLORS["main_bg_light"], borderwidth=0, relief='flat')
        self.style.configure('MainContent.TLabel', background=DL_COLORS["main_bg_light"], foreground=DL_COLORS["text_dark"])

        self.style.configure('TEntry', fieldbackground=DL_COLORS["input_bg"], foreground=DL_COLORS["text_dark"], borderwidth=1, relief='solid', focusthickness=0, focuscolor='none')

        self.style.configure('TCombobox', background=DL_COLORS["input_bg"], fieldbackground=DL_COLORS["input_bg"], foreground=DL_COLORS["text_dark"], selectbackground=DL_COLORS["input_bg"], selectforeground=DL_COLORS["text_dark"], bordercolor=DL_COLORS["dark_accent"], darkcolor=DL_COLORS["dark_accent"], lightcolor=DL_COLORS["dark_accent"], insertcolor=DL_COLORS["text_dark"], padding=[5, 2], relief='solid', borderwidth=1, focusthickness=0, focuscolor='none', arrowsize=12)
        self.style.map('TCombobox',
                  background=[('readonly', DL_COLORS["input_bg"]), ('disabled', DL_COLORS["input_bg"])],
                  fieldbackground=[('readonly', DL_COLORS["input_bg"]), ('disabled', DL_COLORS["input_bg"])],
                  foreground=[('readonly', DL_COLORS["text_dark"]), ('disabled', DL_COLORS["text_dark"])],
                  arrowcolor=[('active', DL_COLORS["highlight_blue"]), ('!active', DL_COLORS["text_dark"])],
                  bordercolor=[('focus', DL_COLORS["highlight_blue"])]
                  )
        self.style.configure("TCombobox.PopdownFrame", background=DL_COLORS["main_bg_light"], borderwidth=0)
        self.style.configure("TCombobox.Listbox", background=DL_COLORS["main_bg_light"], foreground=DL_COLORS["text_dark"], selectbackground=DL_COLORS["highlight_blue"], selectforeground=DL_COLORS["text_light"], borderwidth=0, relief='flat')

        self.style.configure('TButton', background=DL_COLORS["input_bg"], foreground=DL_COLORS["text_dark"], font=('Arial', 10, 'bold'), borderwidth=0, relief='flat', padding=[10, 5], focusthickness=0, focuscolor='none')
        self.style.map('TButton',
                  background=[('active', DL_COLORS["button_light_hover"]), ('!active', DL_COLORS["input_bg"])],
                  foreground=[('active', DL_COLORS["text_dark"]), ('!active', DL_COLORS["text_dark"])])

        self.style.configure('Treeview.Heading', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"], font=('Arial', 10, 'bold'), relief='flat', padding=[5,5], borderwidth=0)
        self.style.configure('Treeview', background=DL_COLORS["main_bg_light"], fieldbackground=DL_COLORS["main_bg_light"], foreground=DL_COLORS["text_dark"], rowheight=28, borderwidth=0, relief='flat')
        self.style.map('Treeview', background=[('selected', DL_COLORS["highlight_blue"])], foreground=[('selected', DL_COLORS["text_light"])])

        self.style.configure('PasswordToggle.TCheckbutton', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"], font=('Arial', 9), padding=(0,0,0,0), focusthickness=0, focuscolor='none')
        self.style.map('PasswordToggle.TCheckbutton', background=[('active', DL_COLORS["dark_accent"]), ('!active', DL_COLORS["dark_accent"])], foreground=[('selected', DL_COLORS["highlight_blue"]), ('!selected', DL_COLORS["text_light"])])

        self.style.configure("Vertical.TScrollbar", troughcolor=DL_COLORS["main_bg_light"], background=DL_COLORS["scrollbar_thumb_light"], bordercolor=DL_COLORS["main_bg_light"], arrowcolor=DL_COLORS["text_dark"], relief='flat', borderwidth=0, arrowsize=10)
        self.style.map("Vertical.TScrollbar", background=[('active', DL_COLORS["dark_accent"])], arrowcolor=[('active', DL_COLORS["highlight_blue"])])

        self.style.configure("Horizontal.TScrollbar", troughcolor=DL_COLORS["main_bg_light"], background=DL_COLORS["scrollbar_thumb_light"], bordercolor=DL_COLORS["main_bg_light"], arrowcolor=DL_COLORS["text_dark"], relief='flat', borderwidth=0, arrowsize=10)
        self.style.map("Horizontal.TScrollbar", background=[('active', DL_COLORS["dark_accent"])], arrowcolor=[('active', DL_COLORS["highlight_blue"])])

        self.style.configure('Status.TLabel', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"], relief=tk.FLAT, padding=[5,2])


    def check_dcli_status(self):
        """
        Runs dcli --version to check if dcli is installed,
        then dcli accounts whoami to check login status.
        Transitions to main GUI or login page based on results.
        """
        self.update_status("Checking Dashlane CLI status...", 'info')
        threading.Thread(target=self._run_dcli_status_check, daemon=True).start()

    def _run_dcli_status_check(self):
        """
        Executes actual dcli commands in a thread for status check.
        Added timeouts to prevent hanging if interactive input is expected.
        """
        try:
            # Check if dcli command exists
            logging.info("Attempting to run 'dcli --version' to confirm dcli presence...")
            # Added a timeout to prevent hanging if dcli isn't responding quickly
            subprocess.run(['dcli', '--version'], check=True, capture_output=True, text=True, encoding='utf-8', timeout=5)
            logging.info("✔ 'dcli --version' successful, dcli command is found.")

            # Check if dcli is logged in
            logging.info("Running 'dcli accounts whoami' to check login status...")
            # Added a timeout to prevent hanging if it's waiting for interactive input (e.g., master password)
            result = subprocess.run(['dcli', 'accounts', 'whoami'], capture_output=True, text=True, check=False, encoding='utf-8', timeout=10)

            logging.info(f"dcli whoami - Return Code: {result.returncode}")
            logging.info(f"dcli whoami - STDOUT: '{result.stdout.strip()}'")
            logging.info(f"dcli whoami - STDERR: '{result.stderr.strip()}'")

            # CORRECTED LOGIC: Check for successful return code AND non-empty output, or output containing '@'
            if result.returncode == 0 and (result.stdout.strip() != '' or '@' in result.stdout):
                logging.info("✔ dcli is detected as logged in.")
                self.after(0, self.show_main_gui)
            else:
                logging.info("✖ dcli is not logged in based on 'whoami' output or return code. Showing login page.")
                self.after(0, self.show_login_page)

        except FileNotFoundError:
            logging.error("✖ 'dcli' command not found during status check. Showing login page with 'not found' message.")
            self.after(0, lambda: self.show_login_page(dcli_not_found=True))
        except TimeoutExpired as e: # Catch TimeoutExpired specifically for subprocess.run
            logging.error(f"dcli command timed out. This often means it's waiting for interactive input in the terminal: {e}")
            self.after(0, lambda: self.show_login_page(dcli_not_found=False)) # Treat as not logged in, show login page
        except subprocess.CalledProcessError as e:
            logging.error(f"subprocess.CalledProcessError during dcli status check (unexpected): {e}")
            logging.error(f"STDOUT: '{e.stdout.strip()}'")
            logging.error(f"STDERR: '{e.stderr.strip()}'")
            self.after(0, self.show_login_page)
        except Exception as e:
            logging.error(f"Unexpected error during dcli status check: {e}", exc_info=True)
            self.after(0, lambda: self.show_login_page(dcli_not_found=True))


    def show_login_page(self, dcli_not_found=False):
        """Displays or updates the login/sync page."""
        self.main_gui_frame.pack_forget()
        self.login_frame.pack(expand=True, fill="both") # Ensure it's packed if not already

        # Update the existing login_status_label and buttons
        if dcli_not_found:
            self.login_status_label.config(text="Dashlane CLI (dcli) was not found in your system's PATH. Please install it first.", foreground=DL_COLORS["error_red"])
            self.dcli_install_button.config(state=tk.NORMAL)
            self.sync_button.config(state=tk.DISABLED)
            self.update_status("DCLI not found.", 'error')
        else:
            self.login_status_label.config(text="Dashlane CLI is not logged in. Please click 'Sync & Login' to authenticate.", foreground=DL_COLORS["text_light"])
            self.dcli_install_button.config(state=tk.DISABLED) # Disable if dcli is found but not logged in
            self.sync_button.config(state=tk.NORMAL)
            self.update_status("DCLI login required.", 'warn')


    def open_dcli_install_page(self):
        """Opens the Dashlane CLI installation page in the default browser."""
        webbrowser.open("https://cli.dashlane.com/install")
        logging.info("Opened Dashlane CLI installation page.")
        self.update_status("DCLI installation page opened.", 'info')

    def start_sync_thread(self):
        """Starts the dcli sync operation in a separate thread."""
        self.sync_button.config(state=tk.DISABLED)
        # IMPORTANT: Instruct the user to check their terminal for prompts
        self.login_status_label.config(text="Syncing... Please **IMMEDIATELY check your terminal/console window (a new one might pop up!)** for Dashlane prompts (e.g., Master Password, 2FA). This window will update after you complete terminal interaction.", foreground=DL_COLORS["warning_orange"])
        self.update_status("DCLI sync in progress...", 'info')

        sync_thread = threading.Thread(target=self._run_dcli_sync_and_check_after_sync, daemon=True)
        sync_thread.start()

    def _run_dcli_sync_and_check_after_sync(self):
        """
        Runs dcli sync interactively, allowing user input in the terminal.
        Then re-checks login status.
        """
        try:
            # Run dcli sync interactively in the user's terminal
            logging.info("Starting 'dcli sync' interactively. User will need to respond in the launching terminal.")
            process = subprocess.Popen(
                ['dcli', 'sync'],
                stdin=sys.stdin, # Pass stdin to dcli so user can type
                stdout=sys.stdout, # Pass stdout to dcli so prompts are visible
                stderr=sys.stderr, # Pass stderr to dcli
                encoding='utf-8',
                errors='ignore',
                shell=False # Safer for direct command execution
            )
            # Wait for the sync process to complete
            process.wait() # This will block until dcli sync exits

            logging.info(f"'dcli sync' process finished with Exit Code: {process.returncode}")

            if process.returncode != 0:
                # If sync failed, the user saw messages in the terminal.
                self.after(0, lambda: self.on_sync_failure(f"DCLI Sync exited with code {process.returncode}. Please review your terminal for details and try again."))
                return

            # After successful sync, re-check login status (this time capturing output with timeout)
            logging.info("Sync completed, re-checking login status with 'dcli accounts whoami'...")
            login_check_result = subprocess.run(
                ['dcli', 'accounts', 'whoami'],
                capture_output=True,
                text=True,
                check=False,
                encoding='utf-8',
                timeout=10 # Add timeout for this post-sync check
            )

            # CORRECTED LOGIC: Check for successful return code AND non-empty output, or output containing '@'
            if login_check_result.returncode == 0 and (login_check_result.stdout.strip() != '' or '@' in login_check_result.stdout):
                self.after(0, self.on_sync_success)
            else:
                logging.warning(f"Login status inconclusive after sync. Whoami RC: {login_check_result.returncode}, STDOUT: {login_check_result.stdout.strip()}")
                self.after(0, lambda: self.on_sync_failure("Login status inconclusive after sync. Please ensure you fully authenticated in the terminal."))

        except FileNotFoundError:
            self.after(0, lambda: self.on_sync_failure("Error: 'dcli' command not found. Please install Dashlane CLI."))
        except TimeoutExpired:
            logging.error("Timeout occurred while running dcli accounts whoami after sync.")
            self.after(0, lambda: self.on_sync_failure("DCLI login check timed out after sync. Please ensure you authenticated correctly in the terminal."))
        except Exception as e:
            logging.error(f"An unexpected error occurred during sync: {e}", exc_info=True)
            self.after(0, lambda: self.on_sync_failure(f"An unexpected error occurred during sync: {e}"))
        finally:
            self.after(0, lambda: self.sync_button.config(state=tk.NORMAL))


    def on_sync_success(self):
        """Handles successful dcli sync and login."""
        self.login_status_label.config(text="Login successful! Loading items...", foreground="green")
        messagebox.showinfo("Success", "Dashlane CLI synced and logged in successfully!")
        self.show_main_gui()

    def on_sync_failure(self, message):
        """Handles failed dcli sync or login."""
        self.login_status_label.config(text=message, foreground=DL_COLORS["error_red"])
        messagebox.showerror("Sync Failed", message)
        self.update_status("DCLI sync failed.", 'error')


    def show_main_gui(self):
        """Builds and displays the main application GUI."""
        self.login_frame.pack_forget()
        self.main_gui_frame.pack(expand=True, fill="both", padx=15, pady=15)

        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Settings...", command=self.open_settings_window)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about_window)

        search_frame = ttk.Frame(self.main_gui_frame, style='MainContent.TFrame')
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Filter by Title/Login:", style='MainContent.TLabel').pack(side=tk.LEFT, padx=(0, 5))

        self.entry_site_name_var = tk.StringVar(value=self.SEARCH_HISTORY[0] if self.SEARCH_HISTORY else '')
        self.entry_site_name = ttk.Combobox(search_frame, width=40, values=self.SEARCH_HISTORY, textvariable=self.entry_site_name_var)
        self.entry_site_name.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.entry_site_name.focus_set()
        self.entry_site_name.bind('<KeyRelease>', self.filter_treeview_items)
        self.entry_site_name.bind('<<ComboboxSelected>>', self.filter_treeview_items)

        clear_button = ttk.Button(search_frame, text="X", width=3, command=self.clear_search_field)
        clear_button.pack(side=tk.LEFT, padx=(5,0))

        treeview_frame = ttk.Frame(self.main_gui_frame, style='MainContent.TFrame')
        treeview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('Title', 'Login', 'Type')
        self.item_treeview = ttk.Treeview(treeview_frame, columns=columns, show='headings')

        self.item_treeview.heading('Title', text='Title', anchor=tk.W, command=lambda: self.treeview_sort_column('Title'))
        self.item_treeview.heading('Login', text='Login', anchor=tk.W, command=lambda: self.treeview_sort_column('Login'))
        self.item_treeview.heading('Type', text='Type', anchor=tk.W, command=lambda: self.treeview_sort_column('Type'))

        self.item_treeview.column('Title', width=200, minwidth=150)
        self.item_treeview.column('Login', width=150, minwidth=100)
        self.item_treeview.column('Type', width=100, minwidth=80)

        self.item_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        treeview_scrollbar = ttk.Scrollbar(treeview_frame, orient=tk.VERTICAL, command=self.item_treeview.yview, style="Vertical.TScrollbar")
        self.item_treeview.configure(yscrollcommand=treeview_scrollbar.set)
        treeview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.item_treeview.bind('<<TreeviewSelect>>', self.on_item_select_from_list)
        self.item_treeview.bind('<Double-1>', lambda event: self.view_selected_item_details())

        action_buttons_frame = ttk.Frame(self.main_gui_frame, style='MainContent.TFrame')
        action_buttons_frame.pack(pady=5)

        self.btn_view_details = ttk.Button(action_buttons_frame, text="View Details", command=self.view_selected_item_details, state=tk.DISABLED)
        self.btn_view_details.pack(side=tk.LEFT, padx=5)

        self.btn_refresh_list = ttk.Button(action_buttons_frame, text="Refresh List", command=lambda: threading.Thread(target=self.run_dcli_command_and_populate_treeview, args=("",), daemon=True).start())
        self.btn_refresh_list.pack(side=tk.LEFT, padx=5)

        # Removed status_label packing from here, it's now packed in __init__
        self.update_status("Main GUI loaded. Attempting to load items...", 'info')
        threading.Thread(target=self.run_dcli_command_and_populate_treeview, args=("",), daemon=True).start()


    def copy_to_clipboard(self, text, button_widget=None, original_text=None, is_sensitive=True):
        self.clipboard_clear()
        self.clipboard_append(text)

        if is_sensitive:
            logging.info("Copied sensitive data to clipboard (password/login).")
        else:
            logging.info(f"Copied text to clipboard: '{text[:50]}{'...' if len(text) > 50 else ''}'")

        if button_widget and original_text:
            button_widget.config(text="Copied!", state=tk.DISABLED)
            self.after(1500, lambda: button_widget.config(text=original_text, state=tk.NORMAL))
        self.start_clipboard_countdown()

    def launch_terminal_command(self, command_parts):
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(['start', 'cmd', '/k'] + command_parts, shell=True)
            elif system == "Darwin":
                subprocess.Popen(['open', '-a', 'Terminal', '--args'] + command_parts)
            elif system == "Linux":
                try:
                    subprocess.Popen(['gnome-terminal', '--'] + command_parts)
                except FileNotFoundError:
                    subprocess.Popen(['xterm', '-e'] + command_parts)
            else:
                messagebox.showwarning("Unsupported OS", f"Cannot launch terminal on {system}.")
                logging.warning(f"Unsupported OS for terminal launch: {system}")
                return False
            logging.info(f"Launched terminal command: {' '.join(command_parts)}")
            return True
        except FileNotFoundError as e:
            messagebox.showerror("Terminal Not Found", f"Could not find a suitable terminal emulator. Error: {e}")
            logging.error(f"Terminal emulator not found: {e}")
            return False
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch terminal command. Error: {e}")
            logging.error(f"Failed to launch terminal command: {e}")
            return False

    def add_to_search_history(self, term):
        term = term.strip()
        if not term: return

        if term in self.SEARCH_HISTORY:
            self.SEARCH_HISTORY.remove(term)
        self.SEARCH_HISTORY.insert(0, term)
        self.SEARCH_HISTORY = self.SEARCH_HISTORY[:self.MAX_SEARCH_HISTORY]

        if hasattr(self, 'entry_site_name') and self.entry_site_name.winfo_exists():
            self.entry_site_name['values'] = self.SEARCH_HISTORY

        try:
            self.app_config['SETTINGS']['search_history'] = json.dumps(self.SEARCH_HISTORY)
            with open(self.CONFIG_FILE, 'w') as f:
                self.app_config.write(f)
            logging.info(f"Search history updated with '{term}'.")
        except Exception as e:
            logging.error(f"Failed to save search history: {e}")


    def display_password_details_window(self, item_title, item_login, password):
        details_window = Toplevel(self)
        details_window.title(f"Details for {item_title}")
        details_window.transient(self)
        details_window.grab_set()

        details_window.config(bg=DL_COLORS["dark_accent"])
        content_frame = ttk.Frame(details_window, padding="15 15 15 15", style='DarkAccent.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(content_frame, text="Title:", font=('Arial', 10, 'bold'), style='DarkAccent.TLabel').grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(content_frame, text=item_title, wraplength=300, style='DarkAccent.TLabel').grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(content_frame, text="Login:", font=('Arial', 10, 'bold'), style='DarkAccent.TLabel').grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Label(content_frame, text=item_login, wraplength=300, style='DarkAccent.TLabel').grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(content_frame, text="Password:", font=('Arial', 10, 'bold'), style='DarkAccent.TLabel').grid(row=2, column=0, sticky=tk.W, pady=2)

        actual_password_text = password
        show_password_var = tk.BooleanVar(value=False)

        password_display = ttk.Label(content_frame, text="*", wraplength=300, style='DarkAccent.TLabel')
        password_display.grid(row=2, column=1, sticky=tk.W, pady=2)

        def update_password_display_label():
            if show_password_var.get():
                password_display.config(text=actual_password_text)
            else:
                password_display.config(text="*" * len(actual_password_text))

        btn_toggle_password_visibility = ttk.Checkbutton(
            content_frame, text="Show Password", variable=show_password_var, command=update_password_display_label,
            onvalue=True, offvalue=False, style='PasswordToggle.TCheckbutton'
        )
        btn_toggle_password_visibility.grid(row=2, column=2, padx=5, sticky=tk.W)
        update_password_display_label()

        button_frame = ttk.Frame(content_frame, style='DarkAccent.TFrame')
        button_frame.grid(row=3, column=0, columnspan=3, pady=15)

        btn_copy_password = ttk.Button(button_frame, text="Copy Password")
        btn_copy_password.config(command=lambda: self.copy_to_clipboard(password, btn_copy_password, "Copy Password", is_sensitive=True))
        btn_copy_password.pack(side=tk.LEFT, padx=5)

        btn_copy_login = ttk.Button(button_frame, text="Copy Login")
        btn_copy_login.config(command=lambda: self.copy_to_clipboard(item_login, btn_copy_login, "Copy Login", is_sensitive=True))
        btn_copy_login.pack(side=tk.LEFT, padx=5)

        btn_copy_both = ttk.Button(button_frame, text="Copy Both")
        btn_copy_both.config(command=lambda: self.copy_to_clipboard(f"{item_login}:{password}", btn_copy_both, "Copy Both", is_sensitive=True))
        btn_copy_both.pack(side=tk.LEFT, padx=5)

        ttk.Button(content_frame, text="Close", command=details_window.destroy).grid(row=4, column=0, columnspan=3, pady=5)

        details_window.protocol("WM_DELETE_WINDOW", lambda: details_window.destroy())
        logging.info(f"Opened password details window for '{item_title}'.")
        self.update_status("Password details displayed.", 'info')

        details_window.bind("<Destroy>", lambda e: self.btn_view_details.config(state=tk.NORMAL))


    def clear_clipboard(self):
        if self._countdown_id:
            self.after_cancel(self._countdown_id)
            self._countdown_id = None
        self.clipboard_clear()
        logging.info("Clipboard automatically cleared.")
        self.update_status("Clipboard cleared. Ready.", 'info')

    def start_clipboard_countdown(self):
        if self._countdown_id:
            self.after_cancel(self._countdown_id)
            self._countdown_id = None
        self._countdown_seconds_remaining = self.CLIPBOARD_CLEAR_DELAY_SECONDS
        self.update_countdown()

    def update_countdown(self):
        if self._countdown_seconds_remaining > 0:
            self.update_status(f"Password copied. Clearing in {self._countdown_seconds_remaining} seconds...", 'info')
            self._countdown_seconds_remaining -= 1
            self._countdown_id = self.after(1000, self.update_countdown)
        else:
            self.clear_clipboard()

    def handle_error_in_thread(self, title, message, level='error', show_login_button=False):
        if self._countdown_id:
            self.after_cancel(self._countdown_id)
            self._countdown_id = None

        if show_login_button:
            response = messagebox.askyesno(title, message + "\n\nWould you like to try running `dcli accounts whoami` in a new terminal to check authentication?")
            if response:
                self.launch_terminal_command(["dcli", "accounts", "whoami"])
                self.update_status("Please check your dcli authentication in the terminal. Ready.", 'info')
            else:
                self.update_status("Error occurred. Ready.", 'error')
        else:
            messagebox.showerror(title, message)
            self.update_status(f"Error: {message}", level)

        if hasattr(self, 'btn_view_details'):
            self.btn_view_details.config(state=tk.NORMAL)
        logging.error(f"GUI Error: {title} - {message}")

    def update_status(self, message, level='info'):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text=message)
            if level == 'error':
                self.status_label.config(foreground=DL_COLORS["error_red"])
            elif level == 'warn':
                self.status_label.config(foreground=DL_COLORS["warning_orange"])
            else:
                self.status_label.config(foreground=DL_COLORS["text_light"])
        logging.debug(f"Status update: {message}")

    def on_item_select_from_list(self, event):
        selected_item_iid = self.item_treeview.selection()
        if selected_item_iid:
            self.btn_view_details.config(state=tk.NORMAL)
            self.update_status("Item selected. Click 'View Details' or double-click.", 'info')
        else:
            self.btn_view_details.config(state=tk.DISABLED)

    def view_selected_item_details(self):
        selected_item_iid = self.item_treeview.selection()
        if not selected_item_iid:
            messagebox.showwarning("Selection Error", "Please select an item from the list first.")
            self.update_status("No item selected.", 'warn')
            return

        selected_index_tag = self.item_treeview.item(selected_item_iid[0], 'tag')
        if selected_index_tag and selected_index_tag[0].isdigit():
            try:
                actual_item_data = self.CURRENTLY_DISPLAYED_ITEMS[int(selected_index_tag[0])]
                item_title = actual_item_data.get('title', 'N/A')
                item_login = actual_item_data.get('login', 'N/A')
                password = actual_item_data.get('password')

                if not password:
                    specific_message = f"The selected item '{item_title}' (Login: {item_login}) does not contain a 'password' field."
                    if actual_item_data.get('note'):
                        specific_message = f"'{item_title}' is a Secure Note. No password to display."
                    elif actual_item_data.get('firstName') or actual_item_data.get('lastName'):
                        specific_message = f"'{item_title}' is a Personal Info item. No password to display."
                    elif actual_item_data.get('address1') or actual_item_data.get('city'):
                        specific_message = f"'{item_title}' is an Address item. No password to display."
                    elif actual_item_data.get('website'):
                        specific_message = f"'{item_title}' is a Website item (no login/password detected)."

                    self.handle_error_in_thread("Password Not Found", specific_message, 'warn')
                    return

                self.display_password_details_window(item_title, item_login, password)
                self.btn_view_details.config(state=tk.DISABLED)

            except IndexError:
                logging.error(f"Could not retrieve full item data for selected item_iid: {selected_item_iid}. Index {selected_index_tag} out of bounds in CURRENTLY_DISPLAYED_ITEMS.")
                self.handle_error_in_thread("Data Error", "Could not retrieve full item details. Please try again or refresh list.")
            except Exception as e:
                logging.error(f"Error viewing item details: {e}")
                self.handle_error_in_thread("Error", f"Failed to view item details: {str(e)}")
        else:
            self.update_status("No item selected.", 'warn')


    def treeview_sort_column(self, col_id):
        """Sort a Treeview column when a header is clicked."""
        current_sort_order = self._treeview_sort_orders.get(col_id, False)
        reverse_sort = not current_sort_order

        def get_sort_value(item):
            if col_id == 'Title':
                return item.get('title', '').lower()
            elif col_id == 'Login':
                return item.get('login', '').lower()
            elif col_id == 'Type':
                if not item.get('password'):
                    if item.get('note') is not None and item.get('note') != '': return "Secure Note"
                    elif any(key in item for key in ['firstName', 'lastName', 'birthDate', 'gender']): return "PersonalInfo"
                    elif any(key in item for key in ['address1', 'city', 'zipCode', 'country']): return "Address"
                    elif any(key in item for key in ['cardHolderName', 'cardNumber']): return "Credit Card"
                    elif any(key in item for key in ['licenseNumber', 'stateOfIssue']): return "ID"
                    elif item.get('website'): return "Website Only"
                    else: return "Other"
                return "Login"
            return ''

        sorted_items = sorted(self.CURRENTLY_DISPLAYED_ITEMS, key=get_sort_value, reverse=reverse_sort)

        self._treeview_sort_orders[col_id] = reverse_sort

        self.populate_treeview(sorted_items)

        sort_direction = "Descending" if reverse_sort else "Ascending"
        self.update_status(f"Sorted by {col_id} ({sort_direction}).", 'info')
        logging.info(f"Treeview sorted by {col_id} in {sort_direction} order.")


    def run_dcli_command_and_populate_treeview(self, search_term=""):
        """
        Executes dcli password list with a specific search term or a broad filter for initial load.
        Populates Treeview with the results.
        """
        if self._countdown_id:
            self.after_cancel(self._countdown_id)
            self._countdown_id = None
            logging.info("Cancelled previous clipboard countdown due to dcli call.")

        self.update_status(f"Searching Dashlane CLI for '{search_term}'..." if search_term else "Loading all accessible items from Dashlane CLI...", 'info')
        self.btn_refresh_list.config(state=tk.DISABLED)
        self.btn_view_details.config(state=tk.DISABLED)

        command = ["dcli", "password", "list"]
        if search_term:
            command.append(search_term)
        else:
            broad_filters = list(string.ascii_lowercase) + list(string.digits)
            broad_filters.extend(['æ', 'ø', 'å', 'é', 'à', 'ç'])
            command.extend(broad_filters)

        command.extend(["--output", "json"])

        try:
            # For `password list`, we still capture output to parse JSON
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='ignore',
                shell=True # Keep shell=True for broad filters for now, although generally not recommended
            )
            stdout_data, stderr_data = process.communicate(timeout=30) # Added timeout

            logging.debug(f"dcli command executed: {' '.join(command)}")
            logging.info(f"dcli command Exit Code ({' '.join(command)}): {process.returncode}")

            if process.returncode != 0:
                logging.error(f"dcli STDERR (command: {' '.join(command)}):\n{stderr_data.strip()}")
                error_message = f"dcli command failed with exit code {process.returncode}:\n{stderr_data.strip()}"
                if "authentication required" in stderr_data.lower() or "not logged in" in stderr_data.lower():
                    self.after(0, lambda: self.handle_error_in_thread(
                        "Authentication Required",
                        "dcli is not authenticated. Please ensure you have an active `dcli` session. "
                        "You may need to interact with the Dashlane desktop app or browser extension "
                        "to ensure dcli is fully authenticated, or click 'Sync & Login'.",
                        show_login_button=True
                    ))
                elif "2fa" in stderr_data.lower() or "two-factor" in stderr_data.lower():
                    self.after(0, lambda: self.handle_error_in_thread(
                        "2FA Required",
                        "dcli is asking for your 2FA code. Please authenticate in the terminal.",
                        show_login_button=True
                    ))
                else:
                    self.after(0, lambda: self.handle_error_in_thread("dcli Error", error_message))
                return

            try:
                items = json.loads(stdout_data)

                unique_items_map = {}
                for item in items:
                    item_id = item.get('id')
                    if item_id:
                        unique_items_map[item_id] = item
                    else:
                        unique_key = (item.get('title', ''), item.get('login', ''), item.get('note', ''))
                        unique_items_map[unique_key] = item

                unique_items_list = list(unique_items_map.values())

                logging.info(f"Command '{' '.join(command)}' successfully returned {len(unique_items_list)} unique items (output not logged).")

                self.after(0, lambda: self.populate_treeview(unique_items_list))
                self.after(0, lambda: self.update_status(f"Loaded {len(unique_items_list)} items. Ready.", 'info'))

            except json.JSONDecodeError as e:
                output_snippet = stdout_data.strip()[:500] + "..." if len(stdout_data.strip()) > 500 else stdout_data.strip()
                sensitive_warning = " (WARNING: This output may contain sensitive data and is being logged for debugging JSON errors.)" if "password list" in " ".join(command) else ""
                error_message = f"dcli command did not return valid JSON. Error: {e}\nOutput (snippet){sensitive_warning}:\n{output_snippet}\nError:\n{stderr_data.strip()}"
                logging.error(error_message)
                self.after(0, lambda: self.handle_error_in_thread("JSON Decode Error", error_message))
            except Exception as json_e:
                error_message = f"Error processing dcli JSON output: {str(json_e)}\nOutput:\n{stdout_data.strip()}"
                self.after(0, lambda: self.handle_error_in_thread("JSON Processing Error", error_message))

        except FileNotFoundError:
            error_message = "dcli not found. Make sure it's in your PATH."
            self.after(0, lambda: self.handle_error_in_thread("Error", error_message, 'error', show_login_button=True))
        except TimeoutExpired as e:
            logging.error(f"dcli password list command timed out: {e}")
            self.after(0, lambda: self.handle_error_in_thread("Command Timed Out", "Dashlane CLI command took too long to respond. This might indicate an issue with dcli or it waiting for an unexpected input. Please try again, or check your terminal.", 'error', show_login_button=True))
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            self.after(0, lambda: self.handle_error_in_thread("An unexpected error occurred", error_message, 'error'))
        finally:
            self.after(0, lambda: self.btn_refresh_list.config(state=tk.NORMAL))
            self.after(0, lambda: self.btn_view_details.config(state=tk.NORMAL if self.item_treeview.selection() else tk.DISABLED))


    def populate_treeview(self, items_to_display):
        self.item_treeview.delete(*self.item_treeview.get_children())
        self.CURRENTLY_DISPLAYED_ITEMS = items_to_display

        for i, item in enumerate(items_to_display):
            title = item.get('title', 'No Title')
            login = item.get('login', 'No Login')

            item_type = "Login"
            if not item.get('password'):
                if item.get('note') is not None and item.get('note') != '': item_type = "Secure Note"
                elif any(key in item for key in ['firstName', 'lastName', 'birthDate', 'gender']): item_type = "Personal Info"
                elif any(key in item for key in ['address1', 'city', 'zipCode', 'country']): item_type = "Address"
                elif any(key in item for key in ['cardHolderName', 'cardNumber']): item_type = "Credit Card"
                elif any(key in item for key in ['licenseNumber', 'stateOfIssue']): item_type = "ID"
                elif item.get('website'): item_type = "Website Only"
                else: item_type = "Other"

            tag = "oddrow" if i % 2 == 0 else "evenrow"
            self.item_treeview.insert("", tk.END, text="", values=(title, login, item_type), tags=(str(i), tag))


    def filter_treeview_items(self, event=None):
        search_term = self.entry_site_name_var.get().strip()
        if search_term:
            self.add_to_search_history(search_term)
            self.update_status(f"Searching Dashlane CLI for '{search_term}'...", 'info')
            threading.Thread(target=self.run_dcli_command_and_populate_treeview, args=(search_term,), daemon=True).start()
        else:
            threading.Thread(target=self.run_dcli_command_and_populate_treeview, args=("",), daemon=True).start()
            self.update_status("Attempting to load all accessible items.", 'info')


    def clear_search_field(self):
        self.entry_site_name_var.set('')
        self.filter_treeview_items()
        self.update_status("Search field cleared. Attempting to load all accessible items.", 'info')
        logging.info("Search field cleared.")

    def show_about_window(self):
        about_window = Toplevel(self)
        about_window.title("About Dashlane CLI GUI")
        about_window.transient(self)
        about_window.grab_set()

        about_frame = ttk.Frame(about_window, padding="15 15 15 15", style='DarkAccent.TFrame')
        about_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(about_frame, text="Dashlane CLI GUI", font=('Arial', 12, 'bold'), style='DarkAccent.TLabel').pack(pady=5)
        ttk.Label(about_frame, text="Version: 1.0", style='DarkAccent.TLabel').pack(pady=2)
        ttk.Label(about_frame, text="A simple graphical interface for Dashlane CLI.", style='DarkAccent.TLabel').pack(pady=2)
        ttk.Label(about_frame, text="Developed by Gemini", style='DarkAccent.TLabel').pack(pady=2)
        ttk.Label(about_frame, text="", style='DarkAccent.TLabel').pack(pady=5)
        ttk.Label(about_frame, text="Requirements:", style='DarkAccent.TLabel').pack(pady=2)
        ttk.Label(about_frame, text="- Dashlane CLI installed and configured", style='DarkAccent.TLabel').pack(pady=2)
        ttk.Label(about_frame, text="- Python 3 with tkinter", style='DarkAccent.TLabel').pack(pady=2)

        ttk.Button(about_frame, text="Close", command=about_window.destroy).pack(pady=10)

        about_window.protocol("WM_DELETE_WINDOW", lambda: about_window.destroy())
        about_window.bind("<Destroy>", lambda e: about_window.grab_release())
        logging.info("Opened About window.")

    def open_settings_window(self):
        settings_window = Toplevel(self)
        settings_window.title("Settings")
        settings_window.transient(self)
        settings_window.grab_set()

        settings_window.config(bg=DL_COLORS["dark_accent"])
        content_frame = ttk.Frame(settings_window, padding="15 15 15 15", style='DarkAccent.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(content_frame, text="Clipboard Clear Delay (seconds):", style='DarkAccent.TLabel').grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        clipboard_delay_var = tk.StringVar(value=self.app_config['SETTINGS']['clipboard_clear_delay_seconds'])
        entry_clipboard_delay = ttk.Entry(content_frame, textvariable=clipboard_delay_var, width=10)
        entry_clipboard_delay.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)

        ttk.Label(content_frame, text="Search History:", style='DarkAccent.TLabel').grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        btn_clear_history = ttk.Button(content_frame, text="Clear Search History")
        btn_clear_history.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)

        def save_and_apply_settings():
            try:
                new_delay = int(clipboard_delay_var.get())
                if new_delay < 0:
                    messagebox.showwarning("Invalid Input", "Clipboard delay cannot be negative.")
                    return

                self.app_config['SETTINGS']['clipboard_clear_delay_seconds'] = str(new_delay)
                self.CLIPBOARD_CLEAR_DELAY_SECONDS = new_delay
                logging.info(f"Clipboard clear delay set to {new_delay} seconds.")

                if self._countdown_id and self._countdown_seconds_remaining > 0:
                    self.after_cancel(self._countdown_id)
                    self.start_clipboard_countdown()

                with open(self.CONFIG_FILE, 'w') as f:
                    self.app_config.write(f)

                self.update_status("Settings saved and applied!", 'info')
                messagebox.showinfo("Settings Saved", "Settings have been saved and applied.")
                settings_window.destroy()

            except ValueError:
                messagebox.showerror("Invalid Input", "Clipboard clear delay must be a whole number.")
            except Exception as e:
                logging.error(f"Error saving settings: {e}")
                messagebox.showerror("Error", f"Failed to save settings: {e}")

        def perform_clear_search_history():
            response = messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all search history?")
            if response:
                self.SEARCH_HISTORY = []
                self.app_config['SETTINGS']['search_history'] = json.dumps(self.SEARCH_HISTORY)

                if hasattr(self, 'entry_site_name') and self.entry_site_name.winfo_exists():
                    self.entry_site_name['values'] = []
                    self.entry_site_name_var.set('')

                with open(self.CONFIG_FILE, 'w') as f:
                    self.app_config.write(f)
                logging.info("Search history cleared.")
                self.update_status("Search history cleared!", 'info')
                messagebox.showinfo("History Cleared", "Search history has been cleared.")

        btn_clear_history.config(command=perform_clear_search_history)

        button_frame = ttk.Frame(content_frame, style='DarkAccent.TFrame')
        button_frame.grid(row=2, column=0, columnspan=2, pady=15)

        btn_save = ttk.Button(button_frame, text="Save", command=save_and_apply_settings)
        btn_save.pack(side=tk.LEFT, padx=5)

        btn_cancel = ttk.Button(button_frame, text="Cancel", command=settings_window.destroy)
        btn_cancel.pack(side=tk.LEFT, padx=5)

        settings_window.protocol("WM_DELETE_WINDOW", lambda: settings_window.destroy())
        settings_window.bind("<Destroy>", lambda e: settings_window.grab_release())
        logging.info("Opened Settings window.")

    def on_closing(self):
        try:
            self.app_config['SETTINGS']['window_x'] = str(self.winfo_x())
            self.app_config['SETTINGS']['window_y'] = str(self.winfo_y())
            self.app_config['SETTINGS']['window_width'] = str(self.winfo_width())
            self.app_config['SETTINGS']['window_height'] = str(self.winfo_height())
            with open(self.CONFIG_FILE, 'w') as f:
                self.app_config.write(f)
            logging.info("Window geometry saved.")
        except Exception as e:
            logging.error(f"Error saving window geometry: {e}")

        self.destroy()
        sys.exit()

if __name__ == "__main__":
    app = App()
    app.mainloop()