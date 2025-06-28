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

# --- Configuration and Logging Setup ---

CONFIG_FILE = 'config.ini'
LOG_FILE = 'dashlane_gui.log'
MAX_SEARCH_HISTORY = 10 # This is a constant for the max history length, not exposed for editing

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
                    filename=LOG_FILE,
                    filemode='w')
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

config = configparser.ConfigParser()
config['SETTINGS'] = {
    'clipboard_clear_delay_seconds': '30',
    'search_history': '[]',
    'window_x': '0',
    'window_y': '0',
    'window_width': '600',
    'window_height': '500'
}

try:
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        logging.info(f"Configuration loaded from {CONFIG_FILE}")
    else:
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        logging.info(f"Created default configuration file: {CONFIG_FILE}")
except Exception as e:
    logging.error(f"Error loading configuration: {e}")

CLIPBOARD_CLEAR_DELAY_SECONDS = int(config['SETTINGS']['clipboard_clear_delay_seconds'])
SEARCH_HISTORY = json.loads(config['SETTINGS']['search_history'])

# This global variable will store the items currently displayed after a search or initial load attempt
CURRENTLY_DISPLAYED_ITEMS = []

# Global dictionary to store sorting order for treeview columns
_treeview_sort_orders = {}

_countdown_id = None
_countdown_seconds_remaining = 0

# --- Corrected Dashlane Color Palette ---
DL_COLORS = {
    "dark_accent": "#02333D",     # The dark blue (main background, details window)
    "main_bg_light": "#F8F8F8",   # Very light grey (main content area, treeview background)
    "input_bg": "#FFFFFF",        # Pure white (entry fields, combobox field, and NOW BUTTONS)
    "button_light_hover": "#F0F0F0", # Light grey for hover effect on white buttons
    "highlight_blue": "#00A5FF",  # A vibrant blue for selection/highlight (Treeview selected row, active arrows)
    "text_dark": "#333333",       # Dark grey for text on light backgrounds (and NOW BUTTONS)
    "text_light": "#FFFFFF",      # White for text on dark backgrounds
    "error_red": "#E74C3C",       # Standard red for errors
    "warning_orange": "#F39C12",  # Standard orange for warnings
    "scrollbar_thumb_light": "#E0E0E0" # For scrollbar thumb (subtle contrast)
}
# --- END Configuration and Logging Setup ---


# --- HELPER FUNCTIONS ---

def copy_to_clipboard(text, button_widget=None, original_text=None):
    root.clipboard_clear()
    root.clipboard_append(text)
    logging.info(f"Copied text to clipboard: '{text[:50]}...'")

    if button_widget and original_text:
        button_widget.config(text="Copied!", state=tk.DISABLED)
        root.after(1500, lambda: button_widget.config(text=original_text, state=tk.NORMAL))

def launch_terminal_command(command_parts):
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

def add_to_search_history(term):
    global SEARCH_HISTORY
    term = term.strip()
    if not term: return

    if term in SEARCH_HISTORY:
        SEARCH_HISTORY.remove(term)
    SEARCH_HISTORY.insert(0, term)
    SEARCH_HISTORY = SEARCH_HISTORY[:MAX_SEARCH_HISTORY]

    entry_site_name['values'] = SEARCH_HISTORY

    try:
        config['SETTINGS']['search_history'] = json.dumps(SEARCH_HISTORY)
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        logging.info(f"Search history updated with '{term}'.")
    except Exception as e:
        logging.error(f"Failed to save search history: {e}")

# --- END HELPER FUNCTIONS ---


# --- START OF CORE GUI FUNCTIONS ---

