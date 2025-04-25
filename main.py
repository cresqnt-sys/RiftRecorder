import sys
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QFileDialog, QCheckBox, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from threading import Thread
import json
import keyboard
import mouse
from recorder_thread import thread

# Copied from recorder_main.py
class BGSI_Recorder:
    def __init__(self, recorded: dict = None, stop_key: str = 'esc'):
        self.start_time = None
        self.stop_recording_flag = False
        self.play_start_time = None
        self.is_playing = False
        self.speed_factor = 1
        self.stop_key = stop_key

        self.recorded = recorded if recorded else {
            'keyboard': [],
            'mouse': []
        }

    def record(self, countdown: float = 0.001):
        self.start_time = time.time() + countdown
        # Start listeners in separate threads to avoid blocking
        mouse_listener_thread = Thread(target=self.mouse_listener)
        keyboard_listener_thread = Thread(target=self.keyboard_listener)

        mouse_listener_thread.start()
        keyboard_listener_thread.start()

        # Wait for threads to potentially finish (e.g., if stop is called quickly)
        # This might need adjustment depending on desired behavior on stop
        keyboard_listener_thread.join() # keyboard_listener blocks until stop_key or flag
        # mouse listener runs until unhooked by stop_recording
        mouse_listener_thread.join() # Wait for mouse listener to finish after unhook


    def play(self, countdown: float = 0.001, speed_factor: float = 1, only_essential_moves: bool = False):
        self.is_playing = True

        if speed_factor > 5:
            speed_factor = 5

        if only_essential_moves:
            self.filter_moves()

        self.speed_factor = speed_factor
        self.play_start_time = time.time() + countdown

        mouse_ = Thread(target=self.play_mouse, args=(self.recorded['mouse'],))
        keyboard_ = Thread(target=self.play_keyboard, args=(self.recorded['keyboard'],))
        # Stop listener needs to run in the background
        stop_thread = Thread(target=self.stop_player_listener)
        stop_thread.daemon = True # Allow program to exit even if this thread is running
        stop_thread.start()


        mouse_.start()
        keyboard_.start()
        mouse_.join()
        keyboard_.join()

        self.is_playing = False # Ensure flag is reset after playback finishes naturally

    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.recorded, f, indent=4)

    def load(self, path: str):
        with open(path, 'r') as f:
            self.recorded = json.load(f)

    def keyboard_listener(self):
        self.wait_to_start(self.start_time)
        print(f"Keyboard listener started. Press '{self.stop_key}' to stop recording.")

        # Define the hook callback function
        def on_key_event(event: keyboard.KeyboardEvent):
            # Prevent processing if recording stopped between event and callback
            if self.stop_recording_flag:
                return
            
            # Check for stop key
            if event.name == self.stop_key and event.event_type == keyboard.KEY_DOWN:
                print(f"'{self.stop_key}' pressed. Stopping recording.")
                self.stop_recording() # This will set flag and unhook
                return # Don't record the stop key itself

            # Record event relative to start time
            # Ensure recording has actually started
            if self.start_time is not None and event.time >= self.start_time:
                 timestamp = event.time - self.start_time
                 print(f"  Recording KB Event: ['{event.event_type == keyboard.KEY_DOWN}', '{event.name}', {timestamp:.4f}]")
                 self.recorded['keyboard'].append([
                      event.event_type == keyboard.KEY_DOWN,
                      event.name,
                      timestamp
                 ])

        try:
            # Hook the callback
            keyboard.hook(on_key_event)
            # Keep the listener thread alive until stop_recording is called
            while not self.stop_recording_flag:
                time.sleep(0.1) # Prevent busy-waiting
        except Exception as e:
            print(f"Error in keyboard listener: {e}")
        finally:
            # Ensure the hook is removed if the thread exits unexpectedly,
            # though stop_recording should normally handle it.
            try:
                 keyboard.unhook(on_key_event)
            except Exception as e:
                 pass
            print("Keyboard listener finished.")


    # Mouse listener needs to run until unhooked
    def mouse_listener(self):
        self.wait_to_start(self.start_time)
        print("Mouse listener started.")
        try:
            mouse.hook(self.on_callback)
            # Keep the listener thread alive until unhooked.
            # A simple way is to wait for the stop flag.
            while not self.stop_recording_flag:
                time.sleep(0.1) # Prevent busy-waiting
        except Exception as e:
             print(f"Error setting up mouse hook: {e}") # May need admin rights
        finally:
             print("Mouse listener finished.")


    def on_callback(self, event):
        # Should check if recording has actually started
        if self.start_time is None or time.time() < self.start_time:
             return
        # Also check stop flag in case events arrive after stop_recording is called
        if self.stop_recording_flag:
             return

        timestamp = time.time() - self.start_time

        if isinstance(event, mouse.MoveEvent):
            self.recorded['mouse'].append(['move', event.x, event.y, timestamp])

        elif isinstance(event, mouse.ButtonEvent):
            self.recorded['mouse'].append(['click', event.button, event.event_type == 'down', timestamp])

        elif isinstance(event, mouse.WheelEvent):
            self.recorded['mouse'].append(['scroll', event.delta, timestamp])

        # Removed 'else: print unknown' as it's not needed

    def stop_recording(self):
        # This function might be called from the keyboard hook or the UI thread
        if not self.stop_recording_flag: # Prevent multiple calls
            print("Executing stop_recording...")
            self.stop_recording_flag = True # Set flag first
            
            # Unhook mouse and keyboard listeners
            try:
                mouse.unhook(self.on_callback)
                print("Mouse unhooked.")
            except Exception as e:
                print(f"Warning: Error unhooking mouse: {e}")
            try:
                # Unhook all keyboard hooks - includes the one set by keyboard_listener
                # and potentially the one by stop_player_listener if somehow active.
                keyboard.unhook_all()
                print("All keyboard hooks removed.")
            except Exception as e:
                 print(f"Warning: Error unhooking keyboard: {e}")

            # Short delay might not be necessary anymore, but can leave it
            time.sleep(0.1)
            print("stop_recording finished.")
            return self.recorded


    def play_keyboard(self, key_events: list):
        print("play_keyboard started.")
        self.wait_to_start(self.play_start_time)
        print("play_keyboard wait finished.")

        for i, key in enumerate(key_events):
            if not self.is_playing: # Check before processing event
                print(f"play_keyboard: Stopping playback early (event {i}).")
                break
                
            pressed, scan_code, t = key
            
            # Calculate adjusted time based on speed factor
            adjusted_time = t / self.speed_factor
            current_playback_time = time.time() - self.play_start_time
            time_to_wait = adjusted_time - current_playback_time

            print(f"  KB Play Event {i}: Data={key}, Orig_t={t:.4f}, Adj_t={adjusted_time:.4f}, Wait={time_to_wait:.4f}")

            if time_to_wait > 0:
                time.sleep(time_to_wait)

            if not self.is_playing: # Check flag again after sleep
                print(f"play_keyboard: Stopping playback early after sleep (event {i}).")
                break

            try:
                action_str = "Press" if pressed else "Release"
                print(f"    -> {action_str} '{scan_code}'")
                if pressed:
                    keyboard.press(scan_code)
                else:
                    keyboard.release(scan_code)
            except Exception as e:
                print(f"Error playing keyboard event ({action_str} {scan_code}): {e}")
        
        print("play_keyboard finished.")


    def play_mouse(self, mouse_events: list):
        self.wait_to_start(self.play_start_time)

        for mouse_event in mouse_events:
            event_type, *args, t = mouse_event

            # Calculate adjusted time based on speed factor
            adjusted_time = t / self.speed_factor
            current_playback_time = time.time() - self.play_start_time
            time_to_wait = adjusted_time - current_playback_time

            if time_to_wait > 0:
                time.sleep(time_to_wait)

            if not self.is_playing: # Check flag before action and after sleep
                break

            try:
                if event_type == 'move':
                    mouse.move(*args)
                elif event_type == 'click':
                    button, is_press = args
                    if is_press:
                        mouse.press(button)
                    else:
                        mouse.release(button)
                elif event_type == 'scroll':
                    delta = args[0]
                    mouse.wheel(delta)
            except Exception as e:
                 print(f"Error playing mouse event ({event_type} {args}): {e}")


    @staticmethod
    def wait_to_start(t: float):
        time_to_sleep = t - time.time()
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)

    # Sleep method used during playback - adjust timing precisely
    # This is replaced by direct calculation in play methods now.
    # def sleep(self, t: float):
    #    time_to_sleep = t - (time.time() - self.play_start_time)
    #    if time_to_sleep > 0:
    #        time.sleep(time_to_sleep)


    # Renamed from stop_player to avoid conflict/confusion
    # This method listens for the stop key during playback
    def stop_player_listener(self):
        print(f"Playback stop listener started. Press '{self.stop_key}' to stop.")
        keyboard.wait(self.stop_key)
        if self.is_playing:
             print(f"'{self.stop_key}' pressed during playback. Stopping player...")
             self.is_playing = False # Set flag to stop playback loops

    def filter_moves(self):
        if not self.recorded['mouse']:
            return

        filtered_moves = []
        last_event = None

        # Always keep the first event if it's a move
        if self.recorded['mouse'][0][0] == 'move':
             filtered_moves.append(self.recorded['mouse'][0])
             last_event = self.recorded['mouse'][0]
             start_index = 1
        else:
             start_index = 0


        for i in range(start_index, len(self.recorded['mouse'])):
            current_event = self.recorded['mouse'][i]

            # If current is not a move, keep it
            if current_event[0] != 'move':
                # If the *previous* event was a move, keep that *last* move event
                if last_event and last_event[0] == 'move':
                    # Avoid adding duplicate non-move events if last_event was also non-move
                    if not filtered_moves or filtered_moves[-1] != last_event:
                         filtered_moves.append(last_event)

                # Keep the current non-move event
                filtered_moves.append(current_event)

            # Update last_event regardless of type
            last_event = current_event

        # Ensure the very last event is added if it was a move and loop finished
        if last_event and last_event[0] == 'move':
             if not filtered_moves or filtered_moves[-1] != last_event:
                  filtered_moves.append(last_event)


        print(f"Filtered mouse events from {len(self.recorded['mouse'])} to {len(filtered_moves)}")
        self.recorded['mouse'] = filtered_moves
