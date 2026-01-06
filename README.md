# Ball-Review-System

Features:
Continuous recording: starts recording immediately when the program starts
Key press to save: press 's' to save the current recording and send it via email
Continuous operation: after saving, recording continues automatically
Email integration: automatically sends recordings via email using the same email settings
Visual feedback: shows recording status, FPS, and duration on screen
Key Differences from the Intruder Detection System:
Removed face detection — just continuous video recording
Manual save trigger — press 's' to save (instead of automatic detection)
Immediate restart — recording continues after saving
Frame buffer — keeps the last 10 seconds in memory for quick saves
Usage:
Press 's' — Save the current recording and send it via email
Press 'q' — Quit the program
The system will:
Save the current recording file
Convert it to H.264 format (for email compatibility)
Send it via email in the background (so recording isn't interrupted)
Continue recording immediately
All recordings are saved in the ball_review_recordings folder. You can adjust the save key or other settings by modifying the constants at the top of the file.
The email configuration uses the same settings as your intruder detection system, so it should work without changes.