def display_password_details_window(item_title, item_login, password):
    details_window = Toplevel(root)
    details_window.title(f"Details for {item_title}")
    details_window.transient(root)
    details_window.grab_set()

    # Apply dark accent background to details window and its frame
    details_window.config(bg=DL_COLORS["dark_accent"])
    content_frame = ttk.Frame(details_window, padding="15 15 15 15", style='DarkAccent.TFrame')
    content_frame.pack(fill=tk.BOTH, expand=True)

    # Labels for title, login, password in details window will have white text on dark background
    ttk.Label(content_frame, text="Title:", font=('Arial', 10, 'bold'), style='DarkAccent.TLabel').grid(row=0, column=0, sticky=tk.W, pady=2)
    ttk.Label(content_frame, text=item_title, wraplength=300, style='DarkAccent.TLabel').grid(row=0, column=1, sticky=tk.W, pady=2)

    ttk.Label(content_frame, text="Login:", font=('Arial', 10, 'bold'), style='DarkAccent.TLabel').grid(row=1, column=0, sticky=tk.W, pady=2)
    ttk.Label(content_frame, text=item_login, wraplength=300, style='DarkAccent.TLabel').grid(row=1, column=1, sticky=tk.W, pady=2)

    ttk.Label(content_frame, text="Password:", font=('Arial', 10, 'bold'), style='DarkAccent.TLabel').grid(row=2, column=0, sticky=tk.W, pady=2)
    
    # Password Visibility Toggle START
    actual_password_text = password
    show_password_var = tk.BooleanVar(value=False) # Initially hide password

    password_display = ttk.Label(content_frame, text="*", wraplength=300, style='DarkAccent.TLabel')
    password_display.grid(row=2, column=1, sticky=tk.W, pady=2)
    
    def update_password_display_label():
        if show_password_var.get():
            password_display.config(text=actual_password_text)
        else:
            password_display.config(text="*" * len(actual_password_text))
            
    btn_toggle_password_visibility = ttk.Checkbutton(
        content_frame,
        text="Show Password",
        variable=show_password_var,
        command=update_password_display_label,
        onvalue=True, offvalue=False,
        style='PasswordToggle.TCheckbutton' # Specific style for this checkbutton
    )
    btn_toggle_password_visibility.grid(row=2, column=2, padx=5, sticky=tk.W)
    update_password_display_label() # Set initial display based on hide
    # Password Visibility Toggle END

    button_frame = ttk.Frame(content_frame, style='DarkAccent.TFrame') # Buttons frame in details window
    button_frame.grid(row=3, column=0, columnspan=3, pady=15)

    btn_copy_password = ttk.Button(button_frame, text="Copy Password")
    btn_copy_password.config(command=lambda: copy_to_clipboard(password, btn_copy_password, "Copy Password"))
    btn_copy_password.pack(side=tk.LEFT, padx=5)

    btn_copy_login = ttk.Button(button_frame, text="Copy Login")
    btn_copy_login.config(command=lambda: copy_to_clipboard(item_login, btn_copy_login, "Copy Login"))
    btn_copy_login.pack(side=tk.LEFT, padx=5)

    btn_copy_both = ttk.Button(button_frame, text="Copy Both")
    btn_copy_both.config(command=lambda: copy_to_clipboard(f"{item_login}:{password}", btn_copy_both, "Copy Both"))
    btn_copy_both.pack(side=tk.LEFT, padx=5)

    ttk.Button(content_frame, text="Close", command=details_window.destroy).grid(row=4, column=0, columnspan=3, pady=5)

    details_window.protocol("WM_DELETE_WINDOW", lambda: details_window.destroy())
    logging.info(f"Opened password details window for '{item_title}'.")
    update_status("Password details displayed.", 'info')

    copy_to_clipboard(password)
    start_clipboard_countdown()

    details_window.bind("<Destroy>", lambda e: btn_view_details.config(state=tk.NORMAL))


def clear_clipboard():
    global status_label, _countdown_id
    if _countdown_id:
        root.after_cancel(_countdown_id)
        _countdown_id = None
    root.clipboard_clear()
    logging.info("Clipboard automatically cleared.")
    update_status("Clipboard cleared. Ready.", 'info')

def start_clipboard_countdown():
    global _countdown_seconds_remaining, _countdown_id
    if _countdown_id:
        root.after_cancel(_countdown_id)
        _countdown_id = None
    _countdown_seconds_remaining = CLIPBOARD_CLEAR_DELAY_SECONDS
    update_countdown()

def update_countdown():
    global _countdown_seconds_remaining, _countdown_id
    if _countdown_seconds_remaining > 0:
        update_status(f"Password copied. Clearing in {_countdown_seconds_remaining} seconds...", 'info')
        _countdown_seconds_remaining -= 1
        _countdown_id = root.after(1000, update_countdown)
    else:
        clear_clipboard()

def handle_error_in_thread(title, message, level='error', show_login_button=False):
    global status_label, _countdown_id
    if _countdown_id:
        root.after_cancel(_countdown_id)
        _countdown_id = None

    if show_login_button:
        response = messagebox.askyesno(title, message + "\n\nWould you like to try running `dcli accounts whoami` in a new terminal to check authentication?")
        if response:
            launch_terminal_command(["dcli", "accounts", "whoami"])
            update_status("Please check your dcli authentication in the terminal. Ready.", 'info')
        else:
            update_status("Error occurred. Ready.", 'error')
    else:
        messagebox.showerror(title, message)
        update_status(f"Error: {message}", level)

    btn_view_details.config(state=tk.NORMAL)
    logging.error(f"GUI Error: {title} - {message}")

def update_status(message, level='info'):
    global status_label
    status_label.config(text=message)
    # Adjust status label foreground based on message level on a dark background
    if level == 'error':
        status_label.config(foreground=DL_COLORS["error_red"])
    elif level == 'warn':
        status_label.config(foreground=DL_COLORS["warning_orange"])
    else:
        status_label.config(foreground=DL_COLORS["text_light"]) # Default text is white
    logging.debug(f"Status update: {message}")

def on_item_select_from_list(event):
    selected_item_iid = item_treeview.selection()
    if selected_item_iid:
        btn_view_details.config(state=tk.NORMAL)
        update_status("Item selected. Click 'View Details' or double-click.", 'info')
    else:
        btn_view_details.config(state=tk.DISABLED)

def view_selected_item_details():
    selected_item_iid = item_treeview.selection()
    if not selected_item_iid:
        messagebox.showwarning("Selection Error", "Please select an item from the list first.")
        update_status("No item selected.", 'warn')
        return

    selected_index_tag = item_treeview.item(selected_item_iid[0], 'tag')
    if selected_index_tag and selected_index_tag[0].isdigit():
        try:
            actual_item_data = CURRENTLY_DISPLAYED_ITEMS[int(selected_index_tag[0])]
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
                
                handle_error_in_thread("Password Not Found", specific_message, 'warn')
                return

            display_password_details_window(item_title, item_login, password)
            btn_view_details.config(state=tk.DISABLED)

        except IndexError:
            logging.error(f"Could not retrieve full item data for selected item_iid: {selected_item_iid}. Index {selected_index_tag} out of bounds in CURRENTLY_DISPLAYED_ITEMS.")
            handle_error_in_thread("Data Error", "Could not retrieve full item details. Please try again or refresh list.")
        except Exception as e:
            logging.error(f"Error viewing item details: {e}")
            handle_error_in_thread("Error", f"Failed to view item details: {str(e)}")
    else:
        update_status("No item selected.", 'warn')


def treeview_sort_column(col_id):
    """Sort a Treeview column when a header is clicked."""
    global _treeview_sort_orders
    
    current_sort_order = _treeview_sort_orders.get(col_id, False) # False for ascending, True for descending
    reverse_sort = not current_sort_order

    def get_sort_value(item):
        if col_id == 'Title':
            return item.get('title', '').lower()
        elif col_id == 'Login':
            return item.get('login', '').lower()
        elif col_id == 'Type':
            if not item.get('password'):
                if item.get('note') is not None and item.get('note') != '':
                    return "Secure Note"
                elif any(key in item for key in ['firstName', 'lastName', 'birthDate', 'gender']):
                    return "Personal Info"
                elif any(key in item for key in ['address1', 'city', 'zipCode', 'country']):
                    return "Address"
                elif any(key in item for key in ['cardHolderName', 'cardNumber']):
                    return "Credit Card"
                elif any(key in item for key in ['licenseNumber', 'stateOfIssue']):
                    return "ID"
                elif item.get('website'):
                    return "Website Only"
                else:
                    return "Other"
            return "Login"
        return ''

    sorted_items = sorted(CURRENTLY_DISPLAYED_ITEMS, key=get_sort_value, reverse=reverse_sort)
    
    _treeview_sort_orders[col_id] = reverse_sort
    
    populate_treeview(sorted_items)
    
    sort_direction = "Descending" if reverse_sort else "Ascending"
    update_status(f"Sorted by {col_id} ({sort_direction}).", 'info')
    logging.info(f"Treeview sorted by {col_id} in {sort_direction} order.")


