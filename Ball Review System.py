# Ball Review System
# Continuously records video and saves/emails recording when key is pressed

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import threading
import subprocess

# Email configuration - Update these with your email credentials
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "rutvikdeshpande11@gmail.com"
SENDER_PASSWORD = "vpch toji olin pfsc"
RECIPIENT_EMAIL = "rutvikdeshpande11@gmail.com"

# Configuration
recordings_folder = "ball_review_recordings"  # Folder to save recordings
fps_target = 30  # Target FPS for recording
SAVE_KEY = ord('s')  # Press 's' to save and send recording
QUIT_KEY = ord('q')  # Press 'q' to quit

# Recording buffer settings (seconds to keep before save key press)
RECORDING_BUFFER_SECONDS = 10  # Keep last 10 seconds before save
MAX_RECORDING_DURATION = 60  # Maximum recording duration per file (seconds)

# Create recordings folder if it doesn't exist
if not os.path.exists(recordings_folder):
    os.makedirs(recordings_folder)

# Initialize the camera
print("[INFO] Initializing camera...")
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (1920, 1080)}))
picam2.start()
time.sleep(2)  # Allow camera to warm up

# Global state variables
is_recording = False
camera_writer = None
recording_start_time = None
current_recording_path = None
frame_width = 1920
frame_height = 1080
recording_lock = threading.Lock()
frame_buffer = []  # Circular buffer for recent frames
buffer_max_frames = RECORDING_BUFFER_SECONDS * fps_target
save_requested = False

def start_recording():
    """Start recording camera"""
    global is_recording, camera_writer, recording_start_time, current_recording_path, frame_buffer
    
    with recording_lock:
        if is_recording:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recording_filename = f"ball_review_{timestamp}.mp4"
        current_recording_path = os.path.join(recordings_folder, recording_filename)
        
        # Initialize camera video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        camera_writer = cv2.VideoWriter(current_recording_path, fourcc, fps_target, (frame_width, frame_height))
        
        # Clear frame buffer
        frame_buffer = []
        
        recording_start_time = datetime.now()
        is_recording = True
        print(f"[INFO] Recording started: {recording_filename}")
        print(f"[INFO] Press '{chr(SAVE_KEY)}' to save and email recording, '{chr(QUIT_KEY)}' to quit")

def add_frame_to_buffer(frame):
    """Add frame to circular buffer"""
    global frame_buffer, buffer_max_frames
    
    # Convert frame to BGR for storage
    if len(frame.shape) == 3 and frame.shape[2] == 4:  # XRGB8888 format
        try:
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        except:
            rgb_frame = frame[:, :, 1:4].copy()
            bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
    elif len(frame.shape) == 3 and frame.shape[2] == 3:
        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    else:
        bgr_frame = frame.copy()
    
    frame_buffer.append(bgr_frame.copy())
    
    # Maintain buffer size
    if len(frame_buffer) > buffer_max_frames:
        frame_buffer.pop(0)

def save_buffer_to_video(output_path):
    """Save frame buffer to video file"""
    if len(frame_buffer) == 0:
        print("[WARNING] Frame buffer is empty, cannot save video")
        return False
    
    print(f"[INFO] Saving {len(frame_buffer)} frames to video...")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    temp_writer = cv2.VideoWriter(output_path, fourcc, fps_target, (frame_width, frame_height))
    
    for frame in frame_buffer:
        # Add timestamp to frame
        current_time = datetime.now()
        timestamp_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        color = (0, 255, 0)
        
        (text_width, text_height), baseline = cv2.getTextSize(timestamp_str, font, font_scale, thickness)
        
        # Draw semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (20 + text_width, 40 + text_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Draw timestamp
        cv2.putText(frame, timestamp_str, (15, 35), font, font_scale, color, thickness)
        
        temp_writer.write(frame)
    
    temp_writer.release()
    print(f"[INFO] Buffer video saved: {output_path}")
    return True

def stop_and_save_recording():
    """Stop current recording, save buffer, and prepare for email"""
    global is_recording, camera_writer, current_recording_path, recording_start_time, save_requested
    
    with recording_lock:
        if not is_recording:
            return None
        
        save_requested = True
        
        # Create timestamp for saved video
        save_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_video_filename = f"ball_review_saved_{save_timestamp}.mp4"
        saved_video_path = os.path.join(recordings_folder, saved_video_filename)
        
        # Save current recording if it exists
        current_video_path = None
        if camera_writer is not None and current_recording_path and os.path.exists(current_recording_path):
            camera_writer.release()
            camera_writer = None
            
            # Check if file has content
            if os.path.getsize(current_recording_path) > 0:
                current_video_path = current_recording_path
                print(f"[INFO] Current recording saved: {current_recording_path}")
        
        # Also save buffer (last few seconds)
        buffer_video_path = None
        if len(frame_buffer) > 0:
            buffer_filename = f"ball_review_buffer_{save_timestamp}.mp4"
            buffer_video_path = os.path.join(recordings_folder, buffer_filename)
            if save_buffer_to_video(buffer_video_path):
                buffer_video_path = buffer_video_path
        
        # Restart recording immediately
        start_time = recording_start_time
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recording_filename = f"ball_review_{timestamp}.mp4"
        current_recording_path = os.path.join(recordings_folder, recording_filename)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        camera_writer = cv2.VideoWriter(current_recording_path, fourcc, fps_target, (frame_width, frame_height))
        recording_start_time = datetime.now()
        
        save_requested = False
        
        # Return the video to send (prefer current recording, fallback to buffer)
        video_to_send = current_video_path if current_video_path else buffer_video_path
        
        return video_to_send, start_time

def convert_video_to_h264(input_path, output_path):
    """Convert video to H.264 format compatible with email clients"""
    try:
        if not os.path.exists(input_path):
            print(f"[ERROR] Input video does not exist: {input_path}")
            return False
        
        print(f"[INFO] Converting video to H.264 format...")
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-c:v', 'libx264', '-preset', 'medium',
            '-crf', '23', '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"[INFO] Video converted successfully: {output_path}")
            return True
        else:
            print(f"[WARNING] Video conversion failed")
            return False
    except Exception as e:
        print(f"[ERROR] Video conversion error: {str(e)}")
        return False