# End of copied code

# Worker signal class
class WorkerSignals(QObject):
    finished = pyqtSignal()
    status_update = pyqtSignal(str)

# Worker class to run recorder/player in a separate thread
class RecorderWorker(QObject):
    def __init__(self, recorder: BGSI_Recorder, action: str, **kwargs):
        super().__init__()
        self.recorder = recorder
        self.action = action
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            if self.action == 'record':
                self.signals.status_update.emit(f"Recording starts in {self.kwargs.get('countdown', 0)}s...")
                self.recorder.record(**self.kwargs)
                print("--- Recording Finished ---")
                print("Recorded Keyboard Events:")
                for event in self.recorder.recorded['keyboard']:
                    print(f"  {event}")
                print("Recorded Mouse Events:")
                print(f"  ({len(self.recorder.recorded['mouse'])} mouse events)") 
                print("-------------------------")
                self.signals.status_update.emit("Recording finished.")
            elif self.action == 'play':
                self.signals.status_update.emit(f"Playback starts in {self.kwargs.get('countdown', 0)}s...")
                print("--- Starting Playback ---")
                print("Playing Keyboard Events:")
                for event in self.recorder.recorded['keyboard']:
                    print(f"  {event}")
                print("Playing Mouse Events:")
                print(f"  ({len(self.recorder.recorded['mouse'])} mouse events)") 
                print("-------------------------")
                self.recorder.play(**self.kwargs)
                self.signals.status_update.emit("Playback finished.")
        except Exception as e:
            self.signals.status_update.emit(f"Error: {e}")
        finally:
            self.signals.finished.emit()


class RecorderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.recorder = BGSI_Recorder()
        self.worker_thread = None
        self.worker = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('RiftRecorder')

        layout = QVBoxLayout()

        # --- Controls ---
        controls_layout = QHBoxLayout()
        self.record_btn = QPushButton('Record')
        self.play_btn = QPushButton('Play')
        self.stop_btn = QPushButton('Stop')
        self.save_btn = QPushButton('Save')
        self.load_btn = QPushButton('Load')

        self.record_btn.clicked.connect(self.start_recording)
        self.play_btn.clicked.connect(self.start_playback)
        self.stop_btn.clicked.connect(self.stop_action)
        self.save_btn.clicked.connect(self.save_recording)
        self.load_btn.clicked.connect(self.load_recording)

        self.stop_btn.setEnabled(False) # Initially disabled

        controls_layout.addWidget(self.record_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.save_btn)
        controls_layout.addWidget(self.load_btn)
        layout.addLayout(controls_layout)

        # --- Options ---
        options_layout = QHBoxLayout()
        self.countdown_label = QLabel('Start Countdown (s):')
        self.countdown_spinbox = QDoubleSpinBox()
        self.countdown_spinbox.setRange(0, 60)
        self.countdown_spinbox.setValue(0.001)
        self.countdown_spinbox.setSingleStep(0.1)

        self.speed_label = QLabel('Playback Speed:')
        self.speed_spinbox = QDoubleSpinBox()
        self.speed_spinbox.setRange(0.1, 5)
        self.speed_spinbox.setValue(1)
        self.speed_spinbox.setSingleStep(0.1)

        self.essential_moves_checkbox = QCheckBox('Only Essential Moves')

        options_layout.addWidget(self.countdown_label)
        options_layout.addWidget(self.countdown_spinbox)
        options_layout.addWidget(self.speed_label)
        options_layout.addWidget(self.speed_spinbox)
        options_layout.addWidget(self.essential_moves_checkbox)
        layout.addLayout(options_layout)

        # --- Status ---
        self.status_label = QLabel('Status: Idle')
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")

    def start_recording(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.update_status("Action already in progress.")
            return

        countdown = self.countdown_spinbox.value()
        self.recorder = BGSI_Recorder(stop_key='esc') # Reset recorder instance

        self.worker = RecorderWorker(self.recorder, 'record', countdown=countdown)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker.signals.status_update.connect(self.update_status)
        self.worker.signals.finished.connect(self.on_worker_finished)
        self.worker_thread.started.connect(self.worker.run)

        self.set_controls_enabled(False)
        self.stop_btn.setEnabled(True)
        self.update_status("Initializing recording...")
        self.worker_thread.start()


    def start_playback(self):
        if not self.recorder.recorded['keyboard'] and not self.recorder.recorded['mouse']:
             self.update_status("No recording loaded or recorded yet.")
             return

        if self.worker_thread and self.worker_thread.isRunning():
            self.update_status("Action already in progress.")
            return

        countdown = self.countdown_spinbox.value()
        speed_factor = self.speed_spinbox.value()
        only_essential = self.essential_moves_checkbox.isChecked()

        # Need to create a *new* recorder instance for playback based on the loaded data
        # because the original recorder might be tied to the recording thread/hooks
        playback_recorder = BGSI_Recorder(recorded=self.recorder.recorded, stop_key='esc')


        self.worker = RecorderWorker(playback_recorder, 'play', countdown=countdown, speed_factor=speed_factor, only_essential_moves=only_essential)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker.signals.status_update.connect(self.update_status)
        self.worker.signals.finished.connect(self.on_worker_finished)
        self.worker_thread.started.connect(self.worker.run)

        self.set_controls_enabled(False)
        self.stop_btn.setEnabled(True)
        self.update_status("Initializing playback...")
        self.worker_thread.start()


    def stop_action(self):
        print("Stop button clicked or action initiated.")
        if self.worker and self.worker_thread and self.worker_thread.isRunning():
            recorder_instance = self.worker.recorder
            if self.worker.action == 'record' and hasattr(recorder_instance, 'stop_recording'):
                print("Requesting stop recording...")
                recorder_instance.stop_recording() # Signal the recorder thread to stop

            elif self.worker.action == 'play' and hasattr(recorder_instance, 'is_playing'):
                 print("Requesting stop playback...")
                 recorder_instance.is_playing = False # Signal the player to stop
            else:
                 print("No active record/play action found in worker to stop.")
        else:
             print("No worker thread running to stop.")

        self.update_status("Stop requested.")
        # UI controls will be re-enabled by on_worker_finished when the worker thread actually exits.

    def on_worker_finished(self):
        self.update_status("Idle")
        self.set_controls_enabled(True)
        self.stop_btn.setEnabled(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
        self.worker_thread = None
        self.worker = None


    def set_controls_enabled(self, enabled):
        self.record_btn.setEnabled(enabled)
        self.play_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.load_btn.setEnabled(enabled)
        self.countdown_spinbox.setEnabled(enabled)
        self.speed_spinbox.setEnabled(enabled)
        self.essential_moves_checkbox.setEnabled(enabled)
        # Stop button handled separately


    def save_recording(self):
        if not self.recorder.recorded['keyboard'] and not self.recorder.recorded['mouse']:
             self.update_status("No recording data to save.")
             return

        path, _ = QFileDialog.getSaveFileName(self, 'Save Recording', '', 'JSON Files (*.json)')
        if path:
            try:
                self.recorder.save(path)
                self.update_status(f"Recording saved to {path}")
            except Exception as e:
                self.update_status(f"Error saving file: {e}")

    def load_recording(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.update_status("Cannot load while an action is in progress.")
            return

        path, _ = QFileDialog.getOpenFileName(self, 'Load Recording', '', 'JSON Files (*.json)')
        if path:
            try:
                # Create a new recorder instance to load into, preserving the original if needed
                self.recorder = BGSI_Recorder()
                self.recorder.load(path)
                self.update_status(f"Recording loaded from {path}")
            except Exception as e:
                self.update_status(f"Error loading file: {e}")

    def closeEvent(self, event):
        # Ensure threads are stopped on close
        self.stop_action()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(500) # Short wait
            if self.worker_thread.isRunning():
                self.worker_thread.terminate() # Force if needed
                self.worker_thread.wait()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = RecorderUI()
    ex.show()
    sys.exit(app.exec()) 