def run_dcli_command_and_populate_treeview(search_term=""):
    """
    Executes dcli password list with a specific search term or a broad filter for initial load.
    Populates Treeview with the results.
    """
    global _countdown_id
    if _countdown_id:
        root.after_cancel(_countdown_id)
        _countdown_id = None
        logging.info("Cancelled previous clipboard countdown due to dcli call.")

    update_status(f"Searching Dashlane CLI for '{search_term}'..." if search_term else "Loading all accessible items from Dashlane CLI...", 'info')
    btn_refresh_list.config(state=tk.DISABLED)
    btn_view_details.config(state=tk.DISABLED)

    command = ["dcli", "password", "list"]
    if search_term:
        command.append(search_term)
    else:
        broad_filters = list(string.ascii_lowercase) + list(string.digits)
        broad_filters.extend(['æ', 'ø', 'å']) # Add some common Nordic characters for broad filtering
        command.extend(broad_filters)
        
    command.extend(["--output", "json"])

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore',
            shell=True
        )
        stdout_data, stderr_data = process.communicate()

        logging.debug(f"dcli STDOUT (command: {' '.join(command)}):\n{stdout_data}")
        logging.debug(f"dcli STDERR (command: {' '.join(command)}):\n{stderr_data}")
        logging.info(f"dcli command Exit Code ({' '.join(command)}): {process.returncode}")

        if process.returncode != 0:
            error_message = f"dcli command failed with exit code {process.returncode}:\n{stderr_data.strip()}"
            if "authentication required" in stderr_data.lower() or "not logged in" in stderr_data.lower():
                root.after(0, lambda: handle_error_in_thread(
                    "Authentication Required",
                    "dcli is not authenticated. Please ensure you have an active `dcli` session. "
                    "You may need to interact with the Dashlane desktop app or browser extension "
                    "to ensure dcli is fully authenticated.",
                    show_login_button=True
                ))
            elif "2fa" in stderr_data.lower() or "two-factor" in stderr_data.lower():
                root.after(0, lambda: handle_error_in_thread(
                    "2FA Required",
                    "dcli is asking for your 2FA code. Please authenticate in the terminal.",
                    show_login_button=True
                ))
            else:
                root.after(0, lambda: handle_error_in_thread("dcli Error", error_message))
            return

        try:
            items = json.loads(stdout_data)
            
            unique_items = {item['id']: item for item in items}.values()
            unique_items_list = list(unique_items)

            logging.info(f"Command '{' '.join(command)}' returned {len(unique_items_list)} unique items.")
            
            root.after(0, lambda: populate_treeview(unique_items_list))
            root.after(0, lambda: update_status(f"Loaded {len(unique_items_list)} items. Ready.", 'info'))
            
        except json.JSONDecodeError as e:
            error_message = f"dcli command did not return valid JSON. Error: {e}\nOutput:\n{stdout_data.strip()}\nError:\n{stderr_data.strip()}"
            root.after(0, lambda: handle_error_in_thread("JSON Decode Error", error_message))
        except Exception as json_e:
            error_message = f"Error processing dcli JSON output: {str(json_e)}\nOutput:\n{stdout_data.strip()}"
            root.after(0, lambda: handle_error_in_thread("JSON Processing Error", error_message))

    except FileNotFoundError:
        error_message = "dcli not found. Make sure it's in your PATH."
        root.after(0, lambda: handle_error_in_thread("Error", error_message, 'error', show_login_button=True))
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        root.after(0, lambda: handle_error_in_thread("An unexpected error occurred", error_message, 'error'))
    finally:
        root.after(0, lambda: btn_refresh_list.config(state=tk.NORMAL))
        root.after(0, lambda: btn_view_details.config(state=tk.NORMAL if item_treeview.selection() else tk.DISABLED))


def populate_treeview(items_to_display):
    global CURRENTLY_DISPLAYED_ITEMS
    item_treeview.delete(*item_treeview.get_children())
    CURRENTLY_DISPLAYED_ITEMS = items_to_display

    for i, item in enumerate(items_to_display):
        title = item.get('title', 'No Title')
        login = item.get('login', 'No Login')
        
        item_type = "Login"
        if not item.get('password'):
            if item.get('note') is not None and item.get('note') != '':
                item_type = "Secure Note"
            elif any(key in item for key in ['firstName', 'lastName', 'birthDate', 'gender']):
                item_type = "Personal Info"
            elif any(key in item for key in ['address1', 'city', 'zipCode', 'country']):
                item_type = "Address"
            elif any(key in item for key in ['cardHolderName', 'cardNumber']):
                item_type = "Credit Card"
            elif any(key in item for key in ['licenseNumber', 'stateOfIssue']):
                item_type = "ID"
            elif item.get('website'):
                item_type = "Website Only"
                
            else:
                item_type = "Other"

        # Apply alternating row tags for potential future styling (e.g., striped rows)
        tag = "oddrow" if i % 2 == 0 else "evenrow"
        item_treeview.insert("", tk.END, text="", values=(title, login, item_type), tags=(str(i), tag))


