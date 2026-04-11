import os
import sys
import time
import shutil
import subprocess

def main():
    if len(sys.argv) < 3:
        print("Usage: updater_helper.py <current_exe> <new_exe>")
        return

    current_exe = os.path.abspath(sys.argv[1])
    new_exe = os.path.abspath(sys.argv[2])

    print(f"Updater helper started.\nReplacing:\n  {current_exe}\nwith:\n  {new_exe}")

    # Wait for the main EXE to exit (max 60s)
    max_wait = 60
    waited = 0
    while True:
        try:
            # Try opening file for writing to check if locked
            with open(current_exe, 'a'):
                break
        except Exception:
            time.sleep(0.5)
            waited += 0.5
            if waited >= max_wait:
                print("Timeout waiting for main EXE to exit.")
                return

    # Replace old EXE
    try:
        shutil.move(new_exe, current_exe)
        print(f"Replaced {current_exe} successfully.")
    except Exception as e:
        print(f"Error replacing EXE: {e}")
        return

    # Relaunch the updated EXE
    try:
        subprocess.Popen([current_exe])
        print("Relaunched updated EXE successfully.")
    except Exception as e:
        print(f"Error relaunching EXE: {e}")

if __name__ == "__main__":
    main()