def send_recording_email(video_path, start_time):
    """Send recording via email"""
    print(f"[INFO] Preparing to send email with recording...")
    print(f"[INFO] Video path: {video_path}")
    
    try:
        if not os.path.exists(video_path):
            print(f"[ERROR] Video file does not exist: {video_path}")
            return False
        
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
        print(f"[INFO] Video file size: {file_size:.2f} MB")
        
        if file_size == 0:
            print(f"[ERROR] Video file is empty (0 bytes). Cannot send email.")
            return False
        
        # Gmail has a 25MB attachment limit
        if file_size > 20:
            print(f"[WARNING] Video file is large ({file_size:.2f} MB). Email may fail.")
        
        # Convert to H.264 if not already
        base_name = os.path.splitext(video_path)[0]
        converted_path = f"{base_name}_h264.mp4"
        
        if convert_video_to_h264(video_path, converted_path):
            final_video_path = converted_path
        else:
            print("[WARNING] Conversion failed, trying to send original video")
            final_video_path = video_path
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        
        timestamp_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        msg['Subject'] = f"Ball Review Recording - {timestamp_str}"
        
        # Email body
        duration = (datetime.now() - start_time).total_seconds()
        body = f"""Ball Review Recording

A recording has been saved and sent.

Recording Time: {timestamp_str}
Recording Duration: {duration:.2f} seconds

The video recording is attached to this email.

This is an automated message from the Ball Review System.
"""
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach video file
        print(f"[INFO] Attaching video file: {os.path.basename(final_video_path)}")
        with open(final_video_path, 'rb') as f:
            part = MIMEBase('video', 'mp4')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(final_video_path)}'
            )
            msg.attach(part)
        
        # Send email
        print(f"[INFO] Connecting to SMTP server: {SMTP_SERVER}:{SMTP_PORT}")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        print(f"[INFO] Logging in to email account...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        print(f"[INFO] Sending email to {RECIPIENT_EMAIL}...")
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, text)
        server.quit()
        
        print(f"[INFO] Email sent successfully to {RECIPIENT_EMAIL}")
        
        # Clean up converted file if it's different from original
        if final_video_path != video_path and os.path.exists(final_video_path):
            try:
                os.remove(final_video_path)
            except:
                pass
        
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Authentication failed. Please check your email and password.")
        print(f"[ERROR] Details: {str(e)}")
        print(f"[INFO] For Gmail, you need to use an App Password, not your regular password.")
        print(f"[INFO] Generate one at: https://myaccount.google.com/apppasswords")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error occurred: {str(e)}")
        return False
    except FileNotFoundError as e:
        print(f"[ERROR] Video file not found: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to send email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def process_and_send_recording(video_path, start_time):
    """Process video and send email in background thread"""
    try:
        print(f"[INFO] Processing and sending recording in background...")
        email_sent = send_recording_email(video_path, start_time)
        if email_sent:
            print(f"[SUCCESS] Email sent successfully! Video was sent to {RECIPIENT_EMAIL}")
            # Optionally remove original file to save space (keep it for now)
            # try:
            #     os.remove(video_path)
            # except:
            #     pass
        else:
            print(f"[ERROR] Email sending failed. Video saved at: {video_path}")
    except Exception as e:
        print(f"[ERROR] Error processing recording: {str(e)}")
        import traceback
        traceback.print_exc()

def cleanup():
    """Cleanup resources"""
    global camera_writer, is_recording
    
    print("[INFO] Cleaning up...")
    
    if is_recording and camera_writer is not None:
        camera_writer.release()
        camera_writer = None
    
    cv2.destroyAllWindows()
    picam2.stop()

# Register cleanup on exit
import atexit
atexit.register(cleanup)

# Main loop
print("[INFO] Ball Review System started")
print("[INFO] Starting continuous recording...")
print(f"[INFO] Press '{chr(SAVE_KEY)}' to save and email recording, '{chr(QUIT_KEY)}' to quit")

# Start recording immediately
start_recording()

frame_count = 0
start_time = time.time()
fps = 0

try:
    while True:
        # Capture frame from camera
        frame = picam2.capture_array()
        
        # Add frame to buffer
        add_frame_to_buffer(frame)
        
        # Record frame if recording
        display_frame = frame.copy()
        
        if is_recording and camera_writer is not None and not save_requested:
            # Convert frame to BGR for video writer
            if len(frame.shape) == 3 and frame.shape[2] == 4:  # XRGB8888 format
                try:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                except:
                    rgb_frame = frame[:, :, 1:4].copy()
                    bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
            elif len(frame.shape) == 3 and frame.shape[2] == 3:
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                bgr_frame = frame.copy()
            
            # Add timestamp to the video frame
            current_time = datetime.now()
            timestamp_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Draw timestamp on frame
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            thickness = 2
            color = (0, 255, 0)  # Green color
            
            (text_width, text_height), baseline = cv2.getTextSize(timestamp_str, font, font_scale, thickness)
            
            # Draw semi-transparent background
            overlay = bgr_frame.copy()
            cv2.rectangle(overlay, (10, 10), (20 + text_width, 40 + text_height), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, bgr_frame, 0.4, 0, bgr_frame)
            
            # Draw timestamp text
            cv2.putText(bgr_frame, timestamp_str, (15, 35), font, font_scale, color, thickness)
            
            camera_writer.write(bgr_frame)
        
        # Display status
        status_text = "RECORDING"
        status_color = (0, 0, 255)  # Red
        cv2.putText(display_frame, status_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
        
        # Display instructions
        instruction_text = f"Press '{chr(SAVE_KEY)}' to save, '{chr(QUIT_KEY)}' to quit"
        cv2.putText(display_frame, instruction_text, (10, display_frame.shape[0] - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Calculate and display FPS
        frame_count += 1
        elapsed_time = time.time() - start_time
        if elapsed_time > 1:
            fps = frame_count / elapsed_time
            frame_count = 0
            start_time = time.time()
        
        cv2.putText(display_frame, f"FPS: {fps:.1f}", (display_frame.shape[1] - 150, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Display recording duration
        if recording_start_time:
            duration = (datetime.now() - recording_start_time).total_seconds()
            duration_text = f"Duration: {duration:.1f}s"
            cv2.putText(display_frame, duration_text, (10, 110), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Display frame
        cv2.imshow('Ball Review System', display_frame)
        
        # Check for key presses
        key = cv2.waitKey(1) & 0xFF
        
        if key == SAVE_KEY:
            print(f"[INFO] Save key pressed. Saving and sending recording...")
            result = stop_and_save_recording()
            if result:
                video_path, start_time = result
                # Process and send in background thread
                email_thread = threading.Thread(
                    target=process_and_send_recording,
                    args=(video_path, start_time),
                    daemon=True
                )
                email_thread.start()
                print("[INFO] Recording saved and email sending started in background...")
                print("[INFO] Recording continues...")
        
        elif key == QUIT_KEY:
            print("[INFO] Quit key pressed. Stopping...")
            break

except KeyboardInterrupt:
    print("\n[INFO] Interrupted by user")

finally:
    cleanup()
    print("[INFO] Ball Review System stopped")