def filter_treeview_items(event=None):
    search_term = entry_site_name.get().strip()
    
    if search_term:
        add_to_search_history(search_term)
        update_status(f"Searching Dashlane CLI for '{search_term}'...", 'info')
        threading.Thread(target=run_dcli_command_and_populate_treeview, args=(search_term,), daemon=True).start()
    else:
        threading.Thread(target=run_dcli_command_and_populate_treeview, args=("",), daemon=True).start()
        update_status("Attempting to load all accessible items.", 'info')


def clear_search_field():
    entry_site_name.set('')
    filter_treeview_items()
    update_status("Search field cleared. Attempting to load all accessible items.", 'info')
    logging.info("Search field cleared.")

def show_about_window():
    about_window = Toplevel(root)
    about_window.title("About Dashlane CLI GUI")
    about_window.transient(root)
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

def open_settings_window():
    settings_window = Toplevel(root)
    settings_window.title("Settings")
    settings_window.transient(root) # Make it appear on top of root
    settings_window.grab_set()     # Prevent interaction with other windows until closed

    settings_window.config(bg=DL_COLORS["dark_accent"])
    content_frame = ttk.Frame(settings_window, padding="15 15 15 15", style='DarkAccent.TFrame')
    content_frame.pack(fill=tk.BOTH, expand=True)

    # Clipboard Delay Setting
    ttk.Label(content_frame, text="Clipboard Clear Delay (seconds):", style='DarkAccent.TLabel').grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
    clipboard_delay_var = tk.StringVar(value=config['SETTINGS']['clipboard_clear_delay_seconds'])
    entry_clipboard_delay = ttk.Entry(content_frame, textvariable=clipboard_delay_var, width=10)
    entry_clipboard_delay.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)

    # Clear Search History Button
    ttk.Label(content_frame, text="Search History:", style='DarkAccent.TLabel').grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
    btn_clear_history = ttk.Button(content_frame, text="Clear Search History")
    btn_clear_history.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)

    def save_and_apply_settings():
        global CLIPBOARD_CLEAR_DELAY_SECONDS, SEARCH_HISTORY, _countdown_id

        try:
            new_delay = int(clipboard_delay_var.get())
            if new_delay < 0:
                messagebox.showwarning("Invalid Input", "Clipboard delay cannot be negative.")
                return

            config['SETTINGS']['clipboard_clear_delay_seconds'] = str(new_delay)
            CLIPBOARD_CLEAR_DELAY_SECONDS = new_delay
            logging.info(f"Clipboard clear delay set to {new_delay} seconds.")

            # If a clipboard countdown is currently active, restart it with the new delay
            if _countdown_id and _countdown_seconds_remaining > 0:
                root.after_cancel(_countdown_id)
                start_clipboard_countdown() # Restart the countdown with the new delay

            # Save the config file
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
            
            update_status("Settings saved and applied!", 'info')
            messagebox.showinfo("Settings Saved", "Settings have been saved and applied.")
            settings_window.destroy() # Close settings window on success

        except ValueError:
            messagebox.showerror("Invalid Input", "Clipboard clear delay must be a whole number.")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def perform_clear_search_history():
        nonlocal btn_clear_history # To reference the button within this function's scope
        response = messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all search history?")
        if response:
            SEARCH_HISTORY = []
            config['SETTINGS']['search_history'] = json.dumps(SEARCH_HISTORY)
            
            # Update the main combobox to reflect the cleared history
            entry_site_name['values'] = []
            entry_site_name.set('') 
            
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
            logging.info("Search history cleared.")
            update_status("Search history cleared!", 'info')
            messagebox.showinfo("History Cleared", "Search history has been cleared.")
            # No need to trigger a full list refresh for just clearing history
            
    btn_clear_history.config(command=perform_clear_search_history)

    # Action Buttons (Save/Cancel)
    button_frame = ttk.Frame(content_frame, style='DarkAccent.TFrame')
    button_frame.grid(row=2, column=0, columnspan=2, pady=15)

    btn_save = ttk.Button(button_frame, text="Save", command=save_and_apply_settings)
    btn_save.pack(side=tk.LEFT, padx=5)

    btn_cancel = ttk.Button(button_frame, text="Cancel", command=settings_window.destroy)
    btn_cancel.pack(side=tk.LEFT, padx=5)

    # Set protocol for window close button
    settings_window.protocol("WM_DELETE_WINDOW", lambda: settings_window.destroy())
    # Release grab when window is destroyed
    settings_window.bind("<Destroy>", lambda e: settings_window.grab_release())
    logging.info("Opened Settings window.")

def on_closing():
    try:
        config['SETTINGS']['window_x'] = str(root.winfo_x())
        config['SETTINGS']['window_y'] = str(root.winfo_y())
        config['SETTINGS']['window_width'] = str(root.winfo_width())
        config['SETTINGS']['window_height'] = str(root.winfo_height())
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        logging.info("Window geometry saved.")
    except Exception as e:
        logging.error(f"Error saving window geometry: {e}")

    root.destroy()
    sys.exit()

# --- END OF CORE GUI FUNCTIONS ---


# --- START OF GUI SETUP ---
root = tk.Tk()
root.title("Dashlane CLI GUI")

# Set the window icon
try:
    icon_path = os.path.join(os.path.dirname(__file__), 'bilde.png')
    if os.path.exists(icon_path):
        root.iconphoto(False, tk.PhotoImage(file=icon_path)) 
        logging.info(f"Application icon set from {icon_path}")
    else:
        logging.warning(f"Application icon file not found at {icon_path}. Skipping icon setting.")
except Exception as e:
    logging.error(f"Error setting application icon: {e}")


try:
    initial_x = int(config['SETTINGS']['window_x'])
    initial_y = int(config['SETTINGS']['window_y'])
    initial_width = int(config['SETTINGS']['window_width'])
    initial_height = int(config['SETTINGS']['window_height'])
    root.geometry(f"{initial_width}x{initial_height}+{initial_x}+{initial_y}")
    logging.info(f"Restored window geometry: {initial_width}x{initial_height}+{initial_x}+{initial_y}")
except Exception as e:
    logging.warning(f"Could not restore window geometry, using defaults. Error: {e}")
    root.geometry("600x500")

root.protocol("WM_DELETE_WINDOW", on_closing)

style = ttk.Style(root)
style.theme_use('clam') # 'clam' provides good base customization options for flat look

# --- General Style Configuration (Flat & Modern) ---
# Root window background and default TFrame background (e.g., main_container_frame)
root.config(bg=DL_COLORS["dark_accent"])
style.configure('TFrame', background=DL_COLORS["dark_accent"], borderwidth=0, relief='flat')
style.configure('DarkAccent.TFrame', background=DL_COLORS["dark_accent"], borderwidth=0, relief='flat')

# Labels with white text on dark background (e.g., headers, in details window)
style.configure('TLabel', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"])
style.configure('DarkAccent.TLabel', background=DL_COLORS["dark_accent"], foreground=DL_COLORS["text_light"])
style.configure('MainContent.TLabel', background=DL_COLORS["main_bg_light"], foreground=DL_COLORS["text_dark"])


# Entry and Combobox fields (input areas) will have white background, dark text
style.configure('TEntry',
                fieldbackground=DL_COLORS["input_bg"],
                foreground=DL_COLORS["text_dark"],
                borderwidth=1, # Small border for definition
                relief='solid', # Solid border for definition
                focusthickness=0, # No dotted focus outline
                focuscolor='none' # No focus color
                )

# Combobox Styling - for the dropdown arrow and overall appearance
style.configure('TCombobox',
                background=DL_COLORS["input_bg"], # Background of the entire combobox widget
                fieldbackground=DL_COLORS["input_bg"], # Background of the text input area
                foreground=DL_COLORS["text_dark"], # Text color
                selectbackground=DL_COLORS["input_bg"], # When text is selected in the input
                selectforeground=DL_COLORS["text_dark"], # Selected text color
                bordercolor=DL_COLORS["dark_accent"], # Border around the combobox
                darkcolor=DL_COLORS["dark_accent"], # For some separators/internal elements
                lightcolor=DL_COLORS["dark_accent"], # For some separators/internal elements
                insertcolor=DL_COLORS["text_dark"], # Cursor color
                padding=[5, 2], # Padding inside the combobox for a bit more space
                relief='solid', # Solid border for definition
                borderwidth=1, # Thin border
                focusthickness=0,
                focuscolor='none',
                arrowsize=12 # Adjust arrow size
                )
# Mapping for Combobox elements, especially the arrow's color and background
style.map('TCombobox',
          background=[('readonly', DL_COLORS["input_bg"]), ('disabled', DL_COLORS["input_bg"])],
          fieldbackground=[('readonly', DL_COLORS["input_bg"]), ('disabled', DL_COLORS["input_bg"])],
          foreground=[('readonly', DL_COLORS["text_dark"]), ('disabled', DL_COLORS["text_dark"])],
          arrowcolor=[('active', DL_COLORS["highlight_blue"]), ('!active', DL_COLORS["text_dark"])], # Arrow will be dark_text or highlight_blue
          bordercolor=[('focus', DL_COLORS["highlight_blue"])] # Blue border when focused
          )
# For the dropdown list itself (the pop-up list of history items)
style.configure("TCombobox.PopdownFrame", background=DL_COLORS["main_bg_light"], borderwidth=0)
style.configure("TCombobox.Listbox", background=DL_COLORS["main_bg_light"], foreground=DL_COLORS["text_dark"],
                selectbackground=DL_COLORS["highlight_blue"], selectforeground=DL_COLORS["text_light"],
                borderwidth=0, relief='flat')


# Buttons - Now WHITE with dark text!
style.configure('TButton',
                background=DL_COLORS["input_bg"], # Pure white button background
                foreground=DL_COLORS["text_dark"], # Dark text on white buttons
                font=('Arial', 10, 'bold'),
                borderwidth=0, # No border
                relief='flat', # Flat appearance
                padding=[10, 5], # More generous padding
                focusthickness=0, # No focus outline
                focuscolor='none' # No focus color
                )
style.map('TButton',
          background=[('active', DL_COLORS["button_light_hover"]), ('!active', DL_COLORS["input_bg"])], # Light grey on hover, white otherwise
          foreground=[('active', DL_COLORS["text_dark"]), ('!active', DL_COLORS["text_dark"])]) # Text remains dark


# --- Treeview Specific Styles ---
style.configure('Treeview.Heading',
                background=DL_COLORS["dark_accent"],
                foreground=DL_COLORS["text_light"],
                font=('Arial', 10, 'bold'),
                relief='flat', # Flat appearance
                padding=[5,5], # Add some padding to headings
                borderwidth=0 # No border for headings
                )
style.configure('Treeview',
                background=DL_COLORS["main_bg_light"], # Main list background (light grey)
                fieldbackground=DL_COLORS["main_bg_light"], # Background behind the rows
                foreground=DL_COLORS["text_dark"], # Default text color in rows
                rowheight=28, # Slightly taller rows for better spacing
                borderwidth=0,
                relief='flat'
                )
# Mapping for selected rows in Treeview - using highlight_blue
style.map('Treeview',
          background=[('selected', DL_COLORS["highlight_blue"])], # Selected row background (vibrant blue)
          foreground=[('selected', DL_COLORS["text_light"])]) # Selected row text color (white)


# --- Password Toggle Button Style (Details Window) ---
style.configure('PasswordToggle.TCheckbutton',
                background=DL_COLORS["dark_accent"], # Match details window background
                foreground=DL_COLORS["text_light"], # White text by default
                font=('Arial', 9), padding=(0,0,0,0),
                focusthickness=0, focuscolor='none')
style.map('PasswordToggle.TCheckbutton',
          background=[('active', DL_COLORS["dark_accent"]), ('!active', DL_COLORS["dark_accent"])],
          foreground=[('selected', DL_COLORS["highlight_blue"]), ('!selected', DL_COLORS["text_light"])]) # Blue when "Show Password" is checked, white when hidden


# --- Scrollbar Styling (Simpler, more subtle) ---
# Vertical scrollbar
style.configure("Vertical.TScrollbar",
                troughcolor=DL_COLORS["main_bg_light"], # The track behind the thumb - light gray
                background=DL_COLORS["scrollbar_thumb_light"], # The scrollbar thumb color - slightly darker light gray
                bordercolor=DL_COLORS["main_bg_light"], # Border around the thumb matches trough for flat look
                arrowcolor=DL_COLORS["text_dark"], # Color of the arrows in the buttons - dark
                relief='flat', # Flat appearance
                borderwidth=0, # No border
                arrowsize=10 # Slightly smaller arrows for subtlety
                )
style.map("Vertical.TScrollbar",
          background=[('active', DL_COLORS["dark_accent"])], # Thumb dark on hover
          arrowcolor=[('active', DL_COLORS["highlight_blue"])]) # Blue arrows on hover

# Horizontal scrollbar (if any, although not used currently, good for completeness)
style.configure("Horizontal.TScrollbar",
                troughcolor=DL_COLORS["main_bg_light"],
                background=DL_COLORS["scrollbar_thumb_light"],
                bordercolor=DL_COLORS["main_bg_light"],
                arrowcolor=DL_COLORS["text_dark"],
                relief='flat',
                borderwidth=0,
                arrowsize=10
                )
style.map("Horizontal.TScrollbar",
          background=[('active', DL_COLORS["dark_accent"])],
          arrowcolor=[('active', DL_COLORS["highlight_blue"])])


# --- Menubar Setup ---
menubar = tk.Menu(root)
root.config(menu=menubar)

file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Settings...", command=open_settings_window)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=on_closing)

help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="About", command=show_about_window)


# Main container for the search bar and treeview. This will be light gray.
# Its background will now be explicitly set to main_bg_light.
main_container_frame = ttk.Frame(root, padding="15 15 15 15", style='MainContent.TFrame')
main_container_frame.pack(fill=tk.BOTH, expand=True)

search_frame = ttk.Frame(main_container_frame, style='MainContent.TFrame')
search_frame.pack(fill=tk.X, pady=(0, 10))

ttk.Label(search_frame, text="Filter by Title/Login:", style='MainContent.TLabel').pack(side=tk.LEFT, padx=(0, 5))

entry_site_name = ttk.Combobox(search_frame, width=40, values=SEARCH_HISTORY)
entry_site_name.pack(side=tk.LEFT, expand=True, fill=tk.X)
entry_site_name.set(SEARCH_HISTORY[0] if SEARCH_HISTORY else '')
entry_site_name.focus_set()
entry_site_name.bind('<KeyRelease>', filter_treeview_items)
entry_site_name.bind('<<ComboboxSelected>>', filter_treeview_items)

clear_button = ttk.Button(search_frame, text="X", width=3, command=clear_search_field)
clear_button.pack(side=tk.LEFT, padx=(5,0))

treeview_frame = ttk.Frame(main_container_frame, style='MainContent.TFrame')
treeview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

columns = ('Title', 'Login', 'Type')
item_treeview = ttk.Treeview(treeview_frame, columns=columns, show='headings')

item_treeview.heading('Title', text='Title', anchor=tk.W, command=lambda: treeview_sort_column('Title'))
item_treeview.heading('Login', text='Login', anchor=tk.W, command=lambda: treeview_sort_column('Login'))
item_treeview.heading('Type', text='Type', anchor=tk.W, command=lambda: treeview_sort_column('Type'))


item_treeview.column('Title', width=200, minwidth=150)
item_treeview.column('Login', width=150, minwidth=100)
item_treeview.column('Type', width=100, minwidth=80)

item_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

treeview_scrollbar = ttk.Scrollbar(treeview_frame, orient=tk.VERTICAL, command=item_treeview.yview, style="Vertical.TScrollbar") # Apply specific style
item_treeview.configure(yscrollcommand=treeview_scrollbar.set)
treeview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

item_treeview.bind('<<TreeviewSelect>>', on_item_select_from_list)
item_treeview.bind('<Double-1>', lambda event: view_selected_item_details())


action_buttons_frame = ttk.Frame(main_container_frame, style='MainContent.TFrame')
action_buttons_frame.pack(pady=5)

btn_view_details = ttk.Button(action_buttons_frame, text="View Details", command=view_selected_item_details, state=tk.DISABLED)
btn_view_details.pack(side=tk.LEFT, padx=5)

btn_refresh_list = ttk.Button(action_buttons_frame, text="Refresh List", command=lambda: threading.Thread(target=run_dcli_command_and_populate_treeview, args=("",), daemon=True).start())
btn_refresh_list.pack(side=tk.LEFT, padx=5)


# --- Status Bar Style ---
# Directly configure the style using its string name
style.configure('Status.TLabel',
                background=DL_COLORS["dark_accent"], # Status bar is dark
                foreground=DL_COLORS["text_light"], # Default text is white
                relief=tk.FLAT, # Flat look for status bar
                padding=[5,2])

# Now create the status_label using the defined style name
status_label = ttk.Label(root, text="Ready.", relief=tk.FLAT, anchor=tk.W, style='Status.TLabel')
status_label.pack(side=tk.BOTTOM, fill=tk.X, ipady=2)


update_status("Initializing...", 'info')

root.after(100, lambda: threading.Thread(target=run_dcli_command_and_populate_treeview, args=("",), daemon=True).start())

root.mainloop()
# --- END OF GUI SETUP